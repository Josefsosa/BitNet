"""
NDGi ErrorDiagnoser — parse errors, auto-load context, diagnose, suggest fixes.
Supports Python tracebacks, Node/JS errors, build errors, and test failures.
"""
import re
import os
import time
from pathlib import Path
from typing import Optional

from src.ndgi.file_reader import FileReader


# File+line patterns: extract location from traceback/stacktrace
FILE_LINE_PATTERNS = [
    (r'File "([^"]+)", line (\d+)', 'python_traceback'),
    (r'at .+\((.+):(\d+):\d+\)', 'node_stacktrace'),
    (r'FAIL(?:ED)?[:\s]+(.+\.(?:py|js|ts|test\.\w+)):?(\d+)', 'test_failure'),
    (r'(.+\.(?:js|ts|jsx|tsx)):(\d+)', 'js_file_line'),
    (r'error: (.+\.(?:c|cpp|h|hpp)):(\d+)', 'c_error'),
    (r'CMake Error at (.+):(\d+)', 'cmake_error'),
]

# Error type patterns: identify the error kind and message
ERROR_TYPE_PATTERNS = [
    (r'(ReferenceError|TypeError|SyntaxError|RangeError): (.+)', 'js_error'),
    (r'(\w+Error): (.+)', 'python_error'),
    (r'(\w+Exception): (.+)', 'python_exception'),
    (r'AssertionError: (.+)', 'assertion_error'),
    (r'error\[E\d+\]: (.+)', 'rust_error'),
    (r'ERROR[:\s]+(.+)', 'generic_error'),
]

# Import patterns for finding related files
IMPORT_PATTERNS = [
    # Python
    (r'^from\s+([\w.]+)\s+import', 'python'),
    (r'^import\s+([\w.]+)', 'python'),
    # JavaScript/TypeScript
    (r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", 'js'),
    # Rust
    (r'^use\s+([\w:]+)', 'rust'),
    # C/C++
    (r'^#include\s*[<"]([^>"]+)[>"]', 'c'),
]

CONTEXT_LINES = 10  # Lines to show around the error location


class ErrorDiagnoser:
    """Parse error output, auto-load context, and diagnose issues."""

    def __init__(self):
        self.file_reader = FileReader()
        self.error_history: list[dict] = []
        self._last_error: dict | None = None

    def parse_error(self, output: str) -> dict:
        """Parse error output, extract file, line, type, and message.

        Uses two-pass parsing:
        1. Find file + line number from traceback/stacktrace patterns
        2. Find error type + message from error type patterns

        Returns dict with: error_type, message, file, line, raw, traceback_lines
        """
        result = {
            "error_type": "unknown",
            "message": "",
            "file": None,
            "line": None,
            "raw": output,
            "traceback_lines": [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        lines = output.strip().splitlines()
        result["traceback_lines"] = lines

        # Pass 1: Extract file + line from traceback patterns
        for pattern, loc_type in FILE_LINE_PATTERNS:
            for line in lines:
                m = re.search(pattern, line)
                if m:
                    groups = m.groups()
                    if not result["file"] and groups:
                        # Skip node_modules paths, prefer app code
                        candidate = groups[0]
                        if 'node_modules' not in candidate:
                            result["file"] = candidate
                            if len(groups) > 1 and groups[1]:
                                try:
                                    result["line"] = int(groups[1])
                                except ValueError:
                                    pass
                            if not result["error_type"] or result["error_type"] == "unknown":
                                result["error_type"] = loc_type
            if result["file"]:
                break

        # Pass 2: Extract error type + message
        for pattern, error_type in ERROR_TYPE_PATTERNS:
            for line in reversed(lines):
                m = re.search(pattern, line)
                if m:
                    result["error_type"] = error_type
                    result["message"] = m.groups()[-1] if m.groups() else line.strip()
                    break
            if result["error_type"] != "unknown":
                break

        # Fallback message from last line
        if not result["message"] and lines:
            result["message"] = lines[-1].strip()

        # Store in history
        self._last_error = result
        self.error_history.append(result)
        if len(self.error_history) > 50:
            self.error_history = self.error_history[-50:]

        return result

    def extract_file_path(self, error: str) -> str | None:
        """Find the file path mentioned in an error string."""
        parsed = self.parse_error(error)
        return parsed.get("file")

    def extract_line_number(self, error: str) -> int | None:
        """Find the line number from an error traceback."""
        parsed = self.parse_error(error)
        return parsed.get("line")

    def get_error_context(self, file: str, line: int,
                          context: int = CONTEXT_LINES) -> dict:
        """Read the file and return lines around the error location.

        Returns dict with: content, file, line, start, end, error
        """
        result = self.file_reader.read_with_context(file, line, context)
        return result

    def get_related_files(self, file: str) -> list[str]:
        """Find imports and related files from the given source file."""
        data = self.file_reader.read_file(file)
        if data["error"]:
            return []

        related = []
        base_dir = str(Path(file).parent)

        for line in data["content"].splitlines():
            stripped = line.strip()
            for pattern, lang in IMPORT_PATTERNS:
                m = re.match(pattern, stripped)
                if not m:
                    continue
                import_path = m.group(1)

                if lang == 'python':
                    # Convert dotted path to file path
                    parts = import_path.split('.')
                    candidates = [
                        os.path.join(base_dir, *parts) + '.py',
                        os.path.join(base_dir, *parts, '__init__.py'),
                        os.path.join(os.path.dirname(base_dir), *parts) + '.py',
                    ]
                elif lang == 'js':
                    if import_path.startswith('.'):
                        candidates = [
                            os.path.join(base_dir, import_path),
                            os.path.join(base_dir, import_path + '.js'),
                            os.path.join(base_dir, import_path + '.ts'),
                            os.path.join(base_dir, import_path + '.tsx'),
                            os.path.join(base_dir, import_path, 'index.js'),
                            os.path.join(base_dir, import_path, 'index.ts'),
                        ]
                    else:
                        candidates = []
                elif lang == 'c':
                    candidates = [
                        os.path.join(base_dir, import_path),
                    ]
                else:
                    candidates = []

                for c in candidates:
                    if os.path.isfile(c) and c not in related:
                        related.append(c)
                        break

        return related

    def diagnose(self, error_output: str) -> dict:
        """Full diagnosis: parse error, load context, find related files.

        Returns dict with: parsed, context, related_files, diagnosis_prompt
        """
        parsed = self.parse_error(error_output)

        context = None
        related_files = []
        loaded_context = {}

        if parsed["file"] and parsed["line"]:
            context = self.get_error_context(parsed["file"], parsed["line"])
            related_files = self.get_related_files(parsed["file"])

            # Load related file summaries
            for rf in related_files[:3]:  # Limit to 3 related files
                summary = self.file_reader.get_file_summary(rf)
                loaded_context[rf] = summary

        elif parsed["file"]:
            # Have file but no line number — load full file summary
            context = {"content": self.file_reader.get_file_summary(parsed["file"]),
                       "error": None}
            related_files = self.get_related_files(parsed["file"])

        return {
            "parsed": parsed,
            "context": context,
            "related_files": related_files,
            "loaded_context": loaded_context,
            "diagnosis_prompt": self._build_diagnosis_prompt(parsed, context,
                                                            related_files,
                                                            loaded_context),
        }

    def _build_diagnosis_prompt(self, parsed: dict, context: dict | None,
                                related_files: list[str],
                                loaded_context: dict) -> str:
        """Build a diagnosis prompt for the LLM."""
        parts = ["DIAGNOSE THIS ERROR:"]
        parts.append(f"\nError Type: {parsed['error_type']}")
        parts.append(f"Message: {parsed['message']}")

        if parsed["file"]:
            parts.append(f"File: {parsed['file']}")
        if parsed["line"]:
            parts.append(f"Line: {parsed['line']}")

        if parsed["traceback_lines"]:
            tb = "\n".join(parsed["traceback_lines"][-15:])  # Last 15 lines
            parts.append(f"\nFull traceback:\n{tb}")

        if context and context.get("content"):
            parts.append(f"\nCode around error:\n{context['content']}")

        if loaded_context:
            parts.append("\nRelated files:")
            for path, summary in loaded_context.items():
                parts.append(f"  {summary}")

        parts.append("\nProvide:")
        parts.append("1. Root cause analysis")
        parts.append("2. Specific fix (code change)")
        parts.append("3. Steps to verify the fix")

        return "\n".join(parts)

    def get_last_error(self) -> dict | None:
        """Return the most recent parsed error."""
        return self._last_error

    def get_error_history(self, limit: int = 10) -> list[dict]:
        """Return recent error history."""
        return self.error_history[-limit:]

    def format_error_summary(self, parsed: dict) -> str:
        """Format a parsed error for terminal display."""
        lines = []
        lines.append(f"  Error: {parsed['error_type']}")
        if parsed["file"]:
            lines.append(f"  File:  {parsed['file']}")
        if parsed["line"]:
            lines.append(f"  Line:  {parsed['line']}")
        lines.append(f"  Msg:   {parsed['message'][:120]}")
        return "\n".join(lines)

    def format_diagnosis(self, diagnosis: dict) -> str:
        """Format full diagnosis for terminal display."""
        parsed = diagnosis["parsed"]
        lines = [
            "\nERROR DIAGNOSIS",
            "-" * 50,
        ]
        lines.append(f"  Type:    {parsed['error_type']}")
        lines.append(f"  Message: {parsed['message'][:120]}")

        if parsed["file"]:
            lines.append(f"  File:    {parsed['file']}")
        if parsed["line"]:
            lines.append(f"  Line:    {parsed['line']}")

        ctx = diagnosis.get("context")
        if ctx and ctx.get("content") and not ctx.get("error"):
            lines.append(f"\n  Code context:")
            for cl in ctx["content"].splitlines()[:15]:
                lines.append(f"    {cl}")

        related = diagnosis.get("related_files", [])
        if related:
            lines.append(f"\n  Related files ({len(related)}):")
            for rf in related[:5]:
                lines.append(f"    {rf}")

        lines.append("")
        return "\n".join(lines)
