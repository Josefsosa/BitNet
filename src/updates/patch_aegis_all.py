#!/usr/bin/env python3
"""
patch_aegis_all.py — Wellton Photonics
Single script. Patches aegis-cli.py from factory state to full PHOTNX config.
Handles both old prompt and already-patched prompt gracefully.

Run: python3 patch_aegis_all.py
 or: python3 patch_aegis_all.py /path/to/aegis-cli.py
"""
import os, sys

DEFAULT_TARGET = "/home/jsosa/workspace/BitNet/src/aegis-cli.py"
TARGET = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET

# ── New system prompt (final state) ──────────────────────────────────────────
NEW_SYSTEM_PROMPT = '''\
    return (
        "You are PHOTNX, the Aegis self-modification agent for Wellton Photonics.\\n"
        "PSTLA mandate: least action, no unnecessary abstraction.\\n\\n"
        "RULES:\\n"
        "1. When asked to CREATE a file, output the full FILE block immediately.\\n"
        "2. Never describe what you will do. Always do it.\\n"
        "3. Never output trit labels without a FILE block or answer above them.\\n"
        "4. End every response with exactly one trit line.\\n\\n"
        "FILE CREATE format:\\n"
        "FILE: /absolute/path/file.md\\n"
        "<<<<<<< CREATE\\n"
        "# content here\\n"
        ">>>>>>> END\\n"
        "TRIT_POS\\n\\n"
        "FILE REPLACE format:\\n"
        "FILE: /absolute/path/file.py\\n"
        "<<<<<<< SEARCH\\n"
        "exact lines from file\\n"
        "=======\\n"
        "replacement lines\\n"
        ">>>>>>> REPLACE\\n"
        "TRIT_POS\\n\\n"
        "If no file action needed: answer in plain text then TRIT_ZERO.\\n"
        "If action fails: explain why then TRIT_NEG.\\n"
        "Do not repeat these instructions. Execute the task now."
    )'''

# ── All patches: (label, [candidate_searches], replacement) ──────────────────
# Each patch lists MULTIPLE possible search strings (old state, mid-state, etc.)
# First match wins. If none match, patch is skipped as already applied.

PATCHES = [
    (
        "PATCH-1: System prompt → PHOTNX config",
        [
            # Original factory default
            '''\
    return (
        "You are Aegis-Coder for Wellton Photonics. You write code.\\n"
        "To modify files, you MUST use this exact EDIT BLOCK format:\\n"
        "FILE: [path/to/file]\\n"
        "<<<<<<< SEARCH\\n"
        "[exact code to replace]\\n"
        "=======\\n"
        "[new code]\\n"
        ">>>>>>> REPLACE"
    )''',
            # Intermediate state from patch_aegis_cli.py
            '''\
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
    )''',
        ],
        NEW_SYSTEM_PROMPT,
    ),
    (
        "PATCH-2: Prompt format → chat tokens",
        [
            'formatted_prompt = f"System: {system_context}\\nUser: {user_prompt}<|eot_id|>\\nAssistant:"',
        ],
        '''\
    formatted_prompt = (
        f"<|system|>\\n{system_context}\\n"
        f"{context_block}"
        f"<|user|>\\nTASK: {user_prompt}\\n<|assistant|>\\n"
    )''',
    ),
    (
        "PATCH-3: Stop sequences → break loop",
        [
            '"stop": ["<|eot_id|>", "User:", "System:"],',
            '"stop":           ["<|eot_id|>", "User:", "System:"],',
        ],
        '"stop":           ["<|user|>", "<|system|>", "TRIT_POS: POSITIVE\\nTRIT_ZERO"],',
    ),
    (
        "PATCH-4: repeat_penalty 1.2 → 1.3",
        [
            '"repeat_penalty": 1.2, # Added parameter to clamp loops dynamically',
            '"repeat_penalty": 1.2,',
        ],
        '"repeat_penalty": 1.3,',
    ),
]

# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    print(f"Target : {TARGET}\n")

    if not os.path.exists(TARGET):
        print(f"[TRIT_NEG] File not found: {TARGET}")
        print("\nKnown locations on this machine:")
        print("  /home/jsosa/workspace/BitNet/src/aegis-cli.py           <- default")
        print("  /home/jsosa/workspace/aegis-ternary/src/training/aegis-cli.py")
        print("  /home/jsosa/Downloads/aegis-cli.py")
        print("\nUsage: python3 patch_aegis_all.py /correct/path/aegis-cli.py")
        sys.exit(1)

    with open(TARGET, "r") as f:
        src = f.read()

    original = src
    results = []

    for label, searches, replacement in PATCHES:
        matched = False
        for search in searches:
            if search in src:
                src = src.replace(search, replacement, 1)
                print(f"[TRIT_POS]  {label}")
                results.append((label, "applied"))
                matched = True
                break
        if not matched:
            # Check if final state already present
            if replacement.strip() in src:
                print(f"[TRIT_ZERO] {label} — already applied, skipping")
                results.append((label, "skipped"))
            else:
                print(f"[TRIT_NEG]  {label} — no match found, manual review needed")
                results.append((label, "failed"))

    if src == original:
        print("\n[TRIT_ZERO] No changes written — file already fully patched.")
        sys.exit(0)

    backup = TARGET + ".bak"
    with open(backup, "w") as f:
        f.write(original)
    print(f"\n[INFO] Backup → {backup}")

    with open(TARGET, "w") as f:
        f.write(src)

    failed  = [r for r in results if r[1] == "failed"]
    applied = [r for r in results if r[1] == "applied"]

    print(f"\n{'='*52}")
    print(f"  Applied : {len(applied)}")
    print(f"  Skipped : {len([r for r in results if r[1] == 'skipped'])}")
    print(f"  Failed  : {len(failed)}")
    print(f"{'='*52}")

    if failed:
        print("\n[TRIT_ZERO] Partial patch — review failed items above.")
    else:
        print("\n[TRIT_POS] All patches applied → " + TARGET)

    print("\nRestart Aegis, then run this test prompt:")
    print('  FILE: /home/jsosa/workspace/aegis-ternary/docs/TEST.md — create a file with one line: PHOTNX online.')
    print("\nExpected: FILE block output followed by TRIT_POS")

if __name__ == "__main__":
    main()
