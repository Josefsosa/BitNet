"""
NDGi FileReader — read, analyze, search, and summarize files for AI context injection.
Supports single/multi-file reads, line-context windows, metadata, and pattern search.
"""
import os
import re
import mimetypes
from pathlib import Path
from typing import Optional


# File size limits
MAX_FILE_SIZE = 512_000       # 512 KB — refuse binary/huge files
MAX_DISPLAY_LINES = 2000      # Max lines for full display
CHUNK_SIZE = 500              # Lines per chunk for large files
CONTEXT_LINES_DEFAULT = 5     # Default context window around a target line

# Text file extensions (non-exhaustive, used as fallback)
TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.rs', '.go', '.java', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.lua',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.html', '.css', '.scss', '.less', '.xml', '.svg', '.json', '.yaml',
    '.yml', '.toml', '.ini', '.cfg', '.conf', '.env', '.properties',
    '.md', '.rst', '.txt', '.log', '.csv', '.tsv',
    '.sql', '.graphql', '.proto', '.dockerfile', '.makefile',
    '.gitignore', '.editorconfig', '.eslintrc', '.prettierrc',
}


class FileReader:
    """Read and analyze files for injection into AI context."""

    def __init__(self):
        self.loaded_files: dict[str, str] = {}  # path -> content cache

    @staticmethod
    def _is_text_file(path: Path) -> bool:
        """Check if a file is likely a text file."""
        ext = path.suffix.lower()
        if ext in TEXT_EXTENSIONS:
            return True
        if path.name.lower() in ('makefile', 'dockerfile', 'rakefile',
                                  'gemfile', 'procfile', 'cmakelists.txt'):
            return True
        mime, _ = mimetypes.guess_type(str(path))
        if mime and mime.startswith('text/'):
            return True
        # Try reading first 512 bytes for binary detection
        try:
            with open(path, 'rb') as f:
                chunk = f.read(512)
                if b'\x00' in chunk:
                    return False
                return True
        except (OSError, PermissionError):
            return False

    def read_file(self, path: str) -> dict:
        """Read a file and return its content with metadata.

        Returns dict with keys: content, path, lines, size, type, error
        """
        p = Path(path).expanduser().resolve()
        result = {"path": str(p), "content": "", "lines": 0,
                  "size": 0, "type": "", "error": None}

        if not p.exists():
            result["error"] = f"File not found: {p}"
            return result
        if not p.is_file():
            result["error"] = f"Not a file: {p}"
            return result
        if not self._is_text_file(p):
            result["error"] = f"Binary file: {p}"
            result["type"] = "binary"
            return result

        stat = p.stat()
        if stat.st_size > MAX_FILE_SIZE:
            result["error"] = f"File too large: {stat.st_size:,} bytes (max {MAX_FILE_SIZE:,})"
            result["size"] = stat.st_size
            return result

        try:
            text = p.read_text(errors='replace')
            lines = text.splitlines()
            result["content"] = text
            result["lines"] = len(lines)
            result["size"] = stat.st_size
            result["type"] = p.suffix.lstrip('.') or "text"
            self.loaded_files[str(p)] = text
            return result
        except (OSError, PermissionError) as e:
            result["error"] = str(e)
            return result

    def read_with_context(self, path: str, line_num: int,
                          context_lines: int = CONTEXT_LINES_DEFAULT) -> dict:
        """Read file and return lines around a specific line number.

        Returns dict with: content, start_line, end_line, target_line, path, error
        """
        file_data = self.read_file(path)
        if file_data["error"]:
            return {"error": file_data["error"], "path": path,
                    "content": "", "start_line": 0, "end_line": 0,
                    "target_line": line_num}

        lines = file_data["content"].splitlines()
        total = len(lines)
        if line_num < 1 or line_num > total:
            return {"error": f"Line {line_num} out of range (1-{total})",
                    "path": path, "content": "", "start_line": 0,
                    "end_line": 0, "target_line": line_num}

        start = max(0, line_num - 1 - context_lines)
        end = min(total, line_num + context_lines)
        selected = lines[start:end]

        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            marker = " >> " if i == line_num else "    "
            numbered.append(f"{i:4d}{marker}{line}")

        return {
            "path": path,
            "content": "\n".join(numbered),
            "start_line": start + 1,
            "end_line": end,
            "target_line": line_num,
            "total_lines": total,
            "error": None,
        }

    def read_multiple(self, paths: list[str]) -> dict[str, dict]:
        """Read multiple files at once. Returns {path: read_result}."""
        results = {}
        for path in paths:
            results[path] = self.read_file(path)
        return results

    def get_file_metadata(self, path: str) -> dict:
        """Get file info: size, lines, type, modified, permissions."""
        p = Path(path).expanduser().resolve()
        meta = {"path": str(p), "exists": p.exists(), "error": None}

        if not p.exists():
            meta["error"] = f"File not found: {p}"
            return meta

        stat = p.stat()
        meta["size"] = stat.st_size
        meta["modified"] = stat.st_mtime
        meta["type"] = p.suffix.lstrip('.') or "unknown"
        meta["is_text"] = self._is_text_file(p) if p.is_file() else False
        meta["is_dir"] = p.is_dir()
        meta["name"] = p.name

        if p.is_file() and meta["is_text"] and stat.st_size < MAX_FILE_SIZE:
            try:
                text = p.read_text(errors='replace')
                meta["lines"] = len(text.splitlines())
            except (OSError, PermissionError):
                meta["lines"] = 0
        else:
            meta["lines"] = 0
        return meta

    def search_in_file(self, path: str, pattern: str) -> list[dict]:
        """Find pattern matches in a file. Returns list of {line_num, line, match}."""
        file_data = self.read_file(path)
        if file_data["error"]:
            return []

        matches = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Fall back to literal search
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        for i, line in enumerate(file_data["content"].splitlines(), 1):
            m = regex.search(line)
            if m:
                matches.append({
                    "line_num": i,
                    "line": line.rstrip(),
                    "match": m.group(),
                })
        return matches

    def get_file_summary(self, path: str) -> str:
        """Generate a 1-2 line summary of what a file does."""
        file_data = self.read_file(path)
        if file_data["error"]:
            return f"Error: {file_data['error']}"

        p = Path(path)
        lines = file_data["content"].splitlines()
        total = len(lines)
        ext = file_data["type"]

        # Extract key info
        imports = []
        classes = []
        functions = []
        docstring = ""

        for line in lines[:50]:  # scan first 50 lines
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                imports.append(stripped)
            elif stripped.startswith('class '):
                m = re.match(r'class\s+(\w+)', stripped)
                if m:
                    classes.append(m.group(1))
            elif stripped.startswith('def '):
                m = re.match(r'def\s+(\w+)', stripped)
                if m:
                    functions.append(m.group(1))
            elif stripped.startswith(('"""', "'''")):
                docstring = stripped.strip('"\' ')
            elif stripped.startswith(('#', '//', '/*')) and not docstring:
                docstring = stripped.lstrip('#/ *').strip()

        # Build summary
        parts = [f"{p.name} ({total} lines, {ext})"]
        if docstring and len(docstring) > 5:
            parts.append(f"  {docstring[:100]}")
        if classes:
            parts.append(f"  Classes: {', '.join(classes[:5])}")
        if functions:
            fn_list = ', '.join(functions[:8])
            if len(functions) > 8:
                fn_list += f" (+{len(functions)-8} more)"
            parts.append(f"  Functions: {fn_list}")
        if imports:
            parts.append(f"  Imports: {len(imports)} modules")

        return "\n".join(parts)

    def format_for_context(self, path: str, max_lines: int = MAX_DISPLAY_LINES) -> str:
        """Format file content for injection into LLM context."""
        file_data = self.read_file(path)
        if file_data["error"]:
            return f"[File Error: {file_data['error']}]"

        lines = file_data["content"].splitlines()
        total = len(lines)
        p = Path(path).name

        if total <= max_lines:
            numbered = [f"{i:4d}  {line}" for i, line in enumerate(lines, 1)]
            header = f"FILE: {p} ({total} lines, {file_data['type']})"
            return f"{header}\n{'─'*60}\n" + "\n".join(numbered)
        else:
            # Chunk: show first and last portions
            first = lines[:max_lines // 2]
            last = lines[-(max_lines // 2):]
            numbered_first = [f"{i:4d}  {line}" for i, line in enumerate(first, 1)]
            skip_start = max_lines // 2 + 1
            skip_end = total - max_lines // 2
            numbered_last = [f"{i:4d}  {line}" for i, line
                             in enumerate(last, total - max_lines // 2 + 1)]
            header = f"FILE: {p} ({total} lines, {file_data['type']}) [CHUNKED]"
            return (f"{header}\n{'─'*60}\n"
                    + "\n".join(numbered_first)
                    + f"\n  ... [{skip_end - skip_start + 1} lines omitted] ...\n"
                    + "\n".join(numbered_last))

    def get_loaded_files(self) -> list[str]:
        """Return list of file paths currently loaded in cache."""
        return list(self.loaded_files.keys())

    def clear_cache(self):
        """Clear the loaded files cache."""
        self.loaded_files.clear()
