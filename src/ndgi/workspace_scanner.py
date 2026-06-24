"""
NDGi WorkspaceScanner — scan project tree, find files, inject structure into prompts.
Prevents hallucinated paths by giving the AI accurate project layout awareness.
"""
import json
import os
import fnmatch
import time
from pathlib import Path
from typing import Optional

from src.ndgi.ndgi_init import LOG_DIR

# Directories to always skip during scanning
SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
    '.mypy_cache', '.pytest_cache', '.tox', '.eggs', 'dist', 'build',
    '.next', '.nuxt', '.cache', '.parcel-cache', 'coverage',
    '.idea', '.vscode', '.DS_Store', 'target', 'out',
}

# Max depth to prevent runaway scanning
MAX_DEPTH = 8
MAX_FILES = 5000


class WorkspaceScanner:
    """Scan and track project file structure."""

    def __init__(self, tree_path: str = None):
        self.tree_path = tree_path or str(LOG_DIR / "workspace_tree.json")
        self.tree: dict = {}
        self.root_path: str = ""
        self.scan_time: float = 0
        self.file_count: int = 0
        self._load()

    def _load(self):
        """Load cached tree from disk."""
        try:
            if os.path.exists(self.tree_path):
                with open(self.tree_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tree = data.get("tree", {})
                    self.root_path = data.get("root", "")
                    self.scan_time = data.get("scan_time", 0)
                    self.file_count = data.get("file_count", 0)
        except (json.JSONDecodeError, OSError):
            self.tree = {}

    def _save(self):
        """Persist tree to disk."""
        os.makedirs(os.path.dirname(self.tree_path), exist_ok=True)
        data = {
            "root": self.root_path,
            "tree": self.tree,
            "scan_time": self.scan_time,
            "file_count": self.file_count,
            "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(self.tree_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def scan(self, root_path: str, max_depth: int = MAX_DEPTH) -> dict:
        """Scan project directory and build file tree.

        Returns the tree dict: {name: subtree_or_None}.
        Files have value None, directories have nested dicts.
        """
        root = Path(root_path).expanduser().resolve()
        if not root.is_dir():
            return {}

        self.root_path = str(root)
        self.file_count = 0
        start = time.time()
        self.tree = self._scan_dir(root, 0, max_depth)
        self.scan_time = round(time.time() - start, 3)
        self._save()
        return self.tree

    def _scan_dir(self, path: Path, depth: int, max_depth: int) -> dict:
        """Recursively scan a directory."""
        if depth >= max_depth or self.file_count >= MAX_FILES:
            return {}

        result = {}
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return {}

        for entry in entries:
            name = entry.name
            if name.startswith('.') and name not in ('.env',):
                continue
            if entry.is_dir():
                if name in SKIP_DIRS:
                    continue
                subtree = self._scan_dir(entry, depth + 1, max_depth)
                if subtree:  # only include non-empty dirs
                    result[name + "/"] = subtree
            elif entry.is_file():
                if self.file_count >= MAX_FILES:
                    break
                self.file_count += 1
                result[name] = None
        return result

    def get_tree(self) -> dict:
        """Get current cached tree."""
        return self.tree

    def find_file(self, pattern: str) -> list[str]:
        """Find files matching a glob-like pattern in the scanned tree."""
        matches = []
        self._find_recursive(self.tree, self.root_path, pattern, matches)
        return matches

    def _find_recursive(self, tree: dict, prefix: str, pattern: str,
                        matches: list):
        """Recursively search tree for pattern matches."""
        for name, subtree in tree.items():
            full = os.path.join(prefix, name.rstrip('/'))
            if subtree is None:
                # It's a file
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    matches.append(full)
            else:
                # It's a directory
                if fnmatch.fnmatch(name.rstrip('/').lower(), pattern.lower()):
                    matches.append(full)
                self._find_recursive(subtree, full, pattern, matches)

    def find_files_by_type(self, ext: str) -> list[str]:
        """Find all files with a given extension."""
        if not ext.startswith('.'):
            ext = '.' + ext
        return self.find_file(f"*{ext}")

    def update_tree(self) -> None:
        """Rescan the last-scanned root directory."""
        if self.root_path:
            self.scan(self.root_path)

    def get_file_count(self) -> int:
        """Total files in the scanned tree."""
        return self.file_count

    def format_tree(self, max_depth: int = 3) -> str:
        """Format tree as a visual string for terminal display."""
        if not self.tree:
            return "[No tree scanned. Use: /scan <path>]"
        lines = [f"Project Structure ({self.file_count} files):"]
        self._format_recursive(self.tree, "", lines, 0, max_depth)
        if self.scan_time:
            lines.append(f"\nScanned in {self.scan_time}s from {self.root_path}")
        return "\n".join(lines)

    def _format_recursive(self, tree: dict, prefix: str, lines: list,
                          depth: int, max_depth: int):
        """Build tree display lines."""
        if depth >= max_depth:
            remaining = self._count_entries(tree)
            if remaining > 0:
                lines.append(f"{prefix}... ({remaining} more entries)")
            return

        items = list(tree.items())
        for i, (name, subtree) in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "

            if subtree is None:
                lines.append(f"{prefix}{connector}{name}")
            else:
                child_count = self._count_entries(subtree)
                lines.append(f"{prefix}{connector}{name} ({child_count} entries)")
                self._format_recursive(subtree, prefix + child_prefix,
                                       lines, depth + 1, max_depth)

    def _count_entries(self, tree: dict) -> int:
        """Count total entries (files + dirs) in a subtree."""
        count = 0
        for name, subtree in tree.items():
            count += 1
            if subtree is not None:
                count += self._count_entries(subtree)
        return count

    def prompt_block(self) -> str:
        """Format compact project structure for system prompt injection."""
        if not self.tree:
            return ""
        lines = [f"PROJECT STRUCTURE ({self.file_count} files):"]
        self._prompt_recursive(self.tree, "  ", lines, 0, max_depth=2)
        return "\n".join(lines)

    def _prompt_recursive(self, tree: dict, prefix: str, lines: list,
                          depth: int, max_depth: int):
        """Build compact tree for prompt injection."""
        if depth >= max_depth:
            count = self._count_entries(tree)
            if count > 0:
                lines.append(f"{prefix}... ({count} more)")
            return

        dirs = [(n, s) for n, s in tree.items() if s is not None]
        files = [n for n, s in tree.items() if s is None]

        for name, subtree in dirs:
            lines.append(f"{prefix}{name}")
            self._prompt_recursive(subtree, prefix + "  ", lines,
                                   depth + 1, max_depth)

        if files:
            if len(files) <= 5:
                for f in files:
                    lines.append(f"{prefix}{f}")
            else:
                for f in files[:3]:
                    lines.append(f"{prefix}{f}")
                lines.append(f"{prefix}... (+{len(files)-3} files)")

    def notify_file_created(self, path: str):
        """Update tree after a file is created."""
        self.update_tree()

    def notify_file_deleted(self, path: str):
        """Update tree after a file is deleted."""
        self.update_tree()

    def notify_file_modified(self, path: str):
        """No tree change needed for modifications (same structure)."""
        pass
