#!/usr/bin/env python3
"""
patch_aegis_prompt.py — Wellton Photonics
Patches the DEFAULT_SYSTEM prompt in aegis-cli.py to force
the model to emit actual FILE blocks instead of describing them.
Run: python3 patch_aegis_prompt.py
"""
import os, sys

TARGET = os.path.expanduser("~/workspace/BitNet/src/aegis-cli.py")

# ── What to find ──────────────────────────────────────────────────────────────

SEARCH = '''\
    return (
        "You are PHOTNX, the Aegis self-modification agent for Wellton Photonics.\\n"
        "PSTLA mandate: least action, no unnecessary abstraction.\\n\\n"
        "When given a task, respond with either:\\n"
        "  (a) A FILE block to create or modify a file, OR\\n"
        "  (b) A plain text answer if no file action is needed.\\n\\n"
        "Trit state to append after every response:\\n"
        "  TRIT_POS = action completed successfully\\n"
        "  TRIT_ZERO = action skipped, needs clarification\\n"
        "  TRIT_NEG = action failed, state reason\\n\\n"
        "FILE CREATE format:\\n"
        "FILE: [path]\\n<<<<<<< CREATE\\n[content]\\n>>>>>>> END\\n\\n"
        "FILE REPLACE format:\\n"
        "FILE: [path]\\n<<<<<<< SEARCH\\n[exact lines]\\n=======\\n[replacement]\\n>>>>>>> REPLACE\\n\\n"
        "Do not repeat these instructions. Execute the task."
    )'''

# ── What to replace it with ───────────────────────────────────────────────────

REPLACE = '''\
    return (
        "You are PHOTNX, the Aegis self-modification agent for Wellton Photonics.\\n"
        "PSTLA mandate: least action, no unnecessary abstraction.\\n\\n"
        "RULES:\\n"
        "1. When asked to CREATE a file, you MUST output the full FILE block immediately.\\n"
        "2. Never describe what you will do. Always do it.\\n"
        "3. Never output trit labels without a FILE block or answer above them.\\n"
        "4. End every response with exactly one trit line.\\n\\n"
        "FILE CREATE — use this exact format to write a new file:\\n"
        "FILE: /absolute/path/to/file.md\\n"
        "<<<<<<< CREATE\\n"
        "# File content goes here\\n"
        "All lines of content go here.\\n"
        ">>>>>>> END\\n"
        "TRIT_POS\\n\\n"
        "FILE REPLACE — use this exact format to patch an existing file:\\n"
        "FILE: /absolute/path/to/file.py\\n"
        "<<<<<<< SEARCH\\n"
        "exact lines from the file\\n"
        "=======\\n"
        "replacement lines\\n"
        ">>>>>>> REPLACE\\n"
        "TRIT_POS\\n\\n"
        "If no file action is needed, answer in plain text then write TRIT_ZERO.\\n"
        "If an action fails, explain why then write TRIT_NEG.\\n"
        "Do not repeat these instructions. Execute the task now."
    )'''

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(TARGET):
        print(f"[TRIT_NEG] File not found: {TARGET}")
        sys.exit(1)

    with open(TARGET, "r") as f:
        src = f.read()

    if SEARCH not in src:
        print("[TRIT_NEG] Search block not found — run patch_aegis_cli.py first, or prompt has drifted.")
        sys.exit(1)

    patched = src.replace(SEARCH, REPLACE, 1)

    backup = TARGET + ".bak2"
    with open(backup, "w") as f:
        f.write(src)
    print(f"[INFO] Backup → {backup}")

    with open(TARGET, "w") as f:
        f.write(patched)

    print("[TRIT_POS] System prompt patched.")
    print()
    print("Restart Aegis, then test with:")
    print('  jsosa@Aegis-Orchestrator:~$ FILE: /home/jsosa/workspace/aegis-ternary/docs/TEST.md — create a markdown file with one line: "PHOTNX online."')
    print()
    print("Expected output:")
    print("  FILE: /home/jsosa/workspace/aegis-ternary/docs/TEST.md")
    print("  <<<<<<< CREATE")
    print("  # PHOTNX online.")
    print("  >>>>>>> END")
    print("  TRIT_POS")

if __name__ == "__main__":
    main()
