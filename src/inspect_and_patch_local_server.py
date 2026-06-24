#!/usr/bin/env python3
import os
import sys
import re
import subprocess
from pathlib import Path

def sanitize_and_patch_file(filepath: Path) -> bool:
    if not filepath.exists():
        return False

    print(f"\n[+] Found local inference server at: {filepath.resolve()}")
    content = filepath.read_text(encoding="utf-8")

    # 1. Strip out Unicode non-breaking spaces (\xa0) and standardize spacing
    if "\xa0" in content:
        print("[*] Standardizing non-breaking space anomalies to standard ASCII...")
        content = content.replace("\xa0", " ")

    # 2. Split file into lines for line-by-line surgical replacement
    lines = content.splitlines()
    start_line_idx = -1
    end_line_idx = -1

    for idx, line in enumerate(lines):
        if "def _forward_to_headroom" in line:
            start_line_idx = idx
        if "def do_POST" in line:
            end_line_idx = idx
            break

    if start_line_idx == -1 or end_line_idx == -1:
        print("[-] Could not locate method boundary blocks safely in this file.")
        return False

    # 3. Rebuild the method block with absolute, normalized indentation rules
    # Ensures perfect class member alignment (4 spaces for def, 8 spaces for body)
    indent = "    "
    body_indent = "        "

    # Define raw body statements (without leading body_indentation prefix)
    body_lines = [
        '"""Forwards request body to local Port 8787 for context optimization."""',
        'target_url = f"{HEADROOM_PROXY}{path}"',
        '',
        '# Build headers dictionary mapping original requests safely',
        'forward_headers = {',
        '    "Content-Type": "application/json"',
        '}',
        '',
        '# Strip routing-interfering reverse proxy headers',
        'excluded_headers = {',
        "    'host',",
        "    'connection',",
        "    'content-length',",
        "    'content-type',",
        "    'accept-encoding',",
        "    'proxy-connection',",
        "    'keep-alive'",
        '}',
        '',
        'for k, v in headers.items():',
        '    k_low = k.lower()',
        '    if k_low not in excluded_headers:',
        '        forward_headers[str(k)] = str(v)',
        '',
        'if "Authorization" in headers:',
        '    forward_headers["Authorization"] = headers["Authorization"]',
        '',
        'try:',
        '    req = urllib.request.Request(',
        '        url=target_url,',
        '        data=request_body,',
        '        headers=forward_headers,',
        '        method="POST"',
        '    )',
        '    with urllib.request.urlopen(req, timeout=60) as response:',
        '        return response.status, response.read()',
        'except urllib.error.HTTPError as e:',
        '    return e.code, e.read()',
        'except Exception as e:',
        '    err_msg = json.dumps({"error": {"message": f"Could not reach Headroom proxy on Port 8787. Verify it is running. Error: {str(e)}"}}).encode("utf-8")',
        '    return 502, err_msg',
        ''
    ]

    # Generate full standardized lines array
    template = [f"{indent}def _forward_to_headroom(self, path: str, request_body: bytes, headers: dict) -> tuple:"]
    for body_line in body_lines:
        if body_line == '':
            template.append('')
        else:
            template.append(f"{body_indent}{body_line}")

    # Reconstruct whole file lines
    new_lines = lines[:start_line_idx] + template + lines[end_line_idx:]
    new_content = "\n".join(new_lines) + "\n"

    # Write cleaned content back
    filepath.write_text(new_content, encoding="utf-8")
    print(f"[√] Successfully patched spacing and indentation in: {filepath.name}")

    # Validate syntax check using Python's compiler module
    try:
        subprocess.run(
            [sys.executable, "-m", "py_compile", str(filepath)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"[+] Syntax validation PASSED for: {filepath.name}")
    except subprocess.CalledProcessError as err:
        print(f"[-] Syntax validation FAILED for {filepath.name}:")
        print(err.stderr.decode('utf-8'))
        return False

    return True


def sanitize_and_patch_cli(filepath: Path) -> bool:
    if not filepath.exists():
        return False

    print(f"\n[+] Found Aegis CLI at: {filepath.resolve()}")
    content = filepath.read_text(encoding="utf-8")
    patched = False

    # 1. Clean non-breaking spaces
    if "\xa0" in content:
        print("[*] Standardizing non-breaking space anomalies in CLI code to ASCII...")
        content = content.replace("\xa0", " ")
        patched = True

    # 2. Fix unconditional endpoint string slice truncation: replaces endpoint[:-1] with endpoint.rstrip('/')
    slice_pattern = re.compile(r'(\b\w*endpoint\w*)\s*\[\s*:\s*-1\s*\]')
    if slice_pattern.search(content):
        matches = slice_pattern.findall(content)
        print(f"[*] Detected potential unconditional slice truncation on endpoint variables: {matches}")
        content = slice_pattern.sub(r"\1.rstrip('/')", content)
        patched = True

    # 3. Clean any literal "localhost:500" configurations (checking for word boundary so it doesn't touch localhost:5000)
    host_pattern = re.compile(r'localhost:500\b')
    if host_pattern.search(content):
        print("[!] Detected literal Port 500 endpoint reference! Patching to 5000...")
        content = host_pattern.sub("localhost:5000", content)
        patched = True

    # 4. Clean other configuration default values containing '500' associated with the endpoint
    def port_repl(match):
        return match.group(1) + "5000"
    content, count = re.subn(r'(\bendpoint\b.*\b)500\b', port_repl, content)
    if count > 0:
        print(f"[*] Cleaned {count} legacy configuration port 500 defaults to 5000.")
        patched = True

    if patched:
        filepath.write_text(content, encoding="utf-8")
        print(f"[√] Successfully patched and corrected slice logic in: {filepath.name}")
        
        # Compile validation
        try:
            subprocess.run(
                [sys.executable, "-m", "py_compile", str(filepath)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"[+] Syntax validation PASSED for: {filepath.name}")
        except subprocess.CalledProcessError as err:
            print(f"[-] Syntax validation FAILED for {filepath.name}:")
            print(err.stderr.decode('utf-8'))
            return False
        return True
    else:
        print("[-] No trailing-slice anomalies detected in this CLI file copy.")
        return False


def main():
    # 1. Server targets
    server_paths = [
        Path("/home/jsosa/workspace/BitNet/src/aegis_local_inference_server.py"),
        Path("./aegis_local_inference_server.py"),
        Path("/home/jsosa/workspace/BitNet/src/aegis_server.py"),
        Path("./aegis_server.py")
    ]

    for path in server_paths:
        sanitize_and_patch_file(path)

    # 2. CLI targets (resolving relative paths to workspace workspace-level directories)
    cli_paths = [
        Path("/home/jsosa/workspace/aegis-ternary/src/aegis-cli.py"),
        Path("../../aegis-ternary/src/aegis-cli.py"),
        Path("../aegis-ternary/src/aegis-cli.py"),
        Path("./aegis-cli.py")
    ]

    for path in cli_paths:
        sanitize_and_patch_cli(path)

if __name__ == "__main__":
    main()