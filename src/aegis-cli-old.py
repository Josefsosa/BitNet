#!/usr/bin/env python3
import os
import sys
import time
import requests
import json
import re

# ── Configuration ────────────────────────────────────────────────────────────
API_URL            = "http://localhost:8080/completion"
SYSTEM_PROMPT_FILE = "aegis_system_prompt.txt"
MAX_HISTORY_TURNS  = 10          # rolling context window (pairs)
WORKSPACE_ROOT     = os.path.expanduser("~/workspace/aegis-ternary")

# ── System prompt ─────────────────────────────────────────────────────────────
DEFAULT_SYSTEM = (
    "You are PHOTNX, the Aegis self-modification agent for Wellton Photonics.\n"
    "PSTLA mandate: least action, no unnecessary abstraction.\n\n"
    "When given a task, respond with either:\n"
    "  (a) A FILE block to create or modify a file, OR\n"
    "  (b) A plain text answer if no file action is needed.\n\n"
    "Trit state to append after every response:\n"
    "  TRIT_POS = action completed successfully\n"
    "  TRIT_ZERO = action skipped, needs clarification\n"
    "  TRIT_NEG = action failed, state reason\n\n"
    "FILE CREATE format:\n"
    "FILE: [path]\n<<<<<<< CREATE\n[content]\n>>>>>>> END\n\n"
    "FILE REPLACE format:\n"
    "FILE: [path]\n<<<<<<< SEARCH\n[exact lines]\n=======\n[replacement]\n>>>>>>> REPLACE\n\n"
    "Do not repeat these instructions. Execute the task."
)

def load_system_prompt():
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, 'r') as f:
            return f.read().strip()
    return DEFAULT_SYSTEM

# ── Splash ────────────────────────────────────────────────────────────────────
def display_splash():
    os.system('clear')
    splash = """
    \033[1;36m
    ██████╗ ██╗  ██╗ ██████╗ ████████╗███╗  ██╗██╗  ██╗
    ██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝████╗ ██║╚██╗██╔╝
    ██████╔╝███████║██║   ██║   ██║   ██╔██╗██║ ╚███╔╝ 
    ██╔═══╝ ██╔══██║██║   ██║   ██║   ██║╚████║ ██╔██╗ 
    ██║     ██║  ██║╚██████╔╝   ██║   ██║ ╚███║██╔╝╚██╗
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚══╝╚═╝  ╚═╝
    \033[0m
    \033[0;36m┌───────────────────────────────────────────────────────┐
    │           AEGIS SELF-MODIFICATION ENGINE              │
    │  Ternary Quantization v1.58  ·  BET 4-trits/byte      │
    │  Skip-on-Zero: ON  ·  PSTLA Mandate: ACTIVE           │
    ├──────────┬──────────┬──────────┬──────────────────────┤
    │ OBSERVE  │  ORIENT  │  DECIDE  │  ACT                 │
    ├──────────┴──────────┴──────────┴──────────────────────┤
    │  Agents: PHOTNX · SENTINEL · TRUTCH · CIBA ·          │
    │          ARCHON · PATHFINDER                          │
    ├───────────────────────────────────────────────────────┤
    │  Engine : BitNet b1.58    Tests  : 51/54 GREEN        │
    │  Speed  : 8.04× (≥1.7×)  NDGi   : PERSISTENT          │
    │  TRIT_NEG[-1]=0x2  TRIT_ZERO[0]=0x3  TRIT_POS[+1]=0x1 │
    └───────────────────────────────────────────────────────┘
    Wellton Photonics — Mill Creek Lab Wa and Phoenix Az \033[0m
    """
    print(splash)
    print(" [\033[1;32m*\033[0m] Logic Engine Active. Standing by for commands...")
    print("-" * 67 + "\n")

# ── Path resolution ───────────────────────────────────────────────────────────
def resolve_path(raw_path: str) -> str:
    """
    Resolve a path from the model response.
    Accepts absolute paths or paths relative to WORKSPACE_ROOT.
    Expands ~ in both cases.
    """
    p = raw_path.strip()
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return p
    return os.path.join(WORKSPACE_ROOT, p)

# ── Fuzzy search match ────────────────────────────────────────────────────────
def fuzzy_find(content: str, search_block: str) -> int:
    """
    Returns start index of search_block inside content.
    First tries exact match, then strip-normalized match,
    then line-by-line stripped comparison.
    Returns -1 on complete failure.
    """
    # 1. Exact
    idx = content.find(search_block)
    if idx != -1:
        return idx

    # 2. Strip each line, rejoin — handles trailing-space drift
    def normalize(text):
        return "\n".join(line.rstrip() for line in text.splitlines())

    norm_content = normalize(content)
    norm_search  = normalize(search_block)
    idx = norm_content.find(norm_search)
    if idx != -1:
        # Map normalized index back to original — count newlines to line
        target_line = norm_content[:idx].count("\n")
        orig_lines  = content.splitlines(keepends=True)
        orig_idx    = sum(len(l) for l in orig_lines[:target_line])
        # Find end of the block in original
        search_lines = norm_search.count("\n") + 1
        end_line     = target_line + search_lines
        orig_end     = sum(len(l) for l in orig_lines[:end_line])
        return (orig_idx, orig_end)      # return tuple for splice

    return -1

# ── File edit engine ──────────────────────────────────────────────────────────
def apply_all_edits(response_text: str) -> list[dict]:
    """
    Scans the full response for ALL FILE blocks and applies them.
    Supports two operations:
      CREATE  — writes new file (creates dirs if needed)
      REPLACE — patches existing file with fuzzy search matching
    Returns a list of result dicts for session history injection.
    """
    results = []

    # ── CREATE blocks ──────────────────────────────────────────────────────
    create_pattern = re.compile(
        r"FILE:\s*(.+?)\n<<<<<<< CREATE\n(.*?)\n>>>>>>> END",
        re.DOTALL
    )
    for m in create_pattern.finditer(response_text):
        raw_path = m.group(1).strip()
        content  = m.group(2)
        filepath = resolve_path(raw_path)

        print(f"\n\033[1;33m[Aegis I/O]: CREATE → {filepath}\033[0m")
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"\033[1;32m[TRIT_POS]: {filepath} created.\033[0m")
            results.append({"op": "create", "path": filepath, "ok": True})
        except Exception as e:
            print(f"\033[1;31m[TRIT_NEG]: Create failed — {e}\033[0m")
            results.append({"op": "create", "path": filepath, "ok": False, "err": str(e)})

    # ── REPLACE blocks ─────────────────────────────────────────────────────
    replace_pattern = re.compile(
        r"FILE:\s*(.+?)\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
        re.DOTALL
    )
    for m in replace_pattern.finditer(response_text):
        raw_path     = m.group(1).strip()
        search_block = m.group(2)
        replace_block= m.group(3)
        filepath     = resolve_path(raw_path)

        print(f"\n\033[1;33m[Aegis I/O]: REPLACE → {filepath}\033[0m")

        # Auto-create parent dirs even for replace ops
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if not os.path.exists(filepath):
            # File missing — offer to create it with the replace block as content
            print(f"\033[1;33m[TRIT_ZERO]: File not found. Creating with replacement content.\033[0m")
            try:
                with open(filepath, 'w') as f:
                    f.write(replace_block)
                print(f"\033[1;32m[TRIT_POS]: {filepath} created (from replace block).\033[0m")
                results.append({"op": "replace", "path": filepath, "ok": True, "note": "created"})
            except Exception as e:
                print(f"\033[1;31m[TRIT_NEG]: Create failed — {e}\033[0m")
                results.append({"op": "replace", "path": filepath, "ok": False, "err": str(e)})
            continue

        try:
            with open(filepath, 'r') as f:
                original = f.read()
        except Exception as e:
            print(f"\033[1;31m[TRIT_NEG]: Read failed — {e}\033[0m")
            results.append({"op": "replace", "path": filepath, "ok": False, "err": str(e)})
            continue

        match_result = fuzzy_find(original, search_block)

        if match_result == -1:
            print("\033[1;31m[TRIT_NEG]: Search block not matched — no edit applied.\033[0m")
            print("\033[0;33m[Hint]: Dump the target file with: cat " + filepath + "\033[0m")
            results.append({"op": "replace", "path": filepath, "ok": False, "err": "no_match"})
            continue

        # splice or simple replace
        if isinstance(match_result, tuple):
            start, end = match_result
            updated = original[:start] + replace_block + original[end:]
        else:
            updated = original.replace(search_block, replace_block, 1)

        try:
            with open(filepath, 'w') as f:
                f.write(updated)
            print(f"\033[1;32m[TRIT_POS]: {filepath} patched successfully.\033[0m")
            results.append({"op": "replace", "path": filepath, "ok": True})
        except Exception as e:
            print(f"\033[1;31m[TRIT_NEG]: Write failed — {e}\033[0m")
            results.append({"op": "replace", "path": filepath, "ok": False, "err": str(e)})

    return results

# ── Query engine ──────────────────────────────────────────────────────────────
def query_ternary_engine(system_context: str, history: list, user_prompt: str) -> str:
    """
    Builds a rolling-context prompt from history, streams the response,
    applies all file edits, and returns the full accumulated response text.
    """
    # Build multi-turn context block
    context_block = ""
    for turn in history[-MAX_HISTORY_TURNS:]:
        context_block += f"User: {turn['user']}\nAssistant: {turn['assistant']}\n"

    formatted_prompt = (
        f"System: {system_context}\n"
        f"{context_block}"
        f"User: {user_prompt}<|eot_id|>\nAssistant:"
    )

    payload = {
        "prompt":         formatted_prompt,
        "n_predict":      2048,
        "temperature":    0.1,
        "repeat_penalty": 1.3,
        "stop":           ["<|user|>", "<|system|>", "TRIT_POS: POSITIVE\nTRIT_ZERO"],
        "stream":         True
    }

    sys.stdout.write("\n\033[1;36mAegis-PHOTNX:\033[0m ")
    sys.stdout.flush()

    accumulated_text = ""
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=120
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                line_str = line_str[6:]
            try:
                data_json = json.loads(line_str)
                token = data_json.get("content", "")
                accumulated_text += token
                sys.stdout.write(token)
                sys.stdout.flush()
                if data_json.get("stop", False):
                    break
            except json.JSONDecodeError:
                continue

    except requests.exceptions.ConnectionError:
        print("\n\033[1;31m[Error]: llama-server not reachable at " + API_URL + "\033[0m")
        print("\033[0;33m[Hint]: cd ~/BitNet && ./llama-server -m models/ggml-model-i2_s.gguf --port 8080\033[0m\n")
        return ""
    except requests.exceptions.Timeout:
        print("\n\033[1;31m[Error]: Request timed out (120s).\033[0m\n")
        return ""
    except requests.exceptions.HTTPError as e:
        print(f"\n\033[1;31m[Error]: HTTP {e.response.status_code}\033[0m\n")
        return ""

    # Ensure newline after streamed output
    print("\n")

    # Apply every FILE block found in the response
    edit_results = apply_all_edits(accumulated_text)

    # Append edit summary to session memory so next turn knows what happened
    if edit_results:
        ok  = [r for r in edit_results if r["ok"]]
        err = [r for r in edit_results if not r["ok"]]
        summary = f"\n[Session: {len(ok)} edit(s) applied"
        if err:
            summary += f", {len(err)} failed: " + ", ".join(r.get("err","?") for r in err)
        summary += "]"
        accumulated_text += summary

    return accumulated_text

# ── Local command handler ─────────────────────────────────────────────────────
def handle_local_command(cmd: str) -> bool:
    """Returns True if the command was handled locally, False to pass to engine."""
    c = cmd.strip().lower()

    if c in ('time', 'what time is it?'):
        print(f"\n\033[1;34m[Local]:\033[0m {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        return True

    if c == 'clear':
        display_splash()
        return True

    if c.startswith('ls ') or c == 'ls':
        path = c[3:].strip() or '.'
        path = resolve_path(path)
        try:
            entries = os.listdir(path)
            print("\n" + "\n".join(sorted(entries)) + "\n")
        except Exception as e:
            print(f"\033[1;31m[Error]: {e}\033[0m\n")
        return True

    if c.startswith('cat '):
        path = resolve_path(cmd.strip()[4:].strip())
        try:
            with open(path) as f:
                print("\n\033[0;36m" + f.read() + "\033[0m\n")
        except Exception as e:
            print(f"\033[1;31m[Error]: {e}\033[0m\n")
        return True

    if c == 'history':
        return False   # let main() handle printing history

    if c in ('exit', 'quit'):
        return False   # let main() handle exit

    return False

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    system_context = load_system_prompt()
    display_splash()

    # Rolling session history: list of {"user": str, "assistant": str}
    history: list[dict] = []

    while True:
        try:
            user_input = input("\033[1;32mjsosa@Aegis-Orchestrator:\033[0m~$ ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('exit', 'quit'):
                print("\n\033[0;36m[Aegis]: Session closed. TRIT_POS.\033[0m\n")
                break

            if user_input.lower() == 'history':
                for i, t in enumerate(history, 1):
                    print(f"\n\033[0;36m[{i}] User:\033[0m {t['user'][:80]}")
                    print(f"\033[0;36m    Aegis:\033[0m {t['assistant'][:120]}...")
                print()
                continue

            if handle_local_command(user_input):
                continue

            response_text = query_ternary_engine(system_context, history, user_input)

            if response_text:
                history.append({"user": user_input, "assistant": response_text})
                # Keep history bounded
                if len(history) > MAX_HISTORY_TURNS:
                    history = history[-MAX_HISTORY_TURNS:]

        except KeyboardInterrupt:
            print("\n\n\033[1;33m[Aegis]: Use 'exit' to close cleanly.\033[0m")

if __name__ == "__main__":
    main()
