#!/usr/bin/env python3
"""
aegis_ooda_dots_patch.py
========================
Patches your Aegis .py file to show the same live dot animation
that the .sh version shows:

  [ORIENT] Inference...
  ◉ · · ·   OBSERVE   Collecting system state
  ◎ · · ·   ORIENT    Pattern match — confidence 0.92
  ◈ · · ·   DECIDE    IG&C bypass active
  ◆ · · ·   ACT       CIBA writing poem...

Run from your Aegis directory:
  python3 aegis_ooda_dots_patch.py

Pass --preview to see the animation without patching anything.
"""

import sys
import time
import threading
import itertools
import argparse
from pathlib import Path


# ── Spinner / dot animator ────────────────────────────────────────────────────

PHASE_ICONS = {
    "OBSERVE": "◉",
    "ORIENT":  "◎",
    "DECIDE":  "◈",
    "ACT":     "◆",
}

PHASE_COLORS = {
    "OBSERVE": "\033[36m",   # cyan
    "ORIENT":  "\033[35m",   # magenta
    "DECIDE":  "\033[33m",   # yellow
    "ACT":     "\033[32m",   # green
}

RESET  = "\033[0m"
DIM    = "\033[2m"
BOLD   = "\033[1m"


class OODASpinner:
    """
    Shows a live animated dot ticker for each OODA phase.
    Matches the [ORIENT] Inference... style from the .sh version
    but adds the icon and phase name.

    Usage:
        with OODASpinner("ORIENT", "Inference") as s:
            result = do_bitnet_call()
        # spinner stops, line is replaced with completed tick
    """

    DOT_FRAMES = [
        "· · ·",
        "● · ·",
        "· ● ·",
        "· · ●",
        "· ● ·",
    ]

    def __init__(self, phase: str, detail: str = "", igc: bool = False):
        self.phase  = phase
        self.detail = detail
        self.igc    = igc
        self._stop  = threading.Event()
        self._thread = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        # Print the completed line (static, no animation)
        icon   = PHASE_ICONS.get(self.phase, "·")
        color  = PHASE_COLORS.get(self.phase, "")
        igc_tag = f"{DIM}[IG&C]{RESET} " if self.igc else ""
        detail = self.detail[:48]
        print(f"\r  {color}{icon}{RESET}  {BOLD}{self.phase:<8}{RESET} {igc_tag}{DIM}{detail}{RESET}  ✓")

    def _spin(self):
        icon   = PHASE_ICONS.get(self.phase, "·")
        color  = PHASE_COLORS.get(self.phase, "")
        igc_tag = f"{DIM}[IG&C]{RESET} " if self.igc else ""
        frames  = itertools.cycle(self.DOT_FRAMES)
        detail  = self.detail[:40]
        while not self._stop.is_set():
            frame = next(frames)
            line  = (
                f"\r  {color}{icon}{RESET}  "
                f"{BOLD}{self.phase:<8}{RESET} "
                f"{DIM}{frame}{RESET}  "
                f"{igc_tag}{detail}"
            )
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(0.12)
        sys.stdout.write("\r" + " " * 72 + "\r")  # clear line
        sys.stdout.flush()


def ooda_header(prompt: str):
    """Print the OODA session header matching v3.1 style."""
    print()
    print(f"  ┌─ OODA ──────────────────────────────────────────────┐")
    print(f"  │  {prompt[:54]:<54} │")
    print(f"  ├─────────────────────────────────────────────────────┤")


def ooda_footer(trit: str, detail: str = ""):
    colors = {"TRIT_POS": "\033[32m", "TRIT_ZERO": "\033[33m", "TRIT_NEG": "\033[31m"}
    c = colors.get(trit, "")
    print(f"  ├─────────────────────────────────────────────────────┤")
    print(f"  │  {c}{trit}{RESET}  {detail[:46]:<46} │")
    print(f"  └─────────────────────────────────────────────────────┘")
    print()


# ── Code block to inject ──────────────────────────────────────────────────────

INJECT_MARKER = "# [AEGIS_OODA_DOTS_v1]"

INJECT_CODE = '''

# ─────────────────────────────────────────────────────────────────────────────
{marker}
# OODA dot animation — matches .sh [ORIENT] Inference... style
# Injected by aegis_ooda_dots_patch.py
# ─────────────────────────────────────────────────────────────────────────────
import sys as _sys, time as _time, threading as _threading, itertools as _itertools

_PHASE_ICONS  = {{"OBSERVE":"◉","ORIENT":"◎","DECIDE":"◈","ACT":"◆"}}
_PHASE_COLORS = {{"OBSERVE":"\\033[36m","ORIENT":"\\033[35m","DECIDE":"\\033[33m","ACT":"\\033[32m"}}
_RST  = "\\033[0m"; _DIM = "\\033[2m"; _BLD = "\\033[1m"
_DOT_FRAMES = ["· · ·","● · ·","· ● ·","· · ●","· ● ·"]

class OODASpinner:
    def __init__(self, phase, detail="", igc=False):
        self.phase=phase; self.detail=detail; self.igc=igc
        self._stop=_threading.Event(); self._t=None
    def __enter__(self):
        self._t=_threading.Thread(target=self._spin,daemon=True); self._t.start(); return self
    def __exit__(self,*_):
        self._stop.set(); self._t.join()
        ic=_PHASE_ICONS.get(self.phase,"·"); co=_PHASE_COLORS.get(self.phase,"")
        ig=f"{{_DIM}}[IG&C]{{_RST}} " if self.igc else ""
        print(f"\\r  {{co}}{{ic}}{{_RST}}  {{_BLD}}{{self.phase:<8}}{{_RST}} {{ig}}{{_DIM}}{{self.detail[:48]}}{{_RST}}  ✓")
    def _spin(self):
        ic=_PHASE_ICONS.get(self.phase,"·"); co=_PHASE_COLORS.get(self.phase,"")
        ig=f"{{_DIM}}[IG&C]{{_RST}} " if self.igc else ""
        for fr in _itertools.cycle(_DOT_FRAMES):
            if self._stop.is_set(): break
            _sys.stdout.write(f"\\r  {{co}}{{ic}}{{_RST}}  {{_BLD}}{{self.phase:<8}}{{_RST}} {{_DIM}}{{fr}}{{_RST}}  {{ig}}{{self.detail[:40]}}")
            _sys.stdout.flush(); _time.sleep(0.12)
        _sys.stdout.write("\\r"+" "*72+"\\r"); _sys.stdout.flush()

def ooda_header(prompt):
    print(f"\\n  ┌─ OODA ──────────────────────────────────────────────┐")
    print(f"  │  {{prompt[:54]:<54}} │")
    print(f"  ├─────────────────────────────────────────────────────┤")

def ooda_footer(trit, detail=""):
    _c={{"TRIT_POS":"\\033[32m","TRIT_ZERO":"\\033[33m","TRIT_NEG":"\\033[31m"}}.get(trit,"")
    print(f"  ├─────────────────────────────────────────────────────┤")
    print(f"  │  {{_c}}{{trit}}{{_RST}}  {{detail[:46]:<46}} │")
    print(f"  └─────────────────────────────────────────────────────┘\\n")

# ─────────────────────────────────────────────────────────────────────────────
# HOW TO USE — replace your current phase print statements with:
#
#   ooda_header(user_prompt)
#
#   with OODASpinner("OBSERVE", "Collecting system state"):
#       sys_state = observer.latest()
#
#   with OODASpinner("ORIENT", f"confidence {conf:.2f}", igc=igc):
#       task_type, conf = classify_task(user_prompt)
#
#   if not igc:
#       with OODASpinner("DECIDE", "routing to agent"):
#           agent = route(task_type)
#
#   with OODASpinner("ACT", f"CIBA writing {resolved.name}", igc=igc):
#       output = llm_call(ciba_prompt)
#       resolved.write_text(strip_trit_loops(output))
#
#   ooda_footer(trit_score, f"→ {resolved.name}")
#
# ─────────────────────────────────────────────────────────────────────────────
'''.format(marker=INJECT_MARKER)


# ── Preview mode ──────────────────────────────────────────────────────────────

def run_preview():
    """Show the animation live without touching any files."""
    prompt = "Create a poem about a hawk and a cat"
    ooda_header(prompt)

    with OODASpinner("OBSERVE", "Collecting system state"):
        time.sleep(0.8)

    with OODASpinner("ORIENT", "confidence 0.92 — IG&C active", igc=True):
        time.sleep(0.6)

    # DECIDE skipped (IG&C)

    with OODASpinner("ACT", "CIBA writing hawk_cat_poem.txt"):
        time.sleep(1.2)

    ooda_footer("TRIT_POS", "→ hawk_cat_poem.txt  written")


# ── Patch writer ──────────────────────────────────────────────────────────────

def find_target(explicit=None):
    candidates = [explicit, "aegis_bridge.py", "aegis_orchestrator.py", "aegis.py", "main.py"]
    for name in candidates:
        if name and Path(name).exists():
            return Path(name)
    for f in Path(".").glob("*.py"):
        if "aegis" in f.name.lower() and "patch" not in f.name.lower():
            return f
    return None


def patch(target: Path, dry_run: bool = False):
    import shutil
    src = target.read_text(encoding="utf-8")

    if INJECT_MARKER in src:
        print(f"[dots_patch] Already patched — skipping. Run with --force to re-inject.")
        return

    patched = src.rstrip() + "\n" + INJECT_CODE

    if dry_run:
        print(f"[dots_patch] DRY RUN — would append {len(INJECT_CODE)} chars to {target}")
        return

    shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    target.write_text(patched, encoding="utf-8")

    print(f"[dots_patch] ✓ Patched {target}")
    print()
    print("  Injected:  OODASpinner  ooda_header()  ooda_footer()")
    print()
    print("  Quick wire-in — replace your phase prints with:")
    print()
    print('    ooda_header(user_prompt)')
    print('    with OODASpinner("OBSERVE", "system state"):')
    print('        state = observer.latest()')
    print('    with OODASpinner("ORIENT", f"conf {conf:.2f}", igc=igc):')
    print('        task_type, conf = classify_task(prompt)')
    print('    with OODASpinner("ACT", f"CIBA → {resolved.name}"):')
    print('        output = llm_call(ciba_prompt)')
    print('    ooda_footer(trit, f"→ {resolved.name}")')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Aegis OODA dot animation patch")
    ap.add_argument("--file",    help="Target .py file")
    ap.add_argument("--preview", action="store_true", help="Show animation without patching")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.preview:
        run_preview()
        return

    target = find_target(args.file)
    if not target:
        print("[dots_patch] No Aegis .py file found. Run from your Aegis directory.")
        sys.exit(1)

    print(f"[dots_patch] Target: {target.resolve()}")
    patch(target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
