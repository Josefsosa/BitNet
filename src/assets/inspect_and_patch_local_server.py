#!/usr/bin/env python3
import os
import re
from pathlib import Path

def inspect_and_patch_server():
    server_path = Path("/home/jsosa/workspace/BitNet/src/aegis_server.py")
    if not server_path.exists():
        server_path = Path("./aegis_server.py")
        if not server_path.exists():
            print("[-] Could not find aegis_server.py in current or absolute directories.")
            return

    print(f"[+] Found local inference server at: {server_path.resolve()}")
    content = server_path.read_text(encoding="utf-8")

    print("[*] Inspecting full header handling code...")
    
    # Let's print out lines 100 to 250 to analyze exactly how the server handles POST requests
    lines = content.splitlines()
    print("\n--- LINES 100 TO 220 OF SERVER SOURCE CODE ---")
    start_line = 100
    end_line = min(220, len(lines))
    for i in range(start_line - 1, end_line):
        print(f"{i+1:3d}: {lines[i]}")

    print("\n[*] Analyzing potential 421 header leakage points...")
    
    # We want to check if any request object forwarded from urllib/requests retains the incoming Host header
    # Or if Headroom Proxy requires an explicit Host header override
    # Let's look for any 'Host' modifications or where urllib.request is called
    
    # Let's write a patch that guarantees Host, Content-Length, and Connection headers are sanitized 
    # before we send anything to the Headroom proxy.
    
    # Let's search for "forward_headers = {" in the file
    if "forward_headers = {" in content:
        print("[!] Found forward_headers creation block. Patching to explicitly clean or assign host...")
        
        # We will add cleaning code to make sure we don't accidentally forward a hostile Host header,
        # and ensure the Host header matches what urllib expects or is fully deleted so urllib can auto-populate it.
        # If Host exists in forward_headers, we delete it.
        
        # Let's also check if Headroom Proxy expects the real destination host (e.g. Gemini's host) instead of localhost
        # Often, reverse proxies like Cloudflare or corporate gateways look at the 'Host' header to route requests.
        # If Headroom routing handler receives the request, it should have a sanitized header list.
        
        # Let's update _forward_to_headroom to sanitize any passed headers explicitly.
        # We will replace lines 104-110 with a safer block that avoids passing any incoming Host header.
        old_headers_block = """         # Build headers dictionary mapping original requests safely
         forward_headers = {
             "Content-Type": "application/json"
         }
         if "Authorization" in headers:
             forward_headers["Authorization"] = headers["Authorization"]"""

        new_headers_block = """         # Build headers dictionary mapping original requests safely
         forward_headers = {
             "Content-Type": "application/json"
         }
         # Sanitize headers to prevent 421 Misdirected Request
         for k, v in headers.items():
             k_low = k.lower()
             if k_low not in ['host', 'connection', 'content-length', 'content-type', 'accept-encoding']:
                 forward_headers[k] = v"""
                 
        if old_headers_block in content:
            content = content.replace(old_headers_block, new_headers_block)
            print("[√] Replaced forward_headers dictionary block successfully with clean mappings.")
            server_path.write_text(content, encoding="utf-8")
        else:
            # Flexible regex-based replace if spacing varies
            pattern = r"forward_headers\s*=\s*\{[^}]*\}"
            content, count = re.subn(pattern, """forward_headers = {
             "Content-Type": "application/json"
         }
         for k, v in headers.items():
             if k.lower() not in ['host', 'connection', 'content-length', 'content-type', 'accept-encoding']:
                 forward_headers[k] = v""", content)
            if count > 0:
                print(f"[√] Patched {count} spacing-variable header dictionaries.")
                server_path.write_text(content, encoding="utf-8")
            else:
                print("[-] Could not automatically replace. Please review the printout above to patch manually.")

if __name__ == "__main__":
    inspect_and_patch_server()