"""
Aegis Git Controller — Structured git operations with ANSI-colored output.

Wraps common git commands with formatted terminal output.
All commands use subprocess.run() in list form (no shell injection).

Usage:
    from tools.git_controller import GitController
    gc = GitController()
    print(gc.status())
"""

import os
import subprocess

# ANSI colors (match aegis-cli.py palette)
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; BL = "\033[1;34m"; DM = "\033[0;36m"
WH = "\033[1;37m"; RS = "\033[0m"


class GitController:
    """Structured git operations with ANSI-formatted terminal output."""

    def __init__(self, repo_path=None):
        self.repo = repo_path or os.path.expanduser("~/workspace/aegis-ternary")

    def _run(self, args: list[str], check=False) -> subprocess.CompletedProcess:
        """Run a git command safely (list form, no shell)."""
        return subprocess.run(
            ["git"] + args,
            cwd=self.repo,
            text=True,
            capture_output=True,
        )

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> str:
        """git status -sb, formatted with ANSI colors."""
        r = self._run(["status", "-sb"])
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"

        lines = []
        for line in r.stdout.splitlines():
            if line.startswith("##"):
                # Branch line
                lines.append(f"{CY}[GIT]{RS} {BL}{line}{RS}")
            elif line.startswith("A ") or line.startswith("M ") or line.startswith("R "):
                # Staged changes
                lines.append(f"  {GR}{line}{RS}")
            elif line.startswith(" M") or line.startswith(" D"):
                # Unstaged changes
                lines.append(f"  {RD}{line}{RS}")
            elif line.startswith("??"):
                # Untracked
                lines.append(f"  {YL}{line}{RS}")
            elif line.startswith("D "):
                # Staged deletion
                lines.append(f"  {RD}{line}{RS}")
            elif line.startswith("MM"):
                # Staged + unstaged modifications
                lines.append(f"  {YL}{line}{RS}")
            else:
                lines.append(f"  {line}")

        return "\n" + "\n".join(lines) + "\n"

    # ── Diff ──────────────────────────────────────────────────────────────

    def diff(self, path=None, cached=False) -> str:
        """git diff [--cached] [path], returns unified diff with colored +/- lines."""
        args = ["diff"]
        if cached:
            args.append("--cached")
        if path:
            args.append(path)
        r = self._run(args)
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"
        if not r.stdout.strip():
            label = "staged" if cached else "working tree"
            return f"\n{YL}[GIT]{RS} No {label} changes.\n"

        lines = []
        for line in r.stdout.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                lines.append(f"{WH}{line}{RS}")
            elif line.startswith("@@"):
                lines.append(f"{CY}{line}{RS}")
            elif line.startswith("+"):
                lines.append(f"{GR}{line}{RS}")
            elif line.startswith("-"):
                lines.append(f"{RD}{line}{RS}")
            elif line.startswith("diff "):
                lines.append(f"{BL}{line}{RS}")
            else:
                lines.append(line)

        return "\n" + "\n".join(lines) + "\n"

    # ── Log ───────────────────────────────────────────────────────────────

    def log(self, count=15, oneline=True) -> str:
        """git log --oneline -N, colored hashes + messages."""
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        r = self._run(args)
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"

        lines = [f"\n{CY}[GIT]{RS} Last {count} commits:\n"]
        for line in r.stdout.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                sha, msg = parts
                lines.append(f"  {YL}{sha}{RS} {msg}")
            else:
                lines.append(f"  {line}")
        lines.append("")
        return "\n".join(lines)

    # ── Branch ────────────────────────────────────────────────────────────

    def branch(self) -> str:
        """git branch -vv, highlight current branch in green."""
        r = self._run(["branch", "-vv"])
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"

        lines = [f"\n{CY}[GIT]{RS} Branches:\n"]
        for line in r.stdout.splitlines():
            if line.startswith("*"):
                lines.append(f"  {GR}{line}{RS}")
            else:
                lines.append(f"  {line}")
        lines.append("")
        return "\n".join(lines)

    # ── Add ───────────────────────────────────────────────────────────────

    def add(self, paths: list[str]) -> str:
        """git add <paths>, returns status after staging."""
        if not paths:
            return f"{YL}[GIT]{RS} No paths specified."
        r = self._run(["add"] + paths)
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"
        # Show status after staging
        return f"{GR}[GIT]{RS} Staged: {', '.join(paths)}\n" + self.status()

    # ── Commit ────────────────────────────────────────────────────────────

    def commit(self, message: str) -> str:
        """git commit -m <message>, returns result. Refuses empty message."""
        if not message.strip():
            return f"{YL}[GIT]{RS} Commit message cannot be empty."
        r = self._run(["commit", "-m", message])
        if r.returncode != 0:
            err = r.stderr.strip() or r.stdout.strip()
            return f"{RD}[GIT]{RS} {err}"
        # Format success output
        output = r.stdout.strip()
        return f"\n{GR}[TRIT_POS]{RS} {output}\n"

    # ── Stash ─────────────────────────────────────────────────────────────

    def stash(self, pop=False) -> str:
        """git stash / git stash pop."""
        args = ["stash", "pop"] if pop else ["stash"]
        r = self._run(args)
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"
        return f"\n{GR}[GIT]{RS} {r.stdout.strip()}\n"

    # ── Pull ──────────────────────────────────────────────────────────────

    def pull(self) -> str:
        """git pull, returns output."""
        r = self._run(["pull"])
        if r.returncode != 0:
            return f"{RD}[GIT]{RS} {r.stderr.strip()}"
        return f"\n{GR}[GIT]{RS} {r.stdout.strip()}\n"

    # ── Push ──────────────────────────────────────────────────────────────

    def push(self) -> str:
        """git push, returns output."""
        r = self._run(["push"])
        if r.returncode != 0:
            err = r.stderr.strip()
            # git push writes progress to stderr even on success
            if r.returncode == 0 or "Everything up-to-date" in err:
                return f"\n{GR}[GIT]{RS} {err}\n"
            return f"{RD}[GIT]{RS} {err}"
        out = r.stdout.strip() or r.stderr.strip()
        return f"\n{GR}[GIT]{RS} {out}\n"

    # ── Show File Diff (for visual diff viewer) ───────────────────────────

    def show_file_diff(self, path: str) -> tuple:
        """Returns (old_content, new_content, unified_diff) for a single file.
        old_content = HEAD version via `git show HEAD:<path>`
        new_content = working tree version via open(path).read()
        unified_diff = `git diff <path>`
        """
        # Get relative path for git commands
        abs_path = os.path.abspath(path)
        try:
            rel_path = os.path.relpath(abs_path, self.repo)
        except ValueError:
            rel_path = abs_path

        # HEAD version
        r_old = self._run(["show", f"HEAD:{rel_path}"])
        old_content = r_old.stdout if r_old.returncode == 0 else ""

        # Working tree version
        try:
            new_content = open(abs_path, "r").read()
        except (FileNotFoundError, PermissionError):
            new_content = ""

        # Unified diff
        r_diff = self._run(["diff", rel_path])
        unified_diff = r_diff.stdout if r_diff.returncode == 0 else ""

        return (old_content, new_content, unified_diff)

    # ── Changed Files List ────────────────────────────────────────────────

    def diff_files(self) -> list[dict]:
        """Returns list of changed files with status.
        Returns: [{'path': ..., 'status': 'M'}, ...]
        """
        files = []

        # Unstaged changes
        r = self._run(["diff", "--name-status"])
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    files.append({"status": parts[0], "path": parts[1]})

        # Staged changes
        r = self._run(["diff", "--cached", "--name-status"])
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    entry = {"status": parts[0] + " (staged)", "path": parts[1]}
                    # Avoid duplicates
                    if not any(f["path"] == entry["path"] for f in files):
                        files.append(entry)

        # Untracked files
        r = self._run(["ls-files", "--others", "--exclude-standard"])
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                path = line.strip()
                if path and not any(f["path"] == path for f in files):
                    files.append({"status": "?", "path": path})

        return files
