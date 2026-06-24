"""
aegis_workspace_patch.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DROP-IN PATCH for aegis_bridge.py

Adds three capabilities:
  1. WorkspaceMapper  — spatial awareness / filesystem orientation
  2. MCPChecker       — post-edit QA checker (syntax + import + run)
  3. Tool dispatcher  — wires both into the MoE bash-tool dispatch loop

INTEGRATION: paste the classes into aegis_bridge.py, then replace
your existing _dispatch_tool() block with the one at the bottom.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import ast
import subprocess
import importlib.util
from pathlib import Path


# ══════════════════════════════════════════════════════════════════
#  1. WORKSPACE MAPPER
#     Gives Aegis a real tree-view of any directory it's working in.
#     Called automatically at session start and on-demand via tool.
# ══════════════════════════════════════════════════════════════════

class WorkspaceMapper:
    """
    Solves the traverse-and-find path problem dynamically.
    Generates a localized system structure summary fed directly into
    the OODA context engine — no broken external tools required.
    """

    SOURCE_EXTS = {'.py', '.md', '.sh', '.json', '.txt', '.js', '.ts',
                   '.yaml', '.yml', '.toml', '.cfg', '.ini', '.env'}

    IGNORED_DIRS = {'.git', '__pycache__', 'node_modules', 'venv',
                    'build', 'logs', '.mypy_cache', '.pytest_cache',
                    'dist', 'eggs', '.eggs', '.tox'}

    def __init__(self, root_dir: str, max_file_size_kb: int = 100):
        self.root_dir = os.path.abspath(root_dir)
        self.max_file_size = max_file_size_kb * 1024

    # ── Tree view ────────────────────────────────────────────────
    def scan_workspace_tree(self) -> str:
        """Accurate text layout of the directory structure."""
        lines = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = sorted(d for d in dirs if d not in self.IGNORED_DIRS)
            level  = root.replace(self.root_dir, '').count(os.sep)
            indent = '  ' * level
            folder = os.path.basename(root)

            if root == self.root_dir:
                lines.append(f"[WORKSPACE ROOT: {folder}]  {self.root_dir}")
            else:
                lines.append(f"{indent}├── DIR  /{folder}")

            sub = '  ' * (level + 1)
            for f in sorted(files):
                ext = os.path.splitext(f)[1].lower()
                if ext in self.SOURCE_EXTS:
                    fpath = os.path.join(root, f)
                    size  = os.path.getsize(fpath)
                    lines.append(f"{sub}└── {f}  ({size // 1024}KB)")

        return "\n".join(lines) if lines else "[EMPTY WORKSPACE]"

    # ── Keyword search ────────────────────────────────────────────
    def search_workspace_keywords(self, query_string: str) -> list[str]:
        """Files containing any of the query keywords."""
        keywords = [w.strip().lower() for w in query_string.split() if len(w) > 3]
        if not keywords:
            return []

        matches = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            for fname in files:
                if os.path.splitext(fname)[1].lower() not in self.SOURCE_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    if os.path.getsize(fpath) > self.max_file_size:
                        continue
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                    if any(kw in content for kw in keywords):
                        matches.append(fpath)
                except Exception:
                    continue
        return matches

    # ── Find by extension ─────────────────────────────────────────
    def find_by_extension(self, ext: str) -> list[str]:
        """Return all files with the given extension (e.g. '.md')."""
        ext = ext if ext.startswith('.') else f'.{ext}'
        results = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            for f in files:
                if f.lower().endswith(ext):
                    results.append(os.path.join(root, f))
        return results

    # ── OODA context block ────────────────────────────────────────
    def build_ooda_context(self) -> str:
        """One-shot context string to prepend to every Aegis system prompt."""
        tree = self.scan_workspace_tree()
        return (
            f"[AEGIS SPATIAL ORIENTATION]\n"
            f"Root: {self.root_dir}\n"
            f"{'─'*60}\n"
            f"{tree}\n"
            f"{'─'*60}\n"
            f"RULE: Never hallucinate file paths. Use bash or workspace tools to verify.\n"
        )


# ══════════════════════════════════════════════════════════════════
#  2. MCP CHECKER
#     Post-edit QA gate. Runs after Aegis writes/modifies a file.
#     Checks: syntax, imports, optional test run, optional lint.
# ══════════════════════════════════════════════════════════════════

class MCPChecker:
    """
    MCP = Modified-Code Probe.
    Automated QA gate that Aegis calls after completing a code edit.
    Returns a structured TRIT result (POS / ZERO / NEG) for the OODA loop.
    """

    def __init__(self, venv_python: str = None):
        # Use venv python if supplied, otherwise system python3
        self.python = venv_python or "python3"

    # ── Entry point ───────────────────────────────────────────────
    def check_file(self, filepath: str, run_tests: bool = False) -> dict:
        """
        Full QA pass on a single file.
        Returns:
          {
            trit: "TRIT_POS" | "TRIT_ZERO" | "TRIT_NEG",
            checks: { syntax, imports, lint, tests },
            errors: [str],
            summary: str
          }
        """
        result = {
            "trit":    "TRIT_POS",
            "checks":  {},
            "errors":  [],
            "summary": ""
        }

        if not os.path.isfile(filepath):
            result["trit"]    = "TRIT_NEG"
            result["errors"]  = [f"File not found: {filepath}"]
            result["summary"] = "❌ File does not exist."
            return result

        ext = Path(filepath).suffix.lower()

        # ── Python checks ─────────────────────────────────────────
        if ext == '.py':
            self._check_py_syntax(filepath, result)
            self._check_py_imports(filepath, result)
            self._check_py_lint(filepath, result)
            if run_tests:
                self._run_pytest(filepath, result)

        # ── Shell checks ──────────────────────────────────────────
        elif ext == '.sh':
            self._check_sh_syntax(filepath, result)

        # ── JSON checks ───────────────────────────────────────────
        elif ext == '.json':
            self._check_json(filepath, result)

        # ── Markdown (basic) ──────────────────────────────────────
        elif ext == '.md':
            result["checks"]["markdown"] = "PASS (no syntax check)"

        else:
            result["checks"]["generic"] = f"PASS (no checker for {ext})"

        # ── Final trit scoring ────────────────────────────────────
        if result["errors"]:
            failed = [k for k, v in result["checks"].items() if "FAIL" in str(v)]
            result["trit"] = "TRIT_NEG" if failed else "TRIT_ZERO"

        result["summary"] = self._build_summary(filepath, result)
        return result

    # ── Python syntax ─────────────────────────────────────────────
    def _check_py_syntax(self, fp: str, result: dict):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            result["checks"]["syntax"] = "PASS"
        except SyntaxError as e:
            result["checks"]["syntax"] = f"FAIL — line {e.lineno}: {e.msg}"
            result["errors"].append(f"SyntaxError: {e}")

    # ── Python imports (dry-run) ──────────────────────────────────
    def _check_py_imports(self, fp: str, result: dict):
        cmd = [self.python, "-c",
               f"import ast, sys; "
               f"src=open('{fp}').read(); "
               f"tree=ast.parse(src); "
               f"[print(n.names[0].name if hasattr(n,'names') else n.module) "
               f" for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            modules = [m for m in r.stdout.strip().splitlines() if m]
            missing = []
            for mod in modules:
                top = mod.split('.')[0]
                if importlib.util.find_spec(top) is None:
                    missing.append(top)
            if missing:
                result["checks"]["imports"] = f"FAIL — missing: {missing}"
                result["errors"].append(f"Missing modules: {missing}")
            else:
                result["checks"]["imports"] = f"PASS ({len(modules)} imports OK)"
        except Exception as e:
            result["checks"]["imports"] = f"ZERO — could not verify: {e}"

    # ── Pylint (non-blocking, score only) ─────────────────────────
    def _check_py_lint(self, fp: str, result: dict):
        r = subprocess.run(
            [self.python, "-m", "pylint", "--score=yes", "--errors-only", fp],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode == 0:
            result["checks"]["lint"] = "PASS (no errors)"
        else:
            # Extract just error lines
            errs = [l for l in r.stdout.splitlines() if ': E' in l]
            if errs:
                result["checks"]["lint"] = f"FAIL — {len(errs)} error(s)"
                result["errors"].extend(errs[:5])  # cap at 5
            else:
                result["checks"]["lint"] = "PASS (warnings only)"

    # ── Pytest (optional) ─────────────────────────────────────────
    def _run_pytest(self, fp: str, result: dict):
        test_dir = str(Path(fp).parent)
        r = subprocess.run(
            [self.python, "-m", "pytest", test_dir, "-x", "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            result["checks"]["tests"] = "PASS"
        else:
            result["checks"]["tests"] = "FAIL"
            result["errors"].append(r.stdout[-800:])  # last 800 chars

    # ── Shell syntax ──────────────────────────────────────────────
    def _check_sh_syntax(self, fp: str, result: dict):
        r = subprocess.run(["bash", "-n", fp], capture_output=True, text=True)
        if r.returncode == 0:
            result["checks"]["syntax"] = "PASS"
        else:
            result["checks"]["syntax"] = f"FAIL — {r.stderr.strip()}"
            result["errors"].append(r.stderr.strip())

    # ── JSON validity ─────────────────────────────────────────────
    def _check_json(self, fp: str, result: dict):
        import json
        try:
            with open(fp) as f:
                json.load(f)
            result["checks"]["json"] = "PASS"
        except json.JSONDecodeError as e:
            result["checks"]["json"] = f"FAIL — {e}"
            result["errors"].append(str(e))

    # ── Summary string ────────────────────────────────────────────
    def _build_summary(self, fp: str, result: dict) -> str:
        trit  = result["trit"]
        icon  = {"TRIT_POS": "✅", "TRIT_ZERO": "⚠️", "TRIT_NEG": "❌"}[trit]
        lines = [f"{icon} MCP CHECK — {os.path.basename(fp)} — {trit}"]
        for check, status in result["checks"].items():
            lines.append(f"  {check:12s}: {status}")
        if result["errors"]:
            lines.append("  ERRORS:")
            for e in result["errors"][:3]:
                lines.append(f"    • {e}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  3. TOOL DISPATCHER — wire into existing aegis_bridge.py
#
#  In your bridge, find the _dispatch_tool() function (or wherever
#  you handle tool_use blocks from the model) and replace/extend it
#  with the block below.
# ══════════════════════════════════════════════════════════════════

# Singletons — instantiate once at module load
_mapper  = None
_checker = MCPChecker(venv_python="python3")


def get_mapper(path: str = None) -> WorkspaceMapper:
    """Return or reinitialise the WorkspaceMapper for a given path."""
    global _mapper
    default = os.environ.get("AEGIS_WORKSPACE", "/home/jsosa/workspace")
    _mapper = WorkspaceMapper(path or default)
    return _mapper


def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """
    Extended tool dispatcher for aegis_bridge.py.
    Drop this into your existing _dispatch_tool() or call it from there.

    Tools handled:
      bash              — run any shell command
      workspace_tree    — scan and return directory tree
      workspace_search  — keyword search across workspace
      workspace_find    — find files by extension
      mcp_check         — run QA checker on a file
    """

    # ── bash ──────────────────────────────────────────────────────
    if tool_name == "bash":
        command = tool_input.get("command", "")
        if not command:
            return "[ERROR] No command provided."
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, cwd=os.environ.get("AEGIS_WORKSPACE", "/home/jsosa")
            )
            out = (r.stdout + r.stderr).strip()
            return out[:4000] if out else "(command returned no output)"
        except subprocess.TimeoutExpired:
            return "[TIMEOUT] Command exceeded 30s limit."
        except Exception as e:
            return f"[ERROR] bash: {e}"

    # ── workspace_tree ────────────────────────────────────────────
    elif tool_name == "workspace_tree":
        path = tool_input.get("path", None)
        mapper = get_mapper(path)
        return mapper.scan_workspace_tree()

    # ── workspace_search ──────────────────────────────────────────
    elif tool_name == "workspace_search":
        query = tool_input.get("query", "")
        path  = tool_input.get("path", None)
        mapper = get_mapper(path)
        results = mapper.search_workspace_keywords(query)
        if not results:
            return f"[workspace_search] No files matched: '{query}'"
        return "\n".join(results)

    # ── workspace_find ────────────────────────────────────────────
    elif tool_name == "workspace_find":
        ext    = tool_input.get("extension", ".md")
        path   = tool_input.get("path", None)
        mapper = get_mapper(path)
        results = mapper.find_by_extension(ext)
        if not results:
            return f"[workspace_find] No *{ext} files found."
        return "\n".join(results)

    # ── mcp_check ────────────────────────────────────────────────
    elif tool_name == "mcp_check":
        filepath  = tool_input.get("filepath", "")
        run_tests = tool_input.get("run_tests", False)
        if not filepath:
            return "[ERROR] mcp_check requires a 'filepath' argument."
        result = _checker.check_file(filepath, run_tests=run_tests)
        return result["summary"]

    else:
        return f"[ERROR] Unknown tool: {tool_name}"


# ══════════════════════════════════════════════════════════════════
#  4. TOOL SCHEMA — paste this into your AEGIS_TOOLS list
# ══════════════════════════════════════════════════════════════════

WORKSPACE_TOOLS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command on the local filesystem. "
            "Use for find, ls, cat, grep, mkdir, cp, mv, etc. "
            "ALWAYS use this to verify real filesystem state — never guess."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "workspace_tree",
        "description": (
            "Return a formatted tree view of a workspace directory. "
            "Call this at the start of any coding task to orient yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to scan (default: AEGIS_WORKSPACE)"}
            }
        }
    },
    {
        "name": "workspace_search",
        "description": "Search files in a workspace directory by keyword content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
                "path":  {"type": "string", "description": "Directory to search (optional)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "workspace_find",
        "description": "Find all files with a given extension (e.g. '.md', '.py') in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "extension": {"type": "string", "description": "File extension to find, e.g. '.md'"},
                "path":      {"type": "string", "description": "Directory to search (optional)"}
            },
            "required": ["extension"]
        }
    },
    {
        "name": "mcp_check",
        "description": (
            "Run automated QA checks on a file after editing. "
            "Checks syntax, imports, lint (Python), shell validity, JSON. "
            "ALWAYS call this after writing or modifying any code file. "
            "Returns TRIT_POS / TRIT_ZERO / TRIT_NEG."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath":  {"type": "string", "description": "Absolute path to the file to check"},
                "run_tests": {"type": "boolean", "description": "Also run pytest if True (default false)"}
            },
            "required": ["filepath"]
        }
    }
]


# ══════════════════════════════════════════════════════════════════
#  5. SESSION INIT — call this once when Aegis starts
#     Returns the orientation block to prepend to system prompt
# ══════════════════════════════════════════════════════════════════

def aegis_session_init(workspace_path: str = None) -> str:
    """
    Call at session start. Returns an orientation block to prepend
    to the Aegis system prompt so the first OODA cycle has full context.

    Usage in aegis_bridge.py:
        SYSTEM_PROMPT = aegis_session_init(REPO_ROOT) + BASE_SYSTEM_PROMPT
    """
    path   = workspace_path or os.environ.get("AEGIS_WORKSPACE", "/home/jsosa/workspace")
    mapper = get_mapper(path)
    return mapper.build_ooda_context()


# ══════════════════════════════════════════════════════════════════
#  QUICK SELF-TEST  (run: python3 aegis_workspace_patch.py)
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    test_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/workspace")

    print("=" * 60)
    print("WORKSPACE MAPPER SELF-TEST")
    print("=" * 60)
    mapper = WorkspaceMapper(test_path)
    print(mapper.scan_workspace_tree())

    print("\n" + "=" * 60)
    print("MCP CHECKER SELF-TEST")
    print("=" * 60)
    checker = MCPChecker()
    # Test on this file itself
    result = checker.check_file(__file__)
    print(result["summary"])

    print("\n" + "=" * 60)
    print("TOOL DISPATCH SELF-TEST")
    print("=" * 60)
    print(dispatch_tool("workspace_find", {"extension": ".py", "path": test_path}))
    print(dispatch_tool("bash", {"command": "echo 'bash tool OK'"}))
