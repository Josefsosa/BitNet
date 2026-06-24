#!/usr/bin/env python3
"""
inspect_cli_details.py
Diagnoses system instructions, query engine, and model configuration in aegis-cli.py.
"""

from pathlib import Path
import re

def inspect_cli():
    cli_path = Path("/home/jsosa/workspace/aegis-ternary/src/aegis-cli.py")
    if not cli_path.exists():
        print("[-] Target 'aegis-cli.py' not found.")
        return

    content = cli_path.read_text(encoding="utf-8")
    
    print("====================================================================")
    print("🔍 DIAGNOSTICS: Inspecting system instructions and model calls")
    print("====================================================================\n")

    # 1. Look for GenerativeModel and system instruction passing
    print("[1] Searching for GenerativeModel instantiations and model client calls:")
    gen_matches = re.finditer(r"(\w*GenerativeModel\w*[\s\S]*?\))", content)
    found_any = False
    for m in gen_matches:
        print(f"\n--- MATCH FOUND ---\n{m.group(1)}\n")
        found_any = True
    if not found_any:
        print("[-] No direct GenerativeModel instantiations found using that pattern.")

    # 2. Extract query_engine function block
    print("\n[2] Extracting query_engine function implementation:")
    query_match = re.search(r"(def query_engine[\s\S]*?)(?=\ndef |\nclass |\nif __name__ ==)", content)
    if query_match:
        print(query_match.group(1))
    else:
        print("[-] query_engine function block not found.")

    # 3. Search for any hardcoded project management strings
    print("\n[3] Searching for references to 'project management' or generic assistant prompts:")
    pm_matches = re.finditer(r"(.{0,40}project management.{0,40})", content, re.IGNORECASE)
    for m in pm_matches:
        print(f"-> {m.group(1).strip()}")

    print("\n====================================================================")

if __name__ == "__main__":
    inspect_cli()