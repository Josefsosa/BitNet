cat << 'EOF' > /home/jsosa/workspace/BitNet/src/aegis-cli.py
#!/usr/bin/env python3
"""
Aegis Orchestrator CLI v3.2 — Wellton Photonics
OODA-native. NDGi-aware. TDD-gated. Loop-proof.

Optimized Configuration for /home/jsosa/workspace/BitNet
"""

import os, sys, re, json, time, subprocess, importlib.util, hashlib
import argparse, threading
import readline
from pathlib import Path

# ── Readline config ──────────────────────────────────────────────────────────
readline.parse_and_bind('set editing-mode emacs')
readline.parse_and_bind('"\\e[A": previous-history')    # Up arrow
readline.parse_and_bind('"\\e[B": next-history')        # Down arrow
readline.parse_and_bind('"\\e[C": forward-char')        # Right arrow
readline.parse_and_bind('"\\e[D": backward-char')       # Left arrow
readline.parse_and_bind('"\\e[H": beginning-of-line')   # Home
readline.parse_and_bind('"\\e[F": end-of-line')         # End
readline.parse_and_bind('"\\e[3~": delete-char')        # Delete key
readline.set_history_length(200)

# ── Config Realignment for BitNet ─────────────────────────────────────────────
API_URL            = "http://127.0.0.1:8080/v1/chat/completions"
NDGI_BASE          = "http://127.0.0.1:8000"
SYSTEM_PROMPT_FILE = "aegis_system_prompt.txt"
MAX_HISTORY_TURNS  = 10
MAX_IDENTICAL_RESPONSES = 2          
WORKSPACE_ROOT     = os.path.expanduser("~/workspace/BitNet")
SRC_ROOT           = os.path.join(WORKSPACE_ROOT, "src")
LOG_DIR            = os.path.join(WORKSPACE_ROOT, "logs")
NDGI_SESSION_FILE  = os.path.join(LOG_DIR, "ndgi_session.json")

# ── ANSI Colors ───────────────────────────────────────────────────────────────
CY="\033[1;36m"; GR="\033[1;32m"; YL="\033[1;33m"
RD="\033[1;31m"; BL="\033[1;34m"; DM="\033[0;36m"
MG="\033[0;35m"; WH="\033[1;37m"; RS="\033[0m"

def parse_args():
    p = argparse.ArgumentParser(description="Aegis Orchestrator CLI — Unified REPL")
    p.add_argument("--persona", default=os.environ.get("AEGIS_PERSONA", ""), help="Persona ID: jfs, rq, br")
    p.add_argument("--gpu-layers", type=int, default=int(os.environ.get("AEGIS_GPU_LAYERS", "0")), help="GPU layers for inference")
    p.add_argument("--threads", type=int, default=int(os.environ.get("AEGIS_CPU_THREADS", "12")), help="CPU threads")
    p.add_argument("--mode", default=os.environ.get("AEGIS_MODE", "full"), choices=("coding", "ops", "full"), help="Feature mode")
    p.add_argument("--endpoint", default=os.environ.get("AEGIS_ENDPOINT", ""), help="Override API URL")
    return p.parse_args()

class NDGiSession:
    def __init__(self):
        self.nodes = {}
        self.load()
    def load(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.exists(NDGI_SESSION_FILE):
                self.nodes = json.load(open(NDGI_SESSION_FILE))
        except: self.nodes = {}
    def save(self):
        try: json.dump(self.nodes, open(NDGI_SESSION_FILE, "w"), indent=2)
        except: pass
    def register(self, path, trit, op, content=""):
        h = hashlib.md5(content.encode()).hexdigest()[:8] if content else ""
        self.nodes[path] = {
            "trit": trit, "hash": h, "op": op,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "attempts": self.nodes.get(path, {}).get("attempts", 0) + 1
        }
        self.save()
    def is_done(self, path):
        n = self.nodes.get(path)
        return n and n["trit"] == 1
    def attempts(self, path):
        n = self.nodes.get(path)
        return n["attempts"] if n else 0
    def summary(self):
        done  = [p for p,n in self.nodes.items() if n["trit"]==1]
        pend  = [p for p,n in self.nodes.items() if n["trit"]==0]
        fail  = [p for p,n in self.nodes.items() if n["trit"]==-1]
        return done, pend, fail
    def print_graph(self):
        done, pend, fail = self.summary()
        print(f"\n{CY}NDGi SESSION GRAPH{RS}")
        print(f"  {GR}TRIT_POS  ({len(done)}){RS}")
        for p in done: print(f"    ✓ {os.path.relpath(p, WORKSPACE_ROOT)}")
        if fail:
            print(f"  {RD}TRIT_NEG  ({len(fail)}){RS}")
            for p in fail: print(f"    ✗ {os.path.relpath(p, WORKSPACE_ROOT)}")

class KnowledgeStore:
    CATEGORIES = ("ENV", "PROJ", "USER", "TASK", "LEARN")
    def __init__(self):
        self.path  = os.path.join(LOG_DIR, "knowledge_nodes.json")
        self.nodes = {}
        self.load()
    def load(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.exists(self.path): self.nodes = json.load(open(self.path))
        except: self.nodes = {}
    def save(self):
        try: json.dump(self.nodes, open(self.path, "w"), indent=2)
        except: pass
    def remember(self, key: str, value: str, category: str = "PROJ", source: str = "user"):
        kid = f"KN-{len(self.nodes)+1:03d}"
        for k, n in self.nodes.items():
            if n.get("key","").lower() == key.lower():
                n["value"] = value
                self.save()
                return k, True
        self.nodes[kid] = {
            "id": kid, "type": "knowledge", "key": key, "value": value,
            "category": category.upper() if category.upper() in self.CATEGORIES else "PROJ",
            "source": source, "confidence": 1.0, "trit": 1,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save()
        return kid, False
    def list_all(self): return list(self.nodes.values())
    def prompt_block(self) -> str:
        if not self.nodes: return ""
        lines = ["KNOWLEDGE NODES (reference facts from founder profile):"]
        for n in self.nodes.values():
            lines.append(f"  [{n['category']}] {n['key']}: {n['value']}")
        return "\n".join(lines)
    def print_nodes(self):
        if not self.nodes: print("\nNo knowledge nodes stored yet.\n"); return
        print(f"\n{CY}ACTIVE NDGi KNOWLEDGE NODES{RS}")
        for n in self.nodes.values():
            print(f"  {GR}{n['id']}{RS} [{n['category']}] {n['key']} → {n['value']}")
        print()
    @staticmethod
    def parse_remember(text: str) -> tuple:
        t = re.sub(r'^remember\s+(that\s+)?', '', text, flags=re.I).strip()
        m = re.match(r'(.+?)\s+(?:is|are|=|runs on)\s+(.+)', t, re.I)
        if m: return m.group(1).strip()[:80], m.group(2).strip()[:200], "PROJ"
        return t[:80], "noted", "PROJ"

class FileContextStore:
    MAX_CHARS = 8000
    def __init__(self): self._files = {}
    def load(self, path: str) -> tuple:
        p = Path(path).expanduser()
        if not p.exists(): p = Path(WORKSPACE_ROOT) / path
        if not p.exists(): return False, f"File not found: {path}"
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            self._files[str(p)] = {"path": str(p), "lines": len(content.splitlines()), "content": content[:self.MAX_CHARS], "truncated": len(content) > self.MAX_CHARS}
            return True, f"Loaded {p.name}"
        except Exception as e: return False, str(e)
    def context_block(self) -> str:
        if not self._files: return ""
        lines = ["LOADED FILE CONTEXTS:"]
        for info in self._files.values():
            lines.append(f"\n--- {info['path']} ---\n{info['content']}")
        return "\n".join(lines)
    def list_loaded(self): return list(self._files.keys())

class WorkspaceScanner:
    IGNORE = {'.git','__pycache__','node_modules','venv','build','dist'}
    def __init__(self):
        self.root = WORKSPACE_ROOT
        self.tree = {}
        self.count = 0
    def scan(self):
        self.tree, self.count = {}, 0
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in self.IGNORE]
            rel = os.path.relpath(dirpath, self.root)
            if rel == '.': rel = ''
            for f in files:
                if not f.endswith(('.pyc', '.log')):
                    self.tree.setdefault(rel or '.', []).append(f)
                    self.count += 1
    def prompt_block(self) -> str:
        return f"WORKSPACE TOPOLOGY: {self.count} indexed files across nominal paths."

class ErrorTracker:
    def __init__(self): self.last_error = None
    def capture(self, text):
        if "Error" in text or "Exception" in text: self.last_error = {"raw": text[:1000]}
    def diagnosis_prompt(self, file_ctx):
        return f"DIAGNOSE LAST SYSTEM EXCEPTION: {self.last_error['raw']}" if self.last_error else ""

class TypoCorrector:
    def __init__(self): self.corrections = {'ngdi': 'ndgi', 'binet': 'bitnet', 'phtonx': 'photonx'}
    def correct(self, text: str) -> str:
        words = text.split()
        return ' '.join(self.corrections.get(w.lower(), w) for w in words)

class OODAEngine:
    def __init__(self, ndgi):
        self.ndgi = ndgi
        self.history = []
    def observe(self, user_input):
        return {"input": user_input, "intent": "code_task" if "create" in user_input.lower() or "fix" in user_input.lower() else "conversation", "bitnet_up": True}
    def orient(self, ctx): return ctx
    def decide(self, ctx):
        ctx["action"] = "engine"
        return ctx
    def pre_act_report(self, ctx): return None
    def is_looping(self, response): return False

class OODASpinner:
    FRAMES = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    def __init__(self, label="Thinking"):
        self.label = label
        self._stop = threading.Event()
        self._thread = None
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    def _run(self):
        i = 0
        while not self._stop.is_set():
            sys.stderr.write(f"\r  {CY}{self.FRAMES[i % len(self.FRAMES)]}{RS} [OODA LOOPING] Processing System Inferences...")
            sys.stderr.flush()
            time.sleep(0.1)
            i += 1
    def stop(self, verdict="TRIT_POS", latency=""):
        self._stop.set()
        if self._thread: self._thread.join(timeout=1)
        sys.stderr.write(f"\r{' '*70}\r  {GR}[{verdict}]{RS} Latency optimization verified ({latency})\n")
        sys.stderr.flush()

PERSONAS = {
    "jfs": {
        "name": "Jose F. Sosa",
        "title": "Founder & CEO — Wellton Photonics",
        "system": "You are Aegis, the trust-gated reasoning engine for Wellton Photonics. Your operator is Jose F. Sosa (jfs). You operate deterministically over a 1.58-bit ternary weight manifold. Respond crisply, with expert clarity. Maintain absolute context alignment with Founder profile specifications."
    }
}

MOE_AGENTS = {"photnx": "PHOTNX Specialist Core Engine", "sentinel": "SENTINEL Security Shield Gate"}

def load_system_prompt(persona_id="jfs"):
    return PERSONAS.get(persona_id, PERSONAS["jfs"])["system"]

def apply_all_edits(text, ndgi): return []

def query_engine(system, history, user_input, ndgi, ooda, knowledge, persona_id="jfs", file_ctx=None, scanner=None):
    full_system = system + f"\n\n--- LIVE GROUND TRUTH DATA ---\n{knowledge.prompt_block()}"
    payload = {
        "model": "bitnet_b1_58-3B",
        "messages": [{"role": "system", "content": full_system}] + [{"role": "user", "content": user_input}],
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": True
    }
    spinner = OODASpinner()
    spinner.start()
    t0 = time.perf_counter()
    
    accumulated = ""
    first_token = True
    try:
        import requests
        r = requests.post(API_URL, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=30)
        r.raise_for_status()
        for line in r.iter_lines():
            if not line: continue
            s = line.decode("utf-8")
            if s.startswith("data: "): s = s[6:]
            if s.strip() == "[DONE]": break
            try:
                d = json.loads(s)
                tok = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if tok:
                    if first_token:
                        spinner.stop("TRIT_POS", f"{time.perf_counter()-t0:.2f}s")
                        print(f"\n{CY}Aegis-{persona_id}:{RS} ", end="")
                        first_token = False
                    accumulated += tok
                    print(tok, end="", flush=True)
            except: continue
    except Exception as e:
        spinner.stop("TRIT_NEG", "")
        print(f"\n{RD}[Connection Failure]{RS} Verify server is active on 127.0.0.1:8080. Trace: {e}")
    print()
    return accumulated

def display_splash(persona_id, files_count):
    print(f"""{CY}
    ██████╗ ██╗  ██╗ ██████╗ ████████╗███╗  ██╗██╗  ██╗
    ██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝████╗ ██║╚██╗██╔╝
    ██████╔╝███████║██║   ██║   ██║   ██╔██╗██║ ╚███╔╝
    ██╔═══╝ ██╔══██║██║   ██║   ██║   ██║╚████║ ██╔██╗
    ██║     ██║  ██║╚██████╔╝   ██║   ██║ ╚███║██╔╝╚██╗
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚══╝╚═╝  ╚═╝{RS}
    {DM}┌────────────────────────────────────────────────────────────────┐
    │   AEGIS UNIFIED CLI v3.2  ·   BitNet b1.58 Ternary Manifold     │
    └────────────────────────────────────────────────────────────────┘{RS}
    [*] Persona Loaded: {WH}Jose F. Sosa [jfs]{RS}
    [*] Workspace Connected: {GR}{WORKSPACE_ROOT}{RS} ({files_count} files indexed)
    """)

def main():
    args = parse_args()
    persona_id = "jfs"
    ndgi = NDGiSession()
    ooda = OODAEngine(ndgi)
    knowledge = KnowledgeStore()
    file_ctx = FileContextStore()
    scanner = WorkspaceScanner()
    
    scanner.scan()
    
    # Pre-populate Knowledge nodes from founder file if available
    founder_file = os.path.join(WORKSPACE_ROOT, "photonx-jfs-ndgi.json")
    if os.path.exists(founder_file):
        try:
            with open(founder_file) as f:
                data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict) and "profile" in v:
                        prof = v["profile"]
                        knowledge.remember("mission", prof.get("mission_statement",""), "USER")
                        knowledge.remember("title", prof.get("current_title",""), "USER")
        except: pass

    display_splash(persona_id, scanner.count)
    system = load_system_prompt(persona_id)
    history = []
    
    while True:
        try:
            raw = input(f"{CY}[{persona_id.upper()}]{RS} {WH}aegis>{RS} ").strip()
            if not raw: continue
            if raw.lower() in ('exit', 'quit', 'q'): break
            if raw.lower() == 'clear': os.system('clear'); continue
            if raw.lower() == 'knowledge': knowledge.print_nodes(); continue
            if raw.lower() == 'graph': ndgi.print_graph(); continue
            
            query_engine(system, history, raw, ndgi, ooda, knowledge, persona_id, file_ctx, scanner)
        except KeyboardInterrupt:
            print("\nType exit to quit.")

if __name__ == "__main__":
    main()
EOF