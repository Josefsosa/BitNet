"""
Aegis AI Change Audit Trail — Hash-chained, tamper-evident log
of every AI file modification.

Every create/patch operation gets recorded with:
  - before/after content hashes
  - chain hash linking to previous entry (tamper-evident)
  - TDD results, command context, timestamps
"""

import os
import json
import hashlib
import time
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.expanduser("~/workspace/aegis-ternary")
AUDIT_FILE = os.path.join(WORKSPACE_ROOT, "docs/workon/runner_logs/ai_audit_trail.json")


class AuditTrail:
    def __init__(self, audit_path=None):
        self.path = audit_path or AUDIT_FILE
        self.entries = {}
        self.load()

    def load(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            if os.path.exists(self.path):
                self.entries = json.load(open(self.path))
        except (json.JSONDecodeError, IOError):
            self.entries = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.entries, f, indent=2)
        except IOError:
            pass

    def _next_id(self):
        n = len(self.entries) + 1
        return f"AUD-{n:04d}"

    def _hash_content(self, content):
        if content is None:
            return None
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]

    def _chain_hash(self, entry_json):
        """Compute chain hash: sha256(prev_chain_hash + entry_json)."""
        prev_hash = "genesis"
        if self.entries:
            last_key = list(self.entries.keys())[-1]
            prev_hash = self.entries[last_key].get("chain_hash", "genesis")
        raw = prev_hash + entry_json
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _relative_path(self, path):
        try:
            return os.path.relpath(path, WORKSPACE_ROOT)
        except ValueError:
            return path

    def _session_id(self):
        return time.strftime("%Y%m%d_%H%M%S")

    def record_create(self, path, content, triggered_by="engine",
                      command="", trit=1, tdd_passed=True, warnings=None):
        entry_id = self._next_id()
        entry = {
            "id": entry_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "operation": "create",
            "path": os.path.abspath(path),
            "relative_path": self._relative_path(path),
            "before_hash": None,
            "after_hash": self._hash_content(content),
            "before_size": 0,
            "after_size": len(content) if content else 0,
            "triggered_by": triggered_by,
            "command": command,
            "trit_result": trit,
            "tdd_passed": tdd_passed,
            "tdd_warnings": warnings or [],
            "content_preview": (content[:200] if content else ""),
            "diff_summary": f"+{content.count(chr(10)) + 1} lines" if content else "+0 lines",
            "session_id": self._session_id(),
        }
        # Compute chain hash (without chain_hash field itself)
        entry_json = json.dumps(entry, sort_keys=True)
        entry["chain_hash"] = self._chain_hash(entry_json)

        self.entries[entry_id] = entry
        self.save()
        return entry_id

    def record_patch(self, path, before_content, after_content,
                     search="", replace="", triggered_by="engine",
                     command="", trit=1, tdd_passed=True, warnings=None):
        entry_id = self._next_id()

        before_lines = before_content.count("\n") + 1 if before_content else 0
        after_lines = after_content.count("\n") + 1 if after_content else 0
        diff_lines = after_lines - before_lines
        diff_sign = "+" if diff_lines >= 0 else ""

        entry = {
            "id": entry_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "operation": "patch",
            "path": os.path.abspath(path),
            "relative_path": self._relative_path(path),
            "before_hash": self._hash_content(before_content),
            "after_hash": self._hash_content(after_content),
            "before_size": len(before_content) if before_content else 0,
            "after_size": len(after_content) if after_content else 0,
            "triggered_by": triggered_by,
            "command": command,
            "trit_result": trit,
            "tdd_passed": tdd_passed,
            "tdd_warnings": warnings or [],
            "content_preview": (replace[:200] if replace else ""),
            "diff_summary": f"{diff_sign}{diff_lines} lines",
            "session_id": self._session_id(),
        }
        entry_json = json.dumps(entry, sort_keys=True)
        entry["chain_hash"] = self._chain_hash(entry_json)

        self.entries[entry_id] = entry
        self.save()
        return entry_id

    def verify_chain(self):
        """Walk the chain and validate all hashes. Returns (valid, bad_id_or_None)."""
        prev_hash = "genesis"
        for entry_id, entry in self.entries.items():
            stored_chain = entry.get("chain_hash", "")
            # Rebuild entry without chain_hash
            entry_copy = {k: v for k, v in entry.items() if k != "chain_hash"}
            entry_json = json.dumps(entry_copy, sort_keys=True)
            raw = prev_hash + entry_json
            expected = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            if stored_chain != expected:
                return (False, entry_id)
            prev_hash = stored_chain
        return (True, None)

    def print_trail(self, last_n=20):
        """Print the last N audit entries."""
        CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
        RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

        entries = list(self.entries.items())
        if not entries:
            print(f"\n{YL}[AUDIT]{RS} No entries recorded yet.\n")
            return

        shown = entries[-last_n:]
        print(f"\n{CY}╔══ AI AUDIT TRAIL ══╗{RS}  ({len(entries)} total, showing last {len(shown)})\n")

        for entry_id, e in shown:
            op = e["operation"].upper()
            trit = e["trit_result"]
            trit_sym = f"{GR}✓{RS}" if trit == 1 else f"{RD}✗{RS}" if trit == -1 else f"{YL}○{RS}"
            op_clr = GR if op == "CREATE" else CY
            tdd = f"{GR}PASS{RS}" if e["tdd_passed"] else f"{RD}FAIL{RS}"

            print(f"  {DM}{entry_id}{RS}  {op_clr}{op:6s}{RS}  {trit_sym}  "
                  f"{e['relative_path']}")
            print(f"         {DM}{e['timestamp']}  |  {e['diff_summary']}  |  "
                  f"TDD: {tdd}  |  chain: {e.get('chain_hash', '?')[:20]}...{RS}")
            if e.get("tdd_warnings"):
                print(f"         {YL}⚠ {', '.join(e['tdd_warnings'])}{RS}")
        print()

    def print_file_history(self, path):
        """Print all audit entries for a specific file."""
        CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
        RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

        abs_path = os.path.abspath(path)
        rel_path = self._relative_path(path)
        matches = [(eid, e) for eid, e in self.entries.items()
                   if e["path"] == abs_path or e["relative_path"] == rel_path]

        if not matches:
            print(f"\n{YL}[AUDIT]{RS} No history for: {path}\n")
            return

        print(f"\n{CY}╔══ FILE HISTORY ══╗{RS}  {rel_path}  ({len(matches)} entries)\n")
        for entry_id, e in matches:
            op = e["operation"].upper()
            trit = e["trit_result"]
            trit_sym = f"{GR}✓{RS}" if trit == 1 else f"{RD}✗{RS}" if trit == -1 else f"{YL}○{RS}"
            print(f"  {DM}{entry_id}{RS}  {trit_sym}  {op:6s}  "
                  f"{e['timestamp']}  {e['diff_summary']}")
            if e.get("content_preview"):
                preview = e["content_preview"][:80].replace("\n", "\\n")
                print(f"         {DM}preview: {preview}{RS}")
        print()

    def print_stats(self):
        """Print summary statistics."""
        CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
        RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

        if not self.entries:
            print(f"\n{YL}[AUDIT]{RS} No entries recorded yet.\n")
            return

        creates = sum(1 for e in self.entries.values() if e["operation"] == "create")
        patches = sum(1 for e in self.entries.values() if e["operation"] == "patch")
        passed = sum(1 for e in self.entries.values() if e["tdd_passed"])
        failed = len(self.entries) - passed
        trit_pos = sum(1 for e in self.entries.values() if e["trit_result"] == 1)
        trit_neg = sum(1 for e in self.entries.values() if e["trit_result"] == -1)

        unique_files = len(set(e["relative_path"] for e in self.entries.values()))

        print(f"\n{CY}╔══ AUDIT STATS ══╗{RS}\n")
        print(f"  {GR}Creates:{RS}  {creates}")
        print(f"  {CY}Patches:{RS}  {patches}")
        print(f"  {GR}TDD Pass:{RS} {passed}    {RD}TDD Fail:{RS} {failed}")
        print(f"  {GR}TRIT+:{RS}   {trit_pos}    {RD}TRIT-:{RS}   {trit_neg}")
        print(f"  {DM}Unique files touched:{RS} {unique_files}")
        print(f"  {DM}Total entries:{RS}        {len(self.entries)}")

        # Chain integrity
        valid, bad_id = self.verify_chain()
        if valid:
            print(f"\n  {GR}Chain integrity: VERIFIED ✓{RS}")
        else:
            print(f"\n  {RD}Chain integrity: BROKEN at {bad_id} ✗{RS}")
        print()
