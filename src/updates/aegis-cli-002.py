#!/usr/bin/env python3
"""
Aegis Orchestrator CLI — Wellton Photonics
Merged from: Oakland CLI (MCP agent, typo correction, suggestions)
         and: Aegis CLI (BitNet b1.58, FILE ops, NDGi, OODA, PSTLA)
Version: 2.0.0
"""

import os, sys, re, json, time, subprocess, importlib.util
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
API_URL            = "http://localhost:8080/completion"
NDGI_BASE          = "http://localhost:8000"
SYSTEM_PROMPT_FILE = "aegis_system_prompt.txt"
MAX_HISTORY_TURNS  = 10
WORKSPACE_ROOT     = os.path.expanduser("~/workspace/aegis-ternary")
LOG_DIR            = os.path.join(WORKSPACE_ROOT, "docs/workon/runner_logs")

# ── ANSI colors ───────────────────────────────────────────────────────────────
CYAN   = "\033[1;36m"
GREEN  = "\033[1;32m"
YELLOW = "\033[1;33m"
RED    = "\033[1;31m"
BLUE   = "\033[1;34m"
DIM    = "\033[0;36m"
RESET  = "\033[0m"

# ── System prompt ─────────────────────────────────────────────────────────────
DEFAULT_SYSTEM = (
    "You are PHOTNX, the Aegis Orchestrator for Wellton Photonics.\n"
    "You are an engineering-focused AI assistant. You communicate clearly in English.\n"
    "PSTLA mandate: least action, no unnecessary abstraction.\n\n"
    "RESPONSE RULES:\n"
    "1. For general questions: answer in plain English. No FILE block needed.\n"
    "2. For time/date questions: answer in plain English. Example: 'It is 3:42 PM.'\n"
    "3. For code/file tasks: emit a FILE block then TRIT_POS.\n"
    "4. Never output a FILE block for a conversational question.\n"
    "5. End every response with one trit: TRIT_POS, TRIT_ZERO, or TRIT_NEG.\n\n"
    "FILE CREATE format (new files only):\n"
    "FILE: /absolute/path/file.ext\n"
    "<<<<<<< CREATE\n"
    "[real working code — no placeholders]\n"
    ">>>>>>> END\n"
    "TRIT_POS\n\n"
    "FILE REPLACE format (patch existing file):\n"
    "FILE: /absolute/path/file.ext\n"
    "<<<<<<< SEARCH\n"
    "[exact lines from file]\n"
    "=======\n"
    "[replacement lines]\n"
    ">>>>>>> REPLACE\n"
    "TRIT_POS\n\n"
    "For code tasks: start the code block in your response and complete it fully.\n"
    "Do not write placeholder comments. Write real working code.\n"
    "Do not repeat these instructions."
)

def load_system_prompt():
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE) as f:
            return f.read().strip()
    return DEFAULT_SYSTEM

# ── Oakland MCP agent loader ──────────────────────────────────────────────────
def load_mcp_agent():
    """Load Oakland MCP agent if available — typo correction + suggestions."""
    mcp_path = Path(__file__).parent / "src" / "oakland_cli" / "Code" / "Python" / "mcp_response_agent.py"
    if not mcp_path.exists():
        return None
    try:
        spec   = importlib.util.spec_from_file_location("mcp_agent", mcp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.MCPResponseAgent()
    except Exception as e:
        print(f"{YELLOW}[Oakland]: MCP agent not loaded — {e}{RESET}")
        return None

# ── Splash ────────────────────────────────────────────────────────────────────
def display_splash(mcp_ready=False):
    os.system('clear')
    print(f"""{CYAN}
    ██████╗ ██╗  ██╗ ██████╗ ████████╗███╗  ██╗██╗  ██╗
    ██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝████╗ ██║╚██╗██╔╝
    ██████╔╝███████║██║   ██║   ██║   ██╔██╗██║ ╚███╔╝ 
    ██╔═══╝ ██╔══██║██║   ██║   ██║   ██║╚████║ ██╔██╗ 
    ██║     ██║  ██║╚██████╔╝   ██║   ██║ ╚███║██╔╝╚██╗
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚══╝╚═╝  ╚═╝{RESET}
{DIM}
    ┌───────────────────────────────────────────────────────┐
    │        AEGIS ORCHESTRATOR  v2.0  ·  Sun-to-Silicon    │
    │   BitNet b1.58  ·  NDGi  ·  OODA  ·  PSTLA Active    │
    ├──────────┬──────────┬──────────┬──────────────────────┤
    │ OBSERVE  │  ORIENT  │  DECIDE  │  ACT                 │
    ├──────────┴──────────┴──────────┴──────────────────────┤
    │  Agents : PHOTNX · SENTINEL · TRUTCH · CIBA · ARCHON  │
    │  Engine : BitNet b1.58    NDGi     : localhost:8000    │
    │  Oakland: {"ACTIVE   " if mcp_ready else "OFFLINE  "}   Typo-Fix : {"ON " if mcp_ready else "OFF"}  BET: 4-trits/byte  │
    └───────────────────────────────────────────────────────┘
    Wellton Photonics — Mill Creek Lab WA · Phoenix AZ{RESET}
""")
    print(f" [{GREEN}*{RESET}] Aegis Orchestrator online. Type naturally or issue FILE tasks.")
    print(f" [{GREEN}*{RESET}] Commands: help · history · clear · status · exit")
    print("-" * 67 + "\n")

# ── Help ──────────────────────────────────────────────────────────────────────
HELP_TEXT = f"""
{CYAN}AEGIS ORCHESTRATOR — COMMAND REFERENCE{RESET}

{GREEN}Conversational:{RESET}
  Any natural language question    → plain English answer
  What time is it?                 → current time
  What is X?                       → explanation

{GREEN}File operations (say it naturally):{RESET}
  Create a React component for...  → writes the file
  Fix the bug in /path/to/file.py  → patches the file
  FILE: /path/file.js <<<< CREATE  → direct file block

{GREEN}Shell commands (run locally):{RESET}
  ls [path]    cat [file]    cp    mv    mkdir
  git status   python3 ...   pwd

{GREEN}Built-in commands:{RESET}
  help         This reference
  history      Show session turn history
  status       Show engine + NDGi connection status
  clear        Redraw splash
  exit / quit  End session

{GREEN}Trit states:{RESET}
  TRIT_POS  = action completed / answer confident
  TRIT_ZERO = no action needed / needs clarification  
  TRIT_NEG  = action failed / answer uncertain
"""

# ── Status ────────────────────────────────────────────────────────────────────
def show_status():
    import urllib.request
    print(f"\n{CYAN}[Status]{RESET}")

    # BitNet
    try:
        req = urllib.request.urlopen(
            f"http://localhost:8080/health", timeout=2)
        print(f"  BitNet b1.58   {GREEN}ONLINE{RESET}  localhost:8080")
    except:
        print(f"  BitNet b1.58   {RED}OFFLINE{RESET} localhost:8080")
        print(f"  {YELLOW}→ cd ~/BitNet && ./llama-server -m models/ggml-model-i2_s.gguf --port 8080{RESET}")

    # NDGi
    try:
        req = urllib.request.urlopen(f"{NDGI_BASE}/ndgi/health", timeout=2)
        print(f"  NDGi proxy     {GREEN}ONLINE{RESET}  {NDGI_BASE}")
    except:
        print(f"  NDGi proxy     {YELLOW}OFFLINE{RESET} {NDGI_BASE}")

    print(f"  Workspace      {WORKSPACE_ROOT}")
    print(f"  Log dir        {LOG_DIR}\n")

# ── Path resolution ───────────────────────────────────────────────────────────
def resolve_path(raw):
    p = os.path.expanduser(raw.strip())
    return p if os.path.isabs(p) else os.path.join(WORKSPACE_ROOT, p)

# ── Fuzzy match ───────────────────────────────────────────────────────────────
def fuzzy_find(content, search):
    idx = content.find(search)
    if idx != -1:
        return idx
    def norm(t):
        return "\n".join(l.rstrip() for l in t.splitlines())
    nc, ns = norm(content), norm(search)
    idx = nc.find(ns)
    if idx != -1:
        tgt   = nc[:idx].count("\n")
        lines = content.splitlines(keepends=True)
        start = sum(len(l) for l in lines[:tgt])
        end   = sum(len(l) for l in lines[:tgt + ns.count("\n") + 1])
        return (start, end)
    return -1

# ── File editor ───────────────────────────────────────────────────────────────
def apply_all_edits(text):
    results = []

    for m in re.finditer(
            r"FILE:\s*(.+?)\n<<<<<<< CREATE\n(.*?)\n>>>>>>> END",
            text, re.DOTALL):
        path = resolve_path(m.group(1))
        content = m.group(2)
        print(f"\n{YELLOW}[CREATE]{RESET} {path}")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(content)
            print(f"{GREEN}[TRIT_POS]{RESET} written ({len(content)} chars)")
            results.append({"ok": True, "op": "create", "path": path})
        except Exception as e:
            print(f"{RED}[TRIT_NEG]{RESET} {e}")
            results.append({"ok": False, "op": "create", "path": path, "err": str(e)})

    for m in re.finditer(
            r"FILE:\s*(.+?)\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
            text, re.DOTALL):
        path    = resolve_path(m.group(1))
        search  = m.group(2)
        replace = m.group(3)
        print(f"\n{YELLOW}[REPLACE]{RESET} {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            open(path, "w").write(replace)
            print(f"{GREEN}[TRIT_POS]{RESET} created from replace block")
            results.append({"ok": True, "op": "replace", "path": path})
            continue
        orig  = open(path).read()
        match = fuzzy_find(orig, search)
        if match == -1:
            print(f"{RED}[TRIT_NEG]{RESET} search block not matched")
            results.append({"ok": False, "op": "replace", "path": path, "err": "no_match"})
            continue
        if isinstance(match, tuple):
            s, e = match
            updated = orig[:s] + replace + orig[e:]
        else:
            updated = orig.replace(search, replace, 1)
        open(path, "w").write(updated)
        print(f"{GREEN}[TRIT_POS]{RESET} patched")
        results.append({"ok": True, "op": "replace", "path": path})

    return results

# ── Engine query ──────────────────────────────────────────────────────────────
def query_engine(system, history, user_input):
    context = ""
    for t in history[-MAX_HISTORY_TURNS:]:
        context += f"<|user|>\n{t['user']}\n<|assistant|>\n{t['assistant']}\n"

    prompt = (
        f"<|system|>\n{system}\n"
        f"{context}"
        f"<|user|>\n{user_input}\n<|assistant|>\n"
    )

    payload = {
        "prompt":         prompt,
        "n_predict":      2048,
        "temperature":    0.15,
        "repeat_penalty": 1.3,
        "stop":           ["<|user|>", "<|system|>", "<|end|>", "<|im_end|>"],
        "stream":         True
    }

    sys.stdout.write(f"\n{CYAN}Aegis-PHOTNX:{RESET} ")
    sys.stdout.flush()

    accumulated = ""
    try:
        import requests
        r = requests.post(API_URL, json=payload,
                          headers={"Content-Type": "application/json"},
                          stream=True, timeout=180)
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            s = line.decode("utf-8")
            if s.startswith("data: "):
                s = s[6:]
            try:
                d   = json.loads(s)
                tok = d.get("content", "")
                accumulated += tok
                sys.stdout.write(tok)
                sys.stdout.flush()
                if d.get("stop"):
                    break
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print(f"\n{RED}[Error]{RESET} {e}")
        print(f"{YELLOW}→ Is llama-server running? cd ~/BitNet && "
              f"./llama-server -m models/ggml-model-i2_s.gguf --port 8080{RESET}\n")
        return ""

    print("\n")
    edits = apply_all_edits(accumulated)
    if edits:
        ok  = sum(1 for e in edits if e["ok"])
        bad = len(edits) - ok
        accumulated += f"\n[Session: {ok} edit(s) applied" + \
                       (f", {bad} failed" if bad else "") + "]"

    # Log to file
    _log(user_input, accumulated)
    return accumulated

# ── Logger ────────────────────────────────────────────────────────────────────
def _log(user, response):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOG_DIR, f"{ts}.md")
        with open(path, "w") as f:
            f.write(f"# {ts}\n\n**User:** {user}\n\n**Aegis:** {response[:2000]}\n")
    except:
        pass

# ── Local command handler ─────────────────────────────────────────────────────
SHELL_CMDS = ('cp ', 'mv ', 'mkdir ', 'rm ', 'touch ', 'chmod ',
              'echo ', 'git ', 'python3 ', 'pip ', 'npm ', 'cd ')

def handle_local(cmd, mcp_agent):
    c = cmd.strip()
    cl = c.lower()

    if cl in ('exit', 'quit', 'q'):
        return "exit"

    if cl == 'help':
        print(HELP_TEXT)
        return "handled"

    if cl == 'clear':
        display_splash(mcp_agent is not None)
        return "handled"

    if cl == 'status':
        show_status()
        return "handled"

    if cl == 'history':
        return "history"

    if cl in ('time', 'what time is it?', 'what time is it'):
        print(f"\n{BLUE}[Local]{RESET} {time.strftime('%A %B %d, %Y · %I:%M:%S %p')}\n")
        return "handled"

    if cl.startswith('ls') or cl.startswith('cat '):
        parts = c.split(None, 1)
        path  = resolve_path(parts[1]) if len(parts) > 1 else '.'
        try:
            if cl.startswith('ls'):
                entries = sorted(os.listdir(path))
                print("\n" + "\n".join(entries) + "\n")
            else:
                print(f"\n{DIM}" + open(path).read() + f"{RESET}\n")
        except Exception as e:
            print(f"{RED}[Error]{RESET} {e}\n")
        return "handled"

    if any(cl.startswith(p) for p in SHELL_CMDS):
        result = subprocess.run(c, shell=True, text=True, capture_output=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"{RED}{result.stderr}{RESET}")
        return "handled"

    # Oakland typo correction — pre-process before sending to engine
    if mcp_agent:
        try:
            corrected = mcp_agent.correct_typos(c)
            if corrected and corrected != c:
                print(f"{DIM}[Corrected: {corrected}]{RESET}")
                return corrected   # return corrected text to re-route to engine
        except AttributeError:
            pass   # method may not exist in all Oakland versions

    return None  # pass to engine

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    system    = load_system_prompt()
    mcp_agent = load_mcp_agent()
    display_splash(mcp_agent is not None)

    history: list = []

    while True:
        try:
            raw = input(f"{GREEN}jsosa@Aegis-Orchestrator:{RESET}~$ ").strip()
            if not raw:
                continue

            result = handle_local(raw, mcp_agent)

            if result == "exit":
                print(f"\n{DIM}[Aegis] Session closed. TRIT_POS.{RESET}\n")
                break

            if result == "history":
                for i, t in enumerate(history, 1):
                    print(f"\n{DIM}[{i}] You:{RESET}  {t['user'][:80]}")
                    print(f"{DIM}    Aegis:{RESET} {t['assistant'][:120]}...")
                print()
                continue

            if result == "handled":
                continue

            # result is either None (pass raw to engine) or corrected string
            prompt = result if result else raw

            response = query_engine(system, history, prompt)

            if response:
                history.append({"user": prompt, "assistant": response})
                if len(history) > MAX_HISTORY_TURNS:
                    history = history[-MAX_HISTORY_TURNS:]

                # Oakland suggestions if available
                if mcp_agent:
                    try:
                        resp_obj = mcp_agent.process_query(prompt)
                        if resp_obj.suggestions:
                            print(f"{DIM}Suggestions: "
                                  f"{', '.join(resp_obj.suggestions[:3])}{RESET}")
                    except:
                        pass

        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[Aegis] Use 'exit' to close cleanly.{RESET}")

if __name__ == "__main__":
    main()
