#!/usr/bin/env python3
import os
import re
from pathlib import Path

def inspect_and_patch_server():
    server_path = Path("./aegis_local_inference_server.py")
    if not server_path.exists():
        # Let's search parent workspace
        server_path = Path("../BitNet/src/aegis_local_inference_server.py")
        if not server_path.exists():
            print("[-] Could not find aegis_local_inference_server.py in current or parallel directories.")
            return

    print(f"[+] Found local inference server at: {server_path.resolve()}")
    content = server_path.read_text(encoding="utf-8")

    # Let's inspect how headers are forwarded to Headroom / Gemini
    print("[*] Inspecting header handling code...")
    
    # Check if we copy headers directly in a requests.post call
    header_regexes = [
        r"headers\s*=\s*headers",
        r"headers\s*=\s*dict\(request\.headers\)",
        r"request\.headers"
    ]
    
    match_found = False
    for regex in header_regexes:
        if re.search(regex, content):
            print(f"[!] Found direct header forwarding pattern matching: '{regex}'")
            match_found = True

    # Check if 'Host' is stripped. If not, this is our 421 culprit!
    if "headers.pop('Host'" in content or "headers.pop('host'" in content or "del headers['Host']" in content:
        print("[√] 'Host' header removal is already present. The issue might be in the request structure itself.")
    else:
        print("[!] MISSING HOST HEADER POP: The 'Host' header is being forwarded verbatim. This causes SSL/Proxy 421 errors!")
        
        # Patching host headers in request forwarding loop
        # We'll look for where headers are compiled from request.headers, usually dict(request.headers) or request.headers.items()
        
        backup_path = server_path.with_suffix(".py.bak")
        print(f"[*] Creating backup of server file to {backup_path}...")
        server_path.write_text(content, encoding="utf-8") # write backup
        os.system(f"cp {server_path} {backup_path}")

        # Let's do a smart replacement. 
        # Typically, servers have something like:
        # headers = {k: v for k, v in request.headers.items()} or headers = dict(request.headers)
        # We will insert a sanitization step right before the requests.post / requests.request call or in the header builder.
        
        patched = False
        
        # Pattern 1: dictionary conversion of headers
        if "dict(request.headers)" in content:
            content = content.replace(
                "dict(request.headers)",
                "self._sanitize_headers(dict(request.headers))" if "self." in content else "sanitize_headers(dict(request.headers))"
            )
            patched = True
            
        # Let's append the helper function to make sure it's defined
        helper_fn = """
def sanitize_headers(headers):
    # Remove hostile headers that trigger 421 Misdirected Request in reverse proxies
    sanitized = {k: v for k, v in headers.items() if k.lower() not in ['host', 'content-length', 'connection']}
    return sanitized
"""
        if patched:
            content += "\n" + helper_fn
            server_path.write_text(content, encoding="utf-8")
            print("[+] Patched dictionary conversion structure successfully.")
        else:
            # Let's perform a broad-spectrum safety patch on any headers dict variable
            # We will search for requests.post or requests.request calls and intercept headers there
            print("[*] Performing generic requests post patch...")
            # We look for: headers=something in requests calls
            pattern = r"requests\.(post|request|get)\(([^)]*headers\s*=\s*([a-zA-Z0-9_]+)[^)]*)\)"
            
            def replacer(match):
                verb = match.group(1)
                args = match.group(2)
                headers_var = match.group(3)
                # Inject a headers sanitizer line right before or clean it inline
                print(f"[!] Intercepted requests.{verb} with headers variable: '{headers_var}'")
                return f"requests.{verb}({args.replace(f'headers={headers_var}', f'headers={{k: v for k, v in {headers_var}.items() if k.lower() not in [\\\'host\\\', \\\'content-length\\\']}}')})"
                
            new_content, count = re.subn(pattern, replacer, content)
            if count > 0:
                server_path.write_text(new_content, encoding="utf-8")
                print(f"[+] Patched {count} instances of requests forwarding with inline Host header exclusion.")
                patched = True
            else:
                print("[-] Could not automatically patch header dictionaries. Please run the script and inspect the source printout below.")
                print("\n--- FIRST 100 LINES OF SERVER SOURCE CODE ---")
                lines = content.splitlines()
                for i in range(min(120, len(lines))):
                    print(f"{i+1:3d}: {lines[i]}")

if __name__ == "__main__":
    inspect_and_patch_server()