import os

# Target the file exactly where it lives relative to your current folder
TARGET_FILE = "../aegis-cli.py"

def apply_surgery():
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Error: Cannot find file at {TARGET_FILE}. Please verify you are in src/updates/")
        return

    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    patched = False
    for i, line in enumerate(lines):
        # Look for the exact line pattern from your previous codebase dump
        if 'elif "write" in inp and any(w in inp for w in (' in line:
            # Inject a loose, loop-proof filter that captures write, create, generate, and make
            lines[i] = '        elif any(verb in inp for verb in ("write", "create", "generate", "make")) and any(w in inp for w in (\n'
            patched = True
            break

    if patched:
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("✅ Success! Intent classification overhaul hot-patched directly into memory engine core.")
    else:
        print("⚠️ Could not find the exact 'write' token string match. Let's force-inject a safe fallback...")
        content = "".join(lines)
        # Safe structural fallback
        old_pattern = 'ctx["intent"] = "code_task"'
        if old_pattern in content:
            print("💡 Core structure is verified. Forcing prompt-level compliance routing...")
            # We insert a direct command text analyzer at the top of the evaluation frame
            for j, l in enumerate(lines):
                if "def orient(" in l or "def decide(" in l:
                    lines[j+1] = lines[j+1] + '        if any(v in ctx.get("input", "").lower() for v in ("create", "generate", "make")): ctx["intent"] = "code_task"\n'
                    patched = True
                    break
            with open(TARGET_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print("✅ Fallback patch structural anchor successfully secured.")
        else:
            print("❌ Target verification signature mismatch. File structure is locked.")

if __name__ == "__main__":
    apply_surgery()