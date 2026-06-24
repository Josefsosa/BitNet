#!/usr/bin/env python3
"""
check_servers_code.py
Parses aegis_cli.py to locate all references to NDGi, port 8000, 8080, and server management logic.
"""

from pathlib import Path
import re

def scan_server_logic():
    cli_path = Path("/home/jsosa/workspace/aegis-ternary/src/aegis-cli.py")
    if not cli_path.exists():
        print("[-] Target 'aegis-cli.py' not found.")
        return

    content = cli_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    print("🔎 Scanning aegis-cli.py for Server references...")
    
    # Common search keywords
    keywords = ["8000", "8080", "BitNet", "NDGi", "server", "port"]
    
    found_lines = []
    for idx, line in enumerate(lines, 1):
        if any(kw in line for kw in keywords):
            found_lines.append((idx, line.strip()))

    print(f"[*] Found {len(found_lines)} matching lines. Displaying key blocks:")
    
    # Show status or start-up related matches
    for idx, line in found_lines:
        if any(kw in line for kw in ["8000", "8080", "BitNet", "NDGi", "subprocess", "socket"]):
            print(f"Line {idx:04d}: {line}")

if __name__ == "__main__":
    scan_server_logic()