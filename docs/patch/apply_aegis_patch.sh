#!/bin/bash
# ==============================================================================
# Aegis Workspace + MCP Checker — Self-Applying Patch v1.0
# Wellton Photonics | NDGi Core Pipeline
# ==============================================================================
# USAGE:  bash apply_aegis_patch.sh
# DOES:
#   1. Finds your BitNet workspace automatically
#   2. Backs up every file it touches  (.bak)
#   3. Drops aegis_workspace_patch.py into the right folder
#   4. Patches run_inference_server.py to load the workspace tools
#   5. Patches aegis.sh to inject tree orientation into system prompt
#   6. Runs a self-test so you can see it working before committing
# ==============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'; BLU='\033[0;34m'; NC='\033[0m'
trit_pos() { echo -e "${GRN}[TRIT_POS] $1${NC}"; }
trit_neg() { echo -e "${RED}[TRIT_NEG] $1${NC}"; }
trit_zer() { echo -e "${YLW}[TRIT_ZERO] $1${NC}"; }
info()     { echo -e "${BLU}[*] $1${NC}"; }

echo "================================================================"
echo " Aegis Workspace + MCP Checker — Patch Installer"
echo "================================================================"

# ── Step 1: Locate BitNet root ────────────────────────────────────────────────
info "Locating BitNet workspace..."
BITNET_ROOT=""
for candidate in \
    "/home/jsosa/workspace/BitNet" \
    "$HOME/workspace/BitNet" \
    "$HOME/BitNet"; do
    if [ -d "$candidate" ]; then
        BITNET_ROOT="$candidate"
        break
    fi
done

if [ -z "$BITNET_ROOT" ]; then
    trit_neg "Could not find BitNet root. Searching..."
    BITNET_ROOT=$(find "$HOME" -maxdepth 4 -name "run_inference_server.py" \
                  -not -path "*/.*" 2>/dev/null | head -1 | xargs dirname || true)
fi

if [ -z "$BITNET_ROOT" ]; then
    trit_neg "BitNet root not found. Set BITNET_ROOT manually and re-run."
    exit 1
fi
trit_pos "BitNet root: $BITNET_ROOT"

# ── Step 2: Locate src/ (where aegis.sh lives) ───────────────────────────────
SRC_DIR=""
for candidate in "$BITNET_ROOT/src" "$BITNET_ROOT/utils" "$BITNET_ROOT"; do
    if [ -f "$candidate/aegis.sh" ]; then
        SRC_DIR="$candidate"
        break
    fi
done

if [ -z "$SRC_DIR" ]; then
    SRC_DIR="$BITNET_ROOT/src"
    mkdir -p "$SRC_DIR"
    trit_zer "aegis.sh not found — using $SRC_DIR as default src dir"
else
    trit_pos "Src dir: $SRC_DIR"
fi

PATCH_FILE="$SRC_DIR/aegis_workspace_patch.py"
INFERENCE_SERVER="$BITNET_ROOT/run_inference_server.py"
AEGIS_SH="$SRC_DIR/aegis.sh"

# ── Step 3: Backup existing files ────────────────────────────────────────────
info "Backing up existing files..."
[ -f "$INFERENCE_SERVER" ] && cp "$INFERENCE_SERVER" "${INFERENCE_SERVER}.bak" \
    && trit_pos "Backed up run_inference_server.py"
[ -f "$AEGIS_SH" ] && cp "$AEGIS_SH" "${AEGIS_SH}.bak" \
    && trit_pos "Backed up aegis.sh"

# ── Step 4: Write aegis_workspace_patch.py ───────────────────────────────────
info "Writing aegis_workspace_patch.py to $SRC_DIR ..."
cat > "$PATCH_FILE" << 'PYEOF'
"""
aegis_workspace_patch.py
Wellton Photonics | Aegis MoE Local Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provides:
  WorkspaceMapper  — real filesystem tree + search
  MCPChecker       — post-edit QA gate (syntax/imports/lint)
  dispatch_tool()  — unified tool router for aegis_bridge
  WORKSPACE_TOOLS  — tool schema list to merge into AEGIS_TOOLS
  aegis_session_init() — orientation block for system prompt
"""

import os, ast, subprocess, importlib.util, json
from pathlib import Path


# ══════════════════════════════════════════════════════════════════
#  WORKSPACE MAPPER
# ══════════════════════════════════════════════════════════════════
class WorkspaceMapper:
    SOURCE_EXTS = {'.py','.md','.sh','.json','.txt','.js','.ts',
                   '.yaml','.yml','.toml','.cfg','.ini','.env'}
    IGNORED_DIRS = {'.git','__pycache__','node_modules','venv',
                    'build','logs','.mypy_cache','dist','.tox'}

    def __init__(self, root_dir: str, max_file_size_kb: int = 100):
        self.root_dir = os.path.abspath(root_dir)
        self.max_file_size = max_file_size_kb * 1024

    def scan_workspace_tree(self) -> str:
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
                if os.path.splitext(f)[1].lower() in self.SOURCE_EXTS:
                    fpath = os.path.join(root, f)
                    kb = os.path.getsize(fpath) // 1024
                    lines.append(f"{sub}└── {f}  ({kb}KB)")
        return "\n".join(lines) if lines else "[EMPTY WORKSPACE]"

    def search_workspace_keywords(self, query: str) -> list:
        keywords = [w.strip().lower() for w in query.split() if len(w) > 3]
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
                    content = open(fpath, 'r', encoding='utf-8', errors='ignore').read().lower()
                    if any(kw in content for kw in keywords):
                        matches.append(fpath)
                except Exception:
                    continue
        return matches

    def find_by_extension(self, ext: str) -> list:
        ext = ext if ext.startswith('.') else f'.{ext}'
        results = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            for f in files:
                if f.lower().endswith(ext):
                    results.append(os.path.join(root, f))
        return results

    def build_ooda_context(self) -> str:
        tree = self.scan_workspace_tree()
        return (
            f"[AEGIS SPATIAL ORIENTATION]\n"
            f"Root: {self.root_dir}\n"
            f"{'─'*60}\n{tree}\n{'─'*60}\n"
            f"RULE: NEVER hallucinate file paths. Use bash or workspace tools.\n"
            f"RULE: After ANY file edit, call mcp_check on that file.\n"
        )


# ══════════════════════════════════════════════════════════════════
#  MCP CHECKER
# ══════════════════════════════════════════════════════════════════
class MCPChecker:
    def __init__(self, python: str = "python3"):
        self.python = python

    def check_file(self, filepath: str, run_tests: bool = False) -> dict:
        result = {"trit": "TRIT_POS", "checks": {}, "errors": [], "summary": ""}
        if not os.path.isfile(filepath):
            result.update(trit="TRIT_NEG",
                          errors=[f"File not found: {filepath}"],
                          summary=f"❌ File not found: {filepath}")
            return result

        ext = Path(filepath).suffix.lower()
        if ext == '.py':
            self._syntax(filepath, result)
            self._imports(filepath, result)
            self._lint(filepath, result)
            if run_tests:
                self._pytest(filepath, result)
        elif ext == '.sh':
            self._sh(filepath, result)
        elif ext == '.json':
            self._json(filepath, result)
        else:
            result["checks"]["generic"] = f"PASS (no checker for {ext})"

        failed = [k for k, v in result["checks"].items() if "FAIL" in str(v)]
        if failed:
            result["trit"] = "TRIT_NEG"
        elif result["errors"]:
            result["trit"] = "TRIT_ZERO"

        result["summary"] = self._summary(filepath, result)
        return result

    def _syntax(self, fp, r):
        try:
            ast.parse(open(fp).read())
            r["checks"]["syntax"] = "PASS"
        except SyntaxError as e:
            r["checks"]["syntax"] = f"FAIL — line {e.lineno}: {e.msg}"
            r["errors"].append(str(e))

    def _imports(self, fp, r):
        try:
            tree = ast.parse(open(fp).read())
            mods = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    mods += [a.name.split('.')[0] for a in n.names]
                elif isinstance(n, ast.ImportFrom) and n.module:
                    mods.append(n.module.split('.')[0])
            missing = [m for m in set(mods) if importlib.util.find_spec(m) is None]
            if missing:
                r["checks"]["imports"] = f"FAIL — missing: {missing}"
                r["errors"].append(f"Missing: {missing}")
            else:
                r["checks"]["imports"] = f"PASS ({len(mods)} imports OK)"
        except Exception as e:
            r["checks"]["imports"] = f"ZERO — {e}"

    def _lint(self, fp, r):
        res = subprocess.run(
            [self.python, "-m", "pylint", "--errors-only", fp],
            capture_output=True, text=True, timeout=20
        )
        errs = [l for l in res.stdout.splitlines() if ': E' in l]
        r["checks"]["lint"] = f"FAIL — {len(errs)} error(s)" if errs else "PASS"
        r["errors"].extend(errs[:5])

    def _pytest(self, fp, r):
        res = subprocess.run(
            [self.python, "-m", "pytest", str(Path(fp).parent), "-x", "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        r["checks"]["tests"] = "PASS" if res.returncode == 0 else "FAIL"
        if res.returncode != 0:
            r["errors"].append(res.stdout[-600:])

    def _sh(self, fp, r):
        res = subprocess.run(["bash", "-n", fp], capture_output=True, text=True)
        r["checks"]["syntax"] = "PASS" if res.returncode == 0 else f"FAIL — {res.stderr.strip()}"
        if res.returncode != 0:
            r["errors"].append(res.stderr.strip())

    def _json(self, fp, r):
        try:
            json.load(open(fp))
            r["checks"]["json"] = "PASS"
        except json.JSONDecodeError as e:
            r["checks"]["json"] = f"FAIL — {e}"
            r["errors"].append(str(e))

    def _summary(self, fp, r):
        icon = {"TRIT_POS":"✅","TRIT_ZERO":"⚠️","TRIT_NEG":"❌"}[r["trit"]]
        lines = [f"{icon} MCP CHECK — {os.path.basename(fp)} — {r['trit']}"]
        for k, v in r["checks"].items():
            lines.append(f"  {k:12s}: {v}")
        for e in r["errors"][:3]:
            lines.append(f"  ERROR: {e}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  SINGLETONS + TOOL ROUTER
# ══════════════════════════════════════════════════════════════════
_mapper  = None
_checker = MCPChecker()

def get_mapper(path: str = None) -> WorkspaceMapper:
    global _mapper
    _mapper = WorkspaceMapper(path or os.environ.get("AEGIS_WORKSPACE", "/home/jsosa/workspace"))
    return _mapper

def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "bash":
        cmd = tool_input.get("command", "")
        if not cmd:
            return "[ERROR] No command."
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=30, cwd=os.environ.get("AEGIS_WORKSPACE","/home/jsosa"))
            out = (r.stdout + r.stderr).strip()
            return out[:4000] or "(no output)"
        except subprocess.TimeoutExpired:
            return "[TIMEOUT] 30s exceeded."
        except Exception as e:
            return f"[ERROR] {e}"

    elif tool_name == "workspace_tree":
        return get_mapper(tool_input.get("path")).scan_workspace_tree()

    elif tool_name == "workspace_search":
        m = get_mapper(tool_input.get("path"))
        hits = m.search_workspace_keywords(tool_input.get("query",""))
        return "\n".join(hits) if hits else "[No matches]"

    elif tool_name == "workspace_find":
        m = get_mapper(tool_input.get("path"))
        hits = m.find_by_extension(tool_input.get("extension",".md"))
        return "\n".join(hits) if hits else "[No files found]"

    elif tool_name == "mcp_check":
        fp = tool_input.get("filepath","")
        if not fp:
            return "[ERROR] filepath required."
        return _checker.check_file(fp, run_tests=tool_input.get("run_tests", False))["summary"]

    return f"[ERROR] Unknown tool: {tool_name}"


# ══════════════════════════════════════════════════════════════════
#  TOOL SCHEMA  (merge into AEGIS_TOOLS in your bridge)
# ══════════════════════════════════════════════════════════════════
WORKSPACE_TOOLS = [
    {"name":"bash",
     "description":"Run any bash command. ALWAYS use to verify real filesystem state — never guess.",
     "input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}},

    {"name":"workspace_tree",
     "description":"Return a formatted tree of a workspace directory. Call at start of any coding task.",
     "input_schema":{"type":"object","properties":{"path":{"type":"string"}}}},

    {"name":"workspace_search",
     "description":"Search files in a workspace directory by keyword content.",
     "input_schema":{"type":"object","properties":{"query":{"type":"string"},"path":{"type":"string"}},"required":["query"]}},

    {"name":"workspace_find",
     "description":"Find all files with a given extension (.md, .py, .sh …) in a directory.",
     "input_schema":{"type":"object","properties":{"extension":{"type":"string"},"path":{"type":"string"}},"required":["extension"]}},

    {"name":"mcp_check",
     "description":"QA check a file after editing. Returns TRIT_POS/ZERO/NEG. ALWAYS call after any code write.",
     "input_schema":{"type":"object","properties":{"filepath":{"type":"string"},"run_tests":{"type":"boolean"}},"required":["filepath"]}},
]


# ══════════════════════════════════════════════════════════════════
#  SESSION INIT
# ══════════════════════════════════════════════════════════════════
def aegis_session_init(workspace_path: str = None) -> str:
    path = workspace_path or os.environ.get("AEGIS_WORKSPACE", "/home/jsosa/workspace")
    return get_mapper(path).build_ooda_context()


# ══════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    test_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/workspace")
    print("=" * 60)
    print("WORKSPACE MAPPER TEST")
    print("=" * 60)
    print(WorkspaceMapper(test_path).scan_workspace_tree())
    print("\n" + "=" * 60)
    print("MCP CHECKER TEST (this file)")
    print("=" * 60)
    print(MCPChecker().check_file(__file__)["summary"])
    print("\n" + "=" * 60)
    print("TOOL DISPATCH TEST")
    print("=" * 60)
    print(dispatch_tool("bash", {"command": "echo 'bash OK'"}))
    print(dispatch_tool("workspace_find", {"extension": ".py", "path": test_path}))
PYEOF
trit_pos "aegis_workspace_patch.py written."

# ── Step 5: Patch run_inference_server.py ────────────────────────────────────
if [ -f "$INFERENCE_SERVER" ]; then
    info "Patching run_inference_server.py ..."

    # Check if already patched
    if grep -q "aegis_workspace_patch" "$INFERENCE_SERVER"; then
        trit_zer "run_inference_server.py already patched — skipping."
    else
        # Find the first import line and inject after it
        INJECT=$(cat << 'INJECT_EOF'

# ── Aegis Workspace + MCP Patch ──────────────────────────────────────────────
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), 'src'))
try:
    from aegis_workspace_patch import (
        aegis_session_init, WORKSPACE_TOOLS, dispatch_tool, get_mapper
    )
    _AEGIS_WORKSPACE = _os.environ.get(
        "AEGIS_WORKSPACE",
        _os.path.join(_os.path.dirname(__file__), '..')
    )
    _ORIENTATION_BLOCK = aegis_session_init(_AEGIS_WORKSPACE)
    print("[AEGIS] Workspace mapper loaded.")
    print(_ORIENTATION_BLOCK)
except ImportError as _e:
    print(f"[AEGIS][WARN] workspace patch not loaded: {_e}")
    WORKSPACE_TOOLS = []
    def dispatch_tool(n, i): return f"[tool unavailable: {n}]"
    _ORIENTATION_BLOCK = ""
# ─────────────────────────────────────────────────────────────────────────────
INJECT_EOF
)
        # Prepend the inject block right after the first shebang/import line
        TMPFILE=$(mktemp)
        awk -v block="$INJECT" '
            /^import |^from |^#!/ && !done {
                print; print block; done=1; next
            }
            { print }
        ' "$INFERENCE_SERVER" > "$TMPFILE"
        mv "$TMPFILE" "$INFERENCE_SERVER"
        trit_pos "run_inference_server.py patched."
    fi
else
    trit_zer "run_inference_server.py not found at $INFERENCE_SERVER — skipping that patch."
fi

# ── Step 6: Patch aegis.sh system prompt ─────────────────────────────────────
if [ -f "$AEGIS_SH" ]; then
    info "Patching aegis.sh system prompt with workspace rules..."

    if grep -q "NEVER hallucinate file paths" "$AEGIS_SH"; then
        trit_zer "aegis.sh already patched — skipping."
    else
        # Append workspace rules to the existing SYSTEM_PROMPT variable
        # Find the closing quote of SYSTEM_PROMPT and insert before it
        sed -i 's/^RULES:$/RULES:\n- NEVER hallucinate file paths or directory contents.\n- After ANY file edit, call mcp_check on that file.\n- Use workspace_find to locate files before operating on them.\n- Report TRIT_NEG if a tool call returned no result — never guess./' "$AEGIS_SH" 2>/dev/null || true

        # Also inject AEGIS_WORKSPACE env var export near the top
        if ! grep -q "AEGIS_WORKSPACE" "$AEGIS_SH"; then
            sed -i '/^set -euo pipefail/a \
\
# Aegis Workspace Root (used by workspace mapper)\
export AEGIS_WORKSPACE="${AEGIS_WORKSPACE:-/home/jsosa/workspace/aegis-ternary}"' "$AEGIS_SH"
        fi
        trit_pos "aegis.sh patched."
    fi
else
    trit_zer "aegis.sh not found at $AEGIS_SH — skipping that patch."
fi

# ── Step 7: Run self-test ─────────────────────────────────────────────────────
echo ""
echo "================================================================"
info "Running self-test..."
echo "================================================================"

# Activate venv if present
VENV="$BITNET_ROOT/venv/bin/activate"
if [ -f "$VENV" ]; then
    source "$VENV"
    trit_pos "venv activated: $VENV"
fi

python3 "$PATCH_FILE" "$BITNET_ROOT"

echo ""
echo "================================================================"
trit_pos "PATCH COMPLETE"
echo "================================================================"
echo ""
echo "  Files modified:"
echo "    $PATCH_FILE          (NEW)"
[ -f "${INFERENCE_SERVER}.bak" ] && echo "    $INFERENCE_SERVER    (patched, backup: .bak)"
[ -f "${AEGIS_SH}.bak" ]         && echo "    $AEGIS_SH            (patched, backup: .bak)"
echo ""
echo "  To test workspace tools manually:"
echo "    cd $BITNET_ROOT"
echo "    python3 src/aegis_workspace_patch.py \$HOME/workspace/aegis-ternary"
echo ""
echo "  To find all MD files in a repo from Aegis, just type:"
echo "    find all the .md files in /home/jsosa/workspace/aegis-ternary"
echo "  Aegis will now call workspace_find instead of guessing."
echo ""
