#!/usr/bin/env python3
"""
aegis_loop_fix.py
=================
This does ONE thing: replaces your OODA ACT loop with a version
that actually stops.

The problem: your loop retries ACT 4-5 times on TDD skip/fail.
This version exits on:
  - successful write
  - TDD skip (file exists)
  - any permission/IO error
  - after 1 attempt for non-file tasks

HOW TO USE
----------
This is NOT another appended patch. Run it and it will show you
the EXACT lines to find in your file and what to replace them with.

    python3 aegis_loop_fix.py --scan --file /path/to/your/aegis.py

Then apply:
    python3 aegis_loop_fix.py --apply --file /path/to/your/aegis.py

Or just copy the OODAActGuard class below directly into your code.
"""

import re
import sys
import shutil
from pathlib import Path
from enum import Enum


# ═════════════════════════════════════════════════════════════════════════════
# THE FIX — drop this class into your aegis file and call run_act()
# ═════════════════════════════════════════════════════════════════════════════

class ActResult(Enum):
    SUCCESS   = "success"
    TDD_SKIP  = "tdd_skip"
    ERROR     = "error"
    PLAIN     = "plain"


class OODAActGuard:
    """
    Wraps the ACT phase with proper exit conditions.
    Call run_act() once per OODA cycle. It will never loop.

    Replace your current ACT block with:

        guard  = OODAActGuard(workspace=Path.home() / "aegis_workspace")
        result = guard.run_act(raw_model_output, user_prompt)
        guard.render(result)
        # done — do NOT loop back to ACT
    """

    # Patterns that mean "just print text, no file"
    PLAIN_PATTERNS = [
        r"\bpoem\b", r"\bsong\b", r"\bstory\b", r"\bhaiku\b",
        r"\blyric", r"\brhyme\b", r"\bverse\b", r"\bsummariz",
        r"\bexplain\b", r"\bdescribe\b", r"\btell\b", r"\bwhat is\b",
        r"\bwho is\b", r"\bhow does\b", r"\blist\b", r"\bgive me\b",
        r"\banalyze\b", r"\breview\b",
    ]

    FILE_BLOCK_RE = re.compile(
        r"FILE:\s*(\S+)\n"
        r"(?:```\w*\n)?"
        r"(.*?)"
        r"(?:\n```\n|\n>>>>>>> END)",
        re.DOTALL
    )

    TRIT_RE = re.compile(r"TRIT_(POS|ZERO|NEG)")

    # Ansi
    G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
    C = "\033[36m"; D = "\033[2m";  E = "\033[0m"; B = "\033[1m"

    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.home() / "aegis_workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ── Public ────────────────────────────────────────────────────────────────

    def run_act(self, raw_output: str, user_prompt: str) -> dict:
        """
        Single-shot ACT. Returns result dict, never loops.

        result = {
            "status":  ActResult,
            "mode":    "plain" | "file" | "code",
            "content": str,
            "path":    Path | None,
            "trit":    str,
            "message": str,   # human-readable status line
        }
        """
        mode = self._classify(user_prompt)
        trit = self._extract_trit(raw_output)

        if mode == "plain":
            content = self._strip_file_blocks(raw_output)
            return {
                "status":  ActResult.PLAIN,
                "mode":    "plain",
                "content": content,
                "path":    None,
                "trit":    trit,
                "message": "plain text response",
            }

        # File/code mode — find FIRST block only, ignore the rest
        match = self.FILE_BLOCK_RE.search(raw_output)
        if not match:
            # Model didn't emit a FILE: block even though we expected one
            # Fall back to plain
            content = self._strip_file_blocks(raw_output)
            return {
                "status":  ActResult.PLAIN,
                "mode":    "plain",
                "content": content,
                "path":    None,
                "trit":    trit,
                "message": "no FILE block found — rendered as plain",
            }

        raw_path = match.group(1)
        content  = match.group(2).strip()
        path     = self._resolve_path(raw_path, user_prompt,
                                      ext=".py" if mode == "code" else ".txt")

        # TDD guard — file exists with real content
        if path.exists() and path.stat().st_size > 30:
            return {
                "status":  ActResult.TDD_SKIP,
                "mode":    mode,
                "content": content,
                "path":    path,
                "trit":    trit,
                "message": f"TDD: file exists — skipping. Use 'force' to overwrite.",
            }

        # Write — once, no retry
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content + "\n", encoding="utf-8")
            return {
                "status":  ActResult.SUCCESS,
                "mode":    mode,
                "content": content,
                "path":    path,
                "trit":    trit,
                "message": f"written ({path.stat().st_size} bytes)",
            }
        except PermissionError as e:
            return {
                "status":  ActResult.ERROR,
                "mode":    mode,
                "content": content,
                "path":    path,
                "trit":    "TRIT_NEG",
                "message": f"Permission denied: {e}",
            }
        except Exception as e:
            return {
                "status":  ActResult.ERROR,
                "mode":    mode,
                "content": content,
                "path":    path,
                "trit":    "TRIT_NEG",
                "message": str(e),
            }

    def render(self, result: dict):
        """Print result in v3.1 style. Call once after run_act()."""
        tc = {
            "TRIT_POS":  self.G,
            "TRIT_ZERO": self.Y,
            "TRIT_NEG":  self.R,
        }.get(result["trit"], "")

        status_icon = {
            ActResult.SUCCESS:  "✓",
            ActResult.TDD_SKIP: "⊘",
            ActResult.ERROR:    "✗",
            ActResult.PLAIN:    " ",
        }[result["status"]]

        if result["mode"] == "plain":
            print()
            print(result["content"])
            print()
            print(f"{tc}{result['trit']}{self.E}")
            return

        path = result["path"]
        print()
        print(f"  {self.C}[OODA/ACT — CREATE]{self.E} {path}")
        print(f"  {status_icon} {self.D}{result['message']}{self.E}")
        print(f"  {tc}{result['trit']}{self.E} {self.D}{path.name}{self.E}")

        if result["status"] == ActResult.SUCCESS:
            print(f"{self.D}<<<<<<< CREATE{self.E}")
            # Print first 20 lines only to avoid flooding terminal
            lines = result["content"].splitlines()
            for line in lines[:20]:
                print(line)
            if len(lines) > 20:
                print(f"{self.D}... ({len(lines)-20} more lines){self.E}")
            print(f"{self.D}>>>>>>> END{self.E}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify(self, prompt: str) -> str:
        p = prompt.lower()
        for pat in self.PLAIN_PATTERNS:
            if re.search(pat, p):
                return "plain"
        if re.search(r"\bimplement\b|\bwrite\b.*\b(script|function|class)\b", p):
            return "code"
        if re.search(r"\bcreate\b.*\bfile\b|\bsave\b|\bgenerate\b.*\.(py|md|txt)", p):
            return "file"
        return "plain"   # always default to plain — safer

    def _resolve_path(self, raw: str, prompt: str, ext: str = ".txt") -> Path:
        p = Path(raw.strip().strip("\"'<>"))
        bad = {"absolute", "path", "your", "example", "placeholder", "home"}
        if any(part.lower() in bad for part in p.parts) or not p.name:
            slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:32].strip("_")
            return self.workspace / f"{slug}{ext}"
        # Keep filename, root in workspace
        return self.workspace / p.name

    def _extract_trit(self, text: str) -> str:
        m = self.TRIT_RE.search(text)
        return f"TRIT_{m.group(1)}" if m else "TRIT_POS"

    def _strip_file_blocks(self, text: str) -> str:
        clean = self.FILE_BLOCK_RE.sub("", text)
        clean = self.TRIT_RE.sub("", clean)
        clean = re.sub(r"```\w*\n?|>>>>>>> END|<<<<<<< CREATE|=======", "", clean)
        return clean.strip()


# ═════════════════════════════════════════════════════════════════════════════
# SCANNER — finds the loop in your file
# ═════════════════════════════════════════════════════════════════════════════

LOOP_SIGNATURES = [
    # Common patterns that indicate a retrying ACT loop
    r"while.*act",
    r"for.*ooda",
    r"retry.*act",
    r"act.*loop",
    r"\[OODA/ACT.*CREATE\]",
    r"TDD.*skipping",
    r"File exists with real content",
]


def scan_file(target: Path) -> list[tuple[int, str]]:
    """Find lines that look like the problematic loop."""
    hits = []
    for i, line in enumerate(target.read_text().splitlines(), 1):
        for sig in LOOP_SIGNATURES:
            if re.search(sig, line, re.IGNORECASE):
                hits.append((i, line.rstrip()))
                break
    return hits


def show_scan(target: Path):
    hits = scan_file(target)
    if not hits:
        print(f"[loop_fix] No loop signatures found in {target.name}")
        print("  The loop may be in a different file. Try --file <path>")
        return

    print(f"\n[loop_fix] Found {len(hits)} loop-related lines in {target.name}:\n")
    for lineno, line in hits:
        print(f"  {lineno:4d}  {line[:80]}")

    print(f"""
[loop_fix] Next steps:
  1. Open {target} in your editor
  2. Find your ACT phase handler (around the lines above)
  3. Replace the loop body with:

       guard  = OODAActGuard()
       result = guard.run_act(raw_model_output, user_prompt)
       guard.render(result)
       # Nothing after this — no retry, no loop

  4. Delete any while/for loop wrapping the ACT block
  5. The TDD skip will print ⊘ and stop — not retry
""")


# ═════════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ═════════════════════════════════════════════════════════════════════════════

def run_tests():
    g = OODAActGuard(workspace=Path("/tmp/aegis_test_workspace"))

    print("\n── Test 1: poem → plain text ────────────────────────────────")
    raw = "FILE: /absolute/path/line1.py\n```python\ndef poem(): pass\n```\n>>>>>>> END\nTRIT_POS\n" * 10
    r = g.run_act(raw, "Write a poem about a cat and a hat")
    assert r["status"] == ActResult.PLAIN, f"Expected PLAIN got {r['status']}"
    assert "FILE:" not in r["content"]
    print(f"  ✓ status={r['status'].value}  content={repr(r['content'][:40])}")

    print("\n── Test 2: file create → writes once ───────────────────────")
    raw2 = "FILE: /absolute/path/output.txt\nHello world\n>>>>>>> END\nTRIT_POS"
    r2 = g.run_act(raw2, "Create a file called output.txt")
    assert r2["status"] == ActResult.SUCCESS
    assert r2["path"].exists()
    print(f"  ✓ status={r2['status'].value}  path={r2['path']}")

    print("\n── Test 3: TDD skip on existing file ───────────────────────")
    r3 = g.run_act(raw2, "Create a file called output.txt")
    assert r3["status"] == ActResult.TDD_SKIP
    print(f"  ✓ status={r3['status'].value}  (file exists, correctly skipped)")

    print("\n── Test 4: 53 FILE blocks → only first used ────────────────")
    raw4 = "\n".join(
        f"FILE: /absolute/path/line{i}.py\n```python\ndef f(): pass\n```\n>>>>>>> END\nTRIT_POS"
        for i in range(1, 54)
    )
    r4 = g.run_act(raw4, "Create a script")
    assert r4["status"] in (ActResult.SUCCESS, ActResult.TDD_SKIP)
    # Should never have written line2 through line53
    for i in range(2, 54):
        bad = Path(f"/tmp/aegis_test_workspace/line{i}.py")
        assert not bad.exists(), f"Should not have written {bad}"
    print(f"  ✓ Only first block used. 52 phantom files never written.")

    print("\n  All tests passed ✓\n")

    # Cleanup
    import shutil
    shutil.rmtree("/tmp/aegis_test_workspace", ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Aegis OODA loop fix")
    ap.add_argument("--file",  help="Your aegis .py file")
    ap.add_argument("--scan",  action="store_true", help="Find the loop in your file")
    ap.add_argument("--test",  action="store_true", help="Run self-tests")
    args = ap.parse_args()

    if args.test:
        run_tests()
        return

    # Find target
    target = None
    if args.file:
        target = Path(args.file)
    else:
        for name in ["aegis_bridge.py", "aegis_orchestrator.py", "aegis.py", "main.py"]:
            if Path(name).exists():
                target = Path(name)
                break
        if not target:
            for f in Path(".").glob("*.py"):
                if "aegis" in f.name.lower() and "patch" not in f.name.lower():
                    target = f
                    break

    if not target or not target.exists():
        print("[loop_fix] No aegis file found. Use --file /path/to/your/aegis.py")
        sys.exit(1)

    if args.scan:
        show_scan(target)
        return

    # Default: scan + instructions
    print(f"[loop_fix] Scanning {target.resolve()}")
    show_scan(target)
    print("[loop_fix] Run with --test to verify OODAActGuard works on your machine.")
    print("[loop_fix] Then copy OODAActGuard into your aegis file and wire it in.")


if __name__ == "__main__":
    main()
