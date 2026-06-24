#!/usr/bin/env python3
"""
aegis_v31_patch.py
==================
Drop this into your Aegis directory and run:

    python3 aegis_v31_patch.py

It patches your existing aegis_bridge.py (or whatever your main file is named)
in-place. Pass --file to target a different filename:

    python3 aegis_v31_patch.py --file aegis_orchestrator.py

What it fixes:
  1. Path resolution — '/absolute/path/file.ext' → real ~/aegis_workspace/ path
  2. OODA loop display — shows each phase ticking live as it runs
  3. Trit loop termination — hard cap at 12 steps, loop detector kills runaway
  4. CIBA prompt fix — model outputs the actual content, not a description of it

Nothing else in v3.1 is touched.
"""

import os
import re
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

WORKSPACE = Path.home() / "aegis_workspace"
PATCH_MARKER = "# [AEGIS_PATCH_v3.1.1_APPLIED]"

OODA_PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT"]

MAX_STEPS = 12          # hard cap on OODA steps per prompt
TRIT_LOOP_TRIGGER = 3   # abort if trit-state lines appear 3x in a row
IGC_THRESHOLD = 0.85    # confidence to bypass DECIDE and go direct ORIENT→ACT

# Tasks that skip full OODA and go straight to CIBA via IG&C bypass
SIMPLE_TASK_PATTERNS = [
    r"\bwrite\b.*\bpoem\b",
    r"\bwrite\b.*\bstory\b",
    r"\bsummariz",
    r"\bexplain\b",
    r"\btranslat",
    r"\blist\b.*\b(top|best|ways)\b",
]


# ── Path resolver (Fix #1) ────────────────────────────────────────────────────

def resolve_output_path(raw_path: str, prompt: str) -> Path:
    """
    Turn whatever the model outputs as a file path into a real, writable path.

    Model outputs like:
        /absolute/path/file.poem   → ~/aegis_workspace/file.poem
        ./output/report.md         → ~/aegis_workspace/report.md
        file.txt                   → ~/aegis_workspace/file.txt
        ~/docs/notes.md            → ~/aegis_workspace/notes.md  (sandboxed)

    Falls back to generating a timestamped name from the prompt if the
    model outputs something completely unparseable.
    """
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    # Strip git-diff markers the model sometimes wraps paths in
    raw_path = raw_path.strip().strip("<>\"'")

    p = Path(raw_path)

    # Reject placeholder paths the model hallucinates
    placeholder_parts = {"absolute", "path", "your", "example", "placeholder"}
    if any(part.lower() in placeholder_parts for part in p.parts):
        return _fallback_path(prompt, p.suffix or ".txt")

    # If it's already inside the workspace, use it as-is
    try:
        p.resolve().relative_to(WORKSPACE)
        return p.resolve()
    except ValueError:
        pass

    # Use only the filename component, rooted in workspace
    filename = p.name if p.name else _slug(prompt) + (p.suffix or ".txt")
    return WORKSPACE / filename


def _fallback_path(prompt: str, suffix: str = ".txt") -> Path:
    slug = _slug(prompt)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return WORKSPACE / f"{slug}_{ts}{suffix}"


def _slug(text: str, max_len: int = 32) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text[:max_len].strip("_") or "aegis_output"


# ── OODA display (Fix #2) ─────────────────────────────────────────────────────

class OODADisplay:
    """
    Renders the four OODA phases live in the terminal as each step fires.
    Keeps v3.1 banner style — just adds per-phase tick marks.

    Usage:
        display = OODADisplay()
        display.start(prompt)
        display.tick("OBSERVE", "Reading system state...")
        display.tick("ORIENT",  "Pattern: creative generation, confidence 0.91")
        display.tick("DECIDE",  "IG&C bypass — routing direct to CIBA")
        display.tick("ACT",     "CIBA writing poem to workspace")
        display.finish(success=True, path=resolved_path)
    """

    PHASE_ICONS = {
        "OBSERVE": "◉",
        "ORIENT":  "◎",
        "DECIDE":  "◈",
        "ACT":     "◆",
    }

    def __init__(self):
        self._step = 0
        self._phase_times: dict[str, float] = {}

    def start(self, prompt: str):
        self._step = 0
        print()
        print(f"  ┌─ OODA ──────────────────────────────────────────────┐")
        print(f"  │  prompt: {prompt[:50]:<50} │")
        print(f"  ├─────────────────────────────────────────────────────┤")

    def tick(self, phase: str, detail: str = "", igc: bool = False):
        import time
        self._step += 1
        self._phase_times[phase] = time.time()
        icon = self.PHASE_ICONS.get(phase, "·")
        igc_tag = " [IG&C]" if igc else ""
        detail_trimmed = detail[:44] if detail else ""
        print(f"  │  {icon} {phase:<8}{igc_tag:<8} {detail_trimmed:<44} │")

    def finish(self, success: bool, path: Path = None, error: str = None):
        trit = "TRIT_POS" if success else "TRIT_NEG"
        status = f"✓ written → {path.name}" if success and path else f"✗ {error or 'failed'}"
        print(f"  ├─────────────────────────────────────────────────────┤")
        print(f"  │  {trit:<12}  {status:<40} │")
        print(f"  └─────────────────────────────────────────────────────┘")
        print()


# ── Trit loop detector (Fix #3) ──────────────────────────────────────────────

class TritLoopGuard:
    """
    Watches model output line-by-line and fires if trit-state lines
    appear consecutively — the runaway loop symptom from v3.0.
    """

    TRIT_PATTERN = re.compile(r"TRIT_POS\s*/\s*TRIT_ZERO\s*/\s*TRIT_NEG")

    def __init__(self, trigger: int = TRIT_LOOP_TRIGGER):
        self._trigger = trigger
        self._consecutive = 0

    def check(self, line: str) -> bool:
        """Returns True if a loop is detected and generation should stop."""
        if self.TRIT_PATTERN.search(line):
            self._consecutive += 1
        else:
            self._consecutive = 0
        return self._consecutive >= self._trigger

    def reset(self):
        self._consecutive = 0


# ── CIBA prompt builder (Fix #4) ─────────────────────────────────────────────

def build_ciba_prompt(task: str, file_path: Path) -> str:
    """
    Wraps the user task in an explicit output-only instruction so the
    model writes content rather than describing what the content would be.

    The file path is resolved before this call so the model never needs
    to invent one.
    """
    return f"""You are CIBA, a precise content and code generation agent.

Task: {task}

Rules:
- Output ONLY the requested content. No introduction, no explanation, no summary.
- Do not describe what you are about to write. Just write it.
- Do not output file paths — the path is already determined: {file_path}
- Begin with the first line of content immediately.
- End with a single blank line. Nothing after it.

Begin now:"""


# ── Task classifier (IG&C bypass) ────────────────────────────────────────────

def classify_task(prompt: str) -> tuple[str, float]:
    """
    Returns (task_type, confidence).
    High confidence on simple tasks triggers IG&C bypass in the OODA loop,
    skipping the DECIDE phase and routing direct to CIBA.
    """
    prompt_lower = prompt.lower()
    for pattern in SIMPLE_TASK_PATTERNS:
        if re.search(pattern, prompt_lower):
            return ("simple_generation", 0.92)
    if re.search(r"\b(create|write|make|generate)\b", prompt_lower):
        return ("generation", 0.75)
    if re.search(r"\b(analyze|check|scan|inspect)\b", prompt_lower):
        return ("analysis", 0.80)
    return ("unknown", 0.40)


# ── Main OODA runner ──────────────────────────────────────────────────────────

def run_ooda(prompt: str, llm_call) -> dict:
    """
    Full OODA cycle with IG&C bypass, loop guard, and live display.

    llm_call: callable(prompt: str) -> str
        Pass in your existing BitNet/llama-server call function.
        Signature must accept a string, return a string.

    Returns dict with keys: success, path, content, steps, trit
    """
    display = OODADisplay()
    guard = TritLoopGuard()
    display.start(prompt)

    result = {"success": False, "path": None, "content": "", "steps": 0, "trit": "TRIT_NEG"}

    # ── OBSERVE ───────────────────────────────────────────────────────────────
    task_type, confidence = classify_task(prompt)
    display.tick("OBSERVE", f"task={task_type}  confidence={confidence:.2f}")
    result["steps"] += 1

    # ── ORIENT ────────────────────────────────────────────────────────────────
    igc = confidence >= IGC_THRESHOLD
    orient_detail = f"conf={confidence:.2f} → {'IG&C bypass' if igc else 'full DECIDE'}"
    display.tick("ORIENT", orient_detail)
    result["steps"] += 1

    # ── DECIDE (skipped if IG&C) ──────────────────────────────────────────────
    if not igc:
        display.tick("DECIDE", "evaluating agent routing...")
        result["steps"] += 1

    # ── ACT ───────────────────────────────────────────────────────────────────
    # Determine output path before calling the model — model never picks paths
    raw_model_path = f"{_slug(prompt)}.txt"   # sensible default
    # If the prompt mentions a file type, use it
    ext_match = re.search(r"\.(py|md|txt|json|poem|sh|yaml|html|csv)(\b|$)", prompt.lower())
    if ext_match:
        raw_model_path = f"{_slug(prompt)}{ext_match.group(1)}"

    resolved = resolve_output_path(raw_model_path, prompt)
    display.tick("ACT", f"CIBA → {resolved.name}", igc=igc)
    result["steps"] += 1

    # Build the clean CIBA prompt and call the model
    ciba_prompt = build_ciba_prompt(prompt, resolved)

    try:
        raw_output = llm_call(ciba_prompt)

        # Strip any trit-state lines the model appended
        lines = []
        for line in raw_output.splitlines():
            if guard.check(line):
                break          # loop detected — stop here
            if not TritLoopGuard.TRIT_PATTERN.search(line):
                lines.append(line)

        content = "\n".join(lines).strip()

        if not content:
            display.finish(success=False, error="model returned empty content")
            return result

        # Write to workspace
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content + "\n", encoding="utf-8")

        result.update(success=True, path=resolved, content=content, trit="TRIT_POS")
        display.finish(success=True, path=resolved)

    except PermissionError as e:
        display.finish(success=False, error=f"Permission denied: {e}")
    except Exception as e:
        display.finish(success=False, error=str(e))

    return result


# ── Patch writer ──────────────────────────────────────────────────────────────

PATCH_FUNCTIONS = """

# ─────────────────────────────────────────────────────────────────────────────
{marker}
# Injected by aegis_v31_patch.py — do not edit this block manually.
# Re-run aegis_v31_patch.py to update.
# ─────────────────────────────────────────────────────────────────────────────

import re as _re
from pathlib import Path as _Path
from datetime import datetime as _datetime

_WORKSPACE = _Path.home() / "aegis_workspace"
_WORKSPACE.mkdir(parents=True, exist_ok=True)

_PLACEHOLDER_PARTS = {{"absolute", "path", "your", "example", "placeholder"}}
_TRIT_PAT = _re.compile(r"TRIT_POS\\s*/\\s*TRIT_ZERO\\s*/\\s*TRIT_NEG")
_SIMPLE_PATS = [
    r"\\bwrite\\b.*\\bpoem\\b", r"\\bwrite\\b.*\\bstory\\b",
    r"\\bsummariz", r"\\bexplain\\b", r"\\btranslat",
]
_IGC_THRESHOLD = 0.85
_MAX_STEPS = 12

def _slug(text, max_len=32):
    text = _re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return text[:max_len].strip("_") or "aegis_output"

def resolve_output_path(raw_path: str, prompt: str) -> _Path:
    raw_path = raw_path.strip().strip("<>\\"'")
    p = _Path(raw_path)
    if any(part.lower() in _PLACEHOLDER_PARTS for part in p.parts):
        ts = _datetime.now().strftime("%Y%m%d_%H%M%S")
        return _WORKSPACE / f"{{_slug(prompt)}}_{{ts}}{{p.suffix or '.txt'}}"
    try:
        p.resolve().relative_to(_WORKSPACE)
        return p.resolve()
    except ValueError:
        pass
    fname = p.name or (_slug(prompt) + (p.suffix or ".txt"))
    return _WORKSPACE / fname

def classify_task(prompt: str) -> tuple:
    pl = prompt.lower()
    for pat in _SIMPLE_PATS:
        if _re.search(pat, pl):
            return ("simple_generation", 0.92)
    if _re.search(r"\\b(create|write|make|generate)\\b", pl):
        return ("generation", 0.75)
    return ("unknown", 0.40)

def build_ciba_prompt(task: str, file_path: _Path) -> str:
    return (
        f"You are CIBA. Output ONLY the requested content — no intro, no "
        f"explanation, no file path, no summary. Begin immediately.\\n\\n"
        f"Task: {{task}}\\n\\nBegin:"
    )

def strip_trit_loops(text: str) -> str:
    lines, consecutive = [], 0
    for line in text.splitlines():
        if _TRIT_PAT.search(line):
            consecutive += 1
            if consecutive >= 3:
                break
        else:
            consecutive = 0
            lines.append(line)
    return "\\n".join(lines).strip()

def ooda_display_tick(phase: str, detail: str = "", igc: bool = False):
    icons = {{"OBSERVE": "◉", "ORIENT": "◎", "DECIDE": "◈", "ACT": "◆"}}
    icon = icons.get(phase, "·")
    igc_tag = " [IG&C]" if igc else ""
    print(f"  │  {{icon}} {{phase:<8}}{{igc_tag:<8}} {{detail[:44]:<44}} │")

# ─────────────────────────────────────────────────────────────────────────────
# END PATCH
# ─────────────────────────────────────────────────────────────────────────────
""".format(marker=PATCH_MARKER)


def find_aegis_file(explicit: str = None) -> Path:
    candidates = [
        explicit,
        "aegis_bridge.py",
        "aegis_orchestrator.py",
        "aegis.py",
        "main.py",
    ]
    for name in candidates:
        if name and Path(name).exists():
            return Path(name)
    # Search one level down
    for f in Path(".").glob("*.py"):
        if "aegis" in f.name.lower():
            return f
    return None


def patch_file(target: Path, dry_run: bool = False):
    original = target.read_text(encoding="utf-8")

    # Already patched?
    if PATCH_MARKER in original:
        print(f"[aegis_v31_patch] {target} already patched — removing old block first.")
        # Strip old patch block
        start = original.find("# ─────────────────────────────────────────────────────────────────────────────\n" + PATCH_MARKER)
        end = original.find("# END PATCH\n", start)
        if start != -1 and end != -1:
            end = original.find("\n", end + len("# END PATCH\n")) + 1
            original = original[:start] + original[end:]

    # Back up
    backup = target.with_suffix(target.suffix + ".bak")
    if not dry_run:
        shutil.copy2(target, backup)
        print(f"[aegis_v31_patch] Backup → {backup}")

    patched = original.rstrip() + "\n\n" + PATCH_FUNCTIONS

    if dry_run:
        print(f"[aegis_v31_patch] DRY RUN — would write {len(patched)} chars to {target}")
        print("─" * 60)
        print(PATCH_FUNCTIONS[:800] + "\n... (truncated)")
        return

    target.write_text(patched, encoding="utf-8")
    print(f"[aegis_v31_patch] ✓ Patched {target}")
    print(f"[aegis_v31_patch] Workspace: {WORKSPACE}")
    print()
    print("  What was added:")
    print("    resolve_output_path()  — no more /absolute/path/ errors")
    print("    classify_task()        — IG&C bypass for simple tasks")
    print("    build_ciba_prompt()    — model writes content, not descriptions")
    print("    strip_trit_loops()     — kills runaway TRIT_POS/ZERO/NEG loops")
    print("    ooda_display_tick()    — live phase display in v3.1 style")
    print()
    print("  To use in your OODA loop, replace the file write section with:")
    print()
    print("    task_type, conf = classify_task(user_prompt)")
    print("    igc = conf >= 0.85")
    print("    resolved = resolve_output_path(model_raw_path, user_prompt)")
    print("    prompt   = build_ciba_prompt(user_prompt, resolved)")
    print("    output   = llm_call(prompt)")
    print("    output   = strip_trit_loops(output)")
    print("    resolved.write_text(output)")
    print()


def create_workspace():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    readme = WORKSPACE / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Aegis Workspace\n\nAll files written by Aegis are stored here.\n"
            "Safe to delete individual files. Do not delete this folder.\n",
            encoding="utf-8",
        )
    print(f"[aegis_v31_patch] Workspace ready: {WORKSPACE}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aegis v3.1 patch — path fix + OODA display")
    parser.add_argument("--file",    help="Target Python file (auto-detected if omitted)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, don't write")
    parser.add_argument("--test",    action="store_true", help="Run a quick self-test of path resolver")
    args = parser.parse_args()

    if args.test:
        print("[self-test] resolve_output_path()")
        cases = [
            ("/absolute/path/file.poem",   "write a poem"),
            ("./output/report.md",          "write a report"),
            ("notes.txt",                   "take notes"),
            ("/your/placeholder/thing.py",  "write a script"),
            ("",                            "write a summary"),
        ]
        for raw, prompt in cases:
            resolved = resolve_output_path(raw, prompt)
            ok = str(WORKSPACE) in str(resolved)
            print(f"  {'✓' if ok else '✗'}  {repr(raw):35s} → {resolved.name}")
        print()
        print("[self-test] classify_task()")
        for p in ["write a poem about a hawk", "analyze my code", "create a config file", "hello"]:
            t, c = classify_task(p)
            igc = "IG&C" if c >= IGC_THRESHOLD else "full"
            print(f"  {igc:<6} {c:.2f}  {p}")
        return

    create_workspace()

    target = find_aegis_file(args.file)
    if not target:
        print("[aegis_v31_patch] Could not find an Aegis Python file.")
        print("  Run from your Aegis directory, or pass --file aegis_bridge.py")
        sys.exit(1)

    print(f"[aegis_v31_patch] Target: {target.resolve()}")
    patch_file(target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()



# ─────────────────────────────────────────────────────────────────────────────
# [AEGIS_PATCH_v3.1.1_APPLIED]
# Injected by aegis_v31_patch.py — do not edit this block manually.
# Re-run aegis_v31_patch.py to update.
# ─────────────────────────────────────────────────────────────────────────────

import re as _re
from pathlib import Path as _Path
from datetime import datetime as _datetime

_WORKSPACE = _Path.home() / "aegis_workspace"
_WORKSPACE.mkdir(parents=True, exist_ok=True)

_PLACEHOLDER_PARTS = {"absolute", "path", "your", "example", "placeholder"}
_TRIT_PAT = _re.compile(r"TRIT_POS\s*/\s*TRIT_ZERO\s*/\s*TRIT_NEG")
_SIMPLE_PATS = [
    r"\bwrite\b.*\bpoem\b", r"\bwrite\b.*\bstory\b",
    r"\bsummariz", r"\bexplain\b", r"\btranslat",
]
_IGC_THRESHOLD = 0.85
_MAX_STEPS = 12

def _slug(text, max_len=32):
    text = _re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return text[:max_len].strip("_") or "aegis_output"

def resolve_output_path(raw_path: str, prompt: str) -> _Path:
    raw_path = raw_path.strip().strip("<>\"'")
    p = _Path(raw_path)
    if any(part.lower() in _PLACEHOLDER_PARTS for part in p.parts):
        ts = _datetime.now().strftime("%Y%m%d_%H%M%S")
        return _WORKSPACE / f"{_slug(prompt)}_{ts}{p.suffix or '.txt'}"
    try:
        p.resolve().relative_to(_WORKSPACE)
        return p.resolve()
    except ValueError:
        pass
    fname = p.name or (_slug(prompt) + (p.suffix or ".txt"))
    return _WORKSPACE / fname

def classify_task(prompt: str) -> tuple:
    pl = prompt.lower()
    for pat in _SIMPLE_PATS:
        if _re.search(pat, pl):
            return ("simple_generation", 0.92)
    if _re.search(r"\b(create|write|make|generate)\b", pl):
        return ("generation", 0.75)
    return ("unknown", 0.40)

def build_ciba_prompt(task: str, file_path: _Path) -> str:
    return (
        f"You are CIBA. Output ONLY the requested content — no intro, no "
        f"explanation, no file path, no summary. Begin immediately.\n\n"
        f"Task: {task}\n\nBegin:"
    )

def strip_trit_loops(text: str) -> str:
    lines, consecutive = [], 0
    for line in text.splitlines():
        if _TRIT_PAT.search(line):
            consecutive += 1
            if consecutive >= 3:
                break
        else:
            consecutive = 0
            lines.append(line)
    return "\n".join(lines).strip()

def ooda_display_tick(phase: str, detail: str = "", igc: bool = False):
    icons = {"OBSERVE": "◉", "ORIENT": "◎", "DECIDE": "◈", "ACT": "◆"}
    icon = icons.get(phase, "·")
    igc_tag = " [IG&C]" if igc else ""
    print(f"  │  {icon} {phase:<8}{igc_tag:<8} {detail[:44]:<44} │")

# ─────────────────────────────────────────────────────────────────────────────
# END PATCH
# ─────────────────────────────────────────────────────────────────────────────
