#!/usr/bin/env python3
import os
from pathlib import Path

def sanitize_and_patch_file(filepath: Path):
    if not filepath.exists():
        return False

    print(f"\n[+] Found local inference server at: {filepath.resolve()}")
    content = filepath.read_text(encoding="utf-8")

    # 1. Clean all non-breaking spaces (Unicode \xa0) to standard spaces to prevent IndentationErrors
    if "\xa0" in content:
        print("[*] Detected non-breaking spaces (\\xa0). Standardizing all spacing to ASCII...")
        content = content.replace("\xa0", " ")

    # 2. Extract and replace the entire _forward_to_headroom method block cleanly
    # This prevents partial regex match spacing bugs.
    start_pattern = "def _forward_to_headroom"
    end_pattern = "def do_POST"

    start_idx = content.find(start_pattern)
    end_idx = content.find(end_pattern)

    if start_idx == -1 or end_idx == -1:
        print("[-] Could not locate method boundary blocks safely in this file.")
        return False

    # Standardized, robustly indented 4-space implementation of the forwarding method
    clean_method_block = """def _forward_to_headroom(self, path: str, request_body: bytes, headers: dict) -> tuple:
        \"\"\"Forwards request body to local Port 8787 for context optimization.\"\"\"
        target_url = f"{HEADROOM_PROXY}{path}"
        
        # Build headers dictionary mapping original requests safely
        forward_headers = {
            "Content-Type": "application/json"
        }
        
        # Sanitize headers to prevent 421 Misdirected Request
        for k, v in headers.items():
            k_low = k.lower()
            if k_low not in ['host', 'connection', 'content-length', 'content-type', 'accept-encoding']:
                forward_headers[k] = v

        try:
            req = urllib.request.Request(
                url=target_url,
                data=request_body,
                headers=forward_headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            err_msg = json.dumps({"error": {"message": f"Could not reach Headroom proxy on Port 8787. Verify it is running. Error: {str(e)}"}}).encode("utf-8")
            return 502, err_msg

    """

    # Replace the old slice with our perfectly aligned clean method block
    # Note: Keep the matching indentation (4 spaces before 'def')
    new_content = content[:start_idx] + "    " + clean_method_block + content[end_idx:]

    # Write cleaned and structured file back
    filepath.write_text(new_content, encoding="utf-8")
    print(f"[√] Cleanly sanitized and patched indentation inside: {filepath.name}")
    return True

def main():
    paths_to_patch = [
        Path("/home/jsosa/workspace/BitNet/src/aegis_local_inference_server.py"),
        Path("./aegis_local_inference_server.py"),
        Path("/home/jsosa/workspace/BitNet/src/aegis_server.py"),
        Path("./aegis_server.py")
    ]

    patched_any = False
    for path in paths_to_patch:
        if sanitize_and_patch_file(path):
            patched_any = True

    if not patched_any:
        print("[-] No target server files were found to patch.")

if __name__ == "__main__":
    main()