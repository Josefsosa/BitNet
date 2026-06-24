#!/usr/bin/env python3
"""
patch_aegis_cli.py — Wellton Photonics
Applies all three loop-fix patches to aegis-cli.py in place.
Run: python3 patch_aegis_cli.py
"""
import os, sys, re

TARGET = os.path.expanduser("~/workspace/aegis-ternary/aegis-cli.py")

# ── Patch definitions ─────────────────────────────────────────────────────────

PATCH_1_SEARCH = '''\
    return (
        "You are Aegis-Coder for Wellton Photonics. You write code.\\n"
        "To modify files, you MUST use this exact EDIT BLOCK format:\\n"
        "FILE: [path/to/file]\\n"
        "<<<<<<< SEARCH\\n"
        "[exact code to replace]\\n"
        "=======\\n"
        "[new code]\\n"
        ">>>>>>> REPLACE"
    )'''

PATCH_1_REPLACE = '''\
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

PATCH_2_SEARCH = '''\
    formatted_prompt = (
        f"System: {system_context}\\n"
        f"{context_block}"
        f"User: {user_prompt}<|eot_id|>\\nAssistant:"
    )'''

PATCH_2_REPLACE = '''\
    formatted_prompt = (
        f"<|system|>\\n{system_context}\\n"
        f"{context_block}"
        f"<|user|>\\nTASK: {user_prompt}\\n<|assistant|>\\n"
    )'''

PATCH_3_SEARCH = '''\
        "stop":           ["<|eot_id|>", "User:", "System:"],'''

PATCH_3_REPLACE = '''\
        "stop":           ["<|user|>", "<|system|>", "TRIT_POS: POSITIVE\\nTRIT_ZERO"],'''

PATCH_4_SEARCH = '''\
        "repeat_penalty": 1.2,'''

PATCH_4_REPLACE = '''\
        "repeat_penalty": 1.3,'''

PATCHES = [
    ("PATCH-1: Replace default system prompt", PATCH_1_SEARCH, PATCH_1_REPLACE),
    ("PATCH-2: Fix prompt format tokens",      PATCH_2_SEARCH, PATCH_2_REPLACE),
    ("PATCH-3: Fix stop sequences",            PATCH_3_SEARCH, PATCH_3_REPLACE),
    ("PATCH-4: Bump repeat_penalty 1.2→1.3",  PATCH_4_SEARCH, PATCH_4_REPLACE),
]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(TARGET):
        print(f"[TRIT_NEG] File not found: {TARGET}")
        print(f"           Set TARGET at top of this script to the correct path.")
        sys.exit(1)

    with open(TARGET, "r") as f:
        src = f.read()

    original = src
    all_ok = True

    for label, search, replace in PATCHES:
        if search in src:
            src = src.replace(search, replace, 1)
            print(f"[TRIT_POS] {label}")
        else:
            print(f"[TRIT_NEG] {label} — search block not found (already patched or drift)")
            all_ok = False

    if src == original:
        print("\n[TRIT_ZERO] No changes written — all patches already applied or all missed.")
        sys.exit(0)

    backup = TARGET + ".bak"
    with open(backup, "w") as f:
        f.write(original)
    print(f"\n[INFO] Backup written → {backup}")

    with open(TARGET, "w") as f:
        f.write(src)

    status = "TRIT_POS" if all_ok else "TRIT_ZERO"
    print(f"[{status}] Patch complete → {TARGET}")
    print("\nQuick test — paste this into Aegis after restart:")
    print('  jsosa@Aegis-Orchestrator:~$ What is 2 + 2? Answer in one line.')
    print("  Expected: '4. TRIT_POS'")

if __name__ == "__main__":
    main()
