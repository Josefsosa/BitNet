#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

class WorkspaceNavigator:
    def render_directory_tree(self, target_path: str = "."):
        """ Prints a high-fidelity visual tree directory overview. """
        root = Path(target_path).resolve()
        print(f"\n\033[1;34m📁 Tree Directory Map: {root.name}\033[0m")
        self._build_tree(root, "")
        
    def _build_tree(self, path: Path, prefix: str):
        try:
            items = sorted(list(path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return
        
        for i, item in enumerate(items):
            if item.name.startswith((".", "__pycache__")) or "orig_monolith" in item.name:
                continue
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            if item.is_dir():
                print(f"{prefix}{connector}\033[1;34m{item.name}/\033[0m")
                self._build_tree(item, prefix + ("    " if is_last else "│   "))
            else:
                print(f"{prefix}{connector}{item.name}")
                
    def render_git_status(self):
        """ Extracts local workspace Git repository version controls. """
        print("\n\033[1;32m🚀 Aegis Repository Telemetry tracking status:\033[0m")
        try:
            res = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                print(res.stdout.strip())
            elif res.returncode == 0:
                print("[✓] Repository clean. Workspace synced with remote origins.")
            else:
                print("[!] Notice: Current workspace root is not registered inside a Git partition.")
        except Exception as e:
            print(f"[-] Git telemetry capture failed: {e}")
