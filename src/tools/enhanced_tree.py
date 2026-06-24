"""
Aegis Enhanced Directory Tree — depth limits, glob filtering,
file sizes, and summary statistics.
"""

import os
import fnmatch

WORKSPACE_ROOT = os.path.expanduser("~/workspace/aegis-ternary")


class EnhancedTree:
    IGNORE = {'.git', '__pycache__', 'node_modules', '.venv', 'build',
              'dist', 'orig_monolith', '.next', 'coverage', '.mypy_cache'}

    def render(self, target_path=".", depth=3, pattern=None, show_size=False):
        """Render an ASCII tree with box-drawing characters."""
        CY = "\033[1;36m"; GR = "\033[1;32m"; DM = "\033[0;36m"; RS = "\033[0m"

        # Resolve path
        if not os.path.isabs(target_path):
            target_path = os.path.join(WORKSPACE_ROOT, target_path)
        target_path = os.path.abspath(target_path)

        if not os.path.isdir(target_path):
            print(f"\033[1;31m[Error]\033[0m Not a directory: {target_path}")
            return

        rel_root = os.path.relpath(target_path, WORKSPACE_ROOT)
        if rel_root == ".":
            rel_root = os.path.basename(target_path)

        print(f"\n{CY}╔══ TREE ══╗{RS}  {GR}{rel_root}/{RS}  (depth={depth})\n")

        stats = {"dirs": 0, "files": 0, "total_bytes": 0}
        lines = []
        self._build(target_path, "", 0, depth, pattern, show_size, stats, lines)

        for line in lines:
            print(line)

        # Summary
        size_str = self._human_size(stats["total_bytes"])
        print(f"\n{DM}  {stats['dirs']} directories, {stats['files']} files"
              f" ({size_str} total){RS}\n")

    def _build(self, path, prefix, current_depth, max_depth,
               pattern, show_size, stats, lines):
        """Recursive tree builder with depth guard."""
        if current_depth >= max_depth:
            return

        GR = "\033[1;32m"; CY = "\033[1;36m"
        YL = "\033[1;33m"; DM = "\033[0;36m"; RS = "\033[0m"

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            lines.append(f"{prefix}└── \033[1;31m[permission denied]\033[0m")
            return

        # Separate dirs and files, filter ignored
        dirs = []
        files = []
        for e in entries:
            full = os.path.join(path, e)
            if e in self.IGNORE:
                continue
            if e.startswith('.') and e != '.env.example':
                continue
            if os.path.isdir(full):
                dirs.append(e)
            else:
                if pattern and not fnmatch.fnmatch(e, pattern):
                    continue
                files.append(e)

        all_items = dirs + files
        total = len(all_items)

        for i, name in enumerate(all_items):
            is_last = (i == total - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            full_path = os.path.join(path, name)

            if os.path.isdir(full_path):
                stats["dirs"] += 1
                lines.append(f"{prefix}{connector}{CY}{name}/{RS}")
                self._build(full_path, child_prefix, current_depth + 1,
                           max_depth, pattern, show_size, stats, lines)
            else:
                stats["files"] += 1
                size_info = ""
                try:
                    fsize = os.path.getsize(full_path)
                    stats["total_bytes"] += fsize
                    if show_size:
                        size_info = f"  {DM}({self._human_size(fsize)}){RS}"
                except OSError:
                    pass

                # Color by extension
                ext = os.path.splitext(name)[1]
                if ext in ('.py',):
                    clr = GR
                elif ext in ('.js', '.jsx', '.ts', '.tsx'):
                    clr = YL
                elif ext in ('.json', '.md', '.txt'):
                    clr = DM
                else:
                    clr = ""
                reset = RS if clr else ""
                lines.append(f"{prefix}{connector}{clr}{name}{reset}{size_info}")

    @staticmethod
    def _human_size(nbytes):
        """Convert bytes to human-readable: '1.2K', '3.4M', etc."""
        if nbytes < 1024:
            return f"{nbytes}B"
        elif nbytes < 1024 * 1024:
            return f"{nbytes / 1024:.1f}K"
        elif nbytes < 1024 * 1024 * 1024:
            return f"{nbytes / (1024 * 1024):.1f}M"
        else:
            return f"{nbytes / (1024 * 1024 * 1024):.1f}G"
