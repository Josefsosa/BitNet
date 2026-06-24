#!/usr/bin/env python3
"""CTXP — Context Persistence Protocol CLI (SPEC-CTXP-LR-001)

Zero-dependency Python tool for managing persistent decision ledgers
across multi-session agent builds.

Usage:
    python3 .ctxp/ctxp.py <command> [args]

Commands:
    init                              Scaffold files from templates
    status                            Print phase, decisions, token estimate
    validate                          Parse and verify STATE.md schema
    checkpoint                        Tag git HEAD as ctxp-{timestamp}
    archive                           Move resolved decisions to archive if > 1.7K tokens
    decision add "label"              Add new ZERO decision
    decision resolve <id> pos|neg     Resolve a decision
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN = 4  # conservative estimate
GREEN_LIMIT = 1700   # tokens — comfortable zone
YELLOW_LIMIT = 2000  # tokens — warning zone
ARCHIVE_THRESHOLD = 1700  # tokens — trigger archival

STATE_FILE = "STATE.md"
ARCHIVE_FILE = "DECISIONS_ARCHIVE.md"
CLAUDE_FILE = "CLAUDE.md"
CHECKPOINT_LOG = ".ctxp/checkpoints/log.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def repo_root() -> Path:
    """Find the repo root (directory containing STATE.md or .ctxp/)."""
    cwd = Path.cwd()
    # Walk up until we find .ctxp/ or STATE.md
    for parent in [cwd, *cwd.parents]:
        if (parent / ".ctxp").is_dir() or (parent / STATE_FILE).is_file():
            return parent
    # Fallback to cwd
    return cwd


def estimate_tokens(text: str) -> int:
    """Estimate token count: 1 token ≈ 4 chars."""
    return len(text) // CHARS_PER_TOKEN


def token_zone(tokens: int) -> str:
    """Return GREEN / YELLOW / RED zone label."""
    if tokens <= GREEN_LIMIT:
        return "GREEN"
    elif tokens <= YELLOW_LIMIT:
        return "YELLOW"
    else:
        return "RED"


def read_file(path: Path) -> str:
    """Read a file, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def write_file(path: Path, content: str) -> None:
    """Write content to file, creating parents if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# STATE.md Parser
# ---------------------------------------------------------------------------

DECISION_PATTERN = re.compile(
    r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(ZERO|POS|NEG)\s*\|\s*(.*?)\s*\|',
    re.MULTILINE
)

PHASE_PATTERN = re.compile(
    r'^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|',
    re.MULTILINE
)


def parse_decisions(text: str) -> list:
    """Parse decision table rows from STATE.md."""
    decisions = []
    in_decisions = False
    for line in text.splitlines():
        if "## Decisions" in line:
            in_decisions = True
            continue
        if in_decisions and line.startswith("## "):
            break
        if not in_decisions:
            continue
        m = DECISION_PATTERN.match(line)
        if m:
            decisions.append({
                "id": int(m.group(1)),
                "label": m.group(2).strip(),
                "state": m.group(3).strip(),
                "detail": m.group(4).strip(),
            })
    return decisions


def parse_phases(text: str) -> list:
    """Parse phase table rows from STATE.md."""
    phases = []
    in_phases = False
    for line in text.splitlines():
        if "## Phases" in line:
            in_phases = True
            continue
        if in_phases and line.startswith("## "):
            break
        if not in_phases:
            continue
        m = PHASE_PATTERN.match(line)
        if m and "---" not in m.group(1) and "Track" not in m.group(1):
            phases.append({
                "track": m.group(1).strip(),
                "phase": m.group(2).strip(),
                "status": m.group(3).strip(),
            })
    return phases


def parse_sections(text: str) -> list:
    """Return list of ## section names."""
    return re.findall(r'^## (.+)$', text, re.MULTILINE)


def max_decision_id(text: str) -> int:
    """Find the highest decision ID in STATE.md and DECISIONS_ARCHIVE.md."""
    root = repo_root()
    all_text = text + "\n" + read_file(root / ARCHIVE_FILE)
    ids = [int(m) for m in re.findall(r'^\|\s*(\d+)\s*\|', all_text, re.MULTILINE)
           if m.isdigit()]
    return max(ids) if ids else 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Scaffold CTXP files from templates."""
    root = repo_root()

    files = {
        STATE_FILE: (
            "# STATE.md — CTXP Decision Ledger\n\n"
            "## Phases\n\n"
            "| Track | Phase | Status |\n"
            "|-------|-------|--------|\n\n"
            "## Decisions\n\n"
            "| ID | Label | State | Detail |\n"
            "|----|-------|-------|--------|\n\n"
            "## Anti-Goals\n\n"
            "## File Manifest\n\n"
        ),
        ARCHIVE_FILE: (
            "# DECISIONS_ARCHIVE.md — Resolved Decisions\n\n"
            "Append-only overflow for resolved decisions moved from STATE.md.\n\n"
            "| ID | Label | State | Detail | Archived |\n"
            "|----|-------|-------|--------|----------|\n"
        ),
    }

    created = []
    for name, content in files.items():
        path = root / name
        if not path.exists():
            write_file(path, content)
            created.append(name)
        else:
            print(f"  SKIP {name} (already exists)")

    # Ensure .ctxp/checkpoints exists
    ckpt = root / ".ctxp" / "checkpoints"
    ckpt.mkdir(parents=True, exist_ok=True)
    gitkeep = ckpt / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
        created.append(".ctxp/checkpoints/.gitkeep")

    if created:
        print(f"  Created: {', '.join(created)}")
    else:
        print("  All files already exist.")


def cmd_status(args):
    """Print phase, decision counts, token estimate, next actions."""
    root = repo_root()
    state_text = read_file(root / STATE_FILE)

    if not state_text:
        print("ERROR: STATE.md not found.")
        sys.exit(1)

    tokens = estimate_tokens(state_text)
    zone = token_zone(tokens)
    decisions = parse_decisions(state_text)
    phases = parse_phases(state_text)

    zero_count = sum(1 for d in decisions if d["state"] == "ZERO")
    pos_count = sum(1 for d in decisions if d["state"] == "POS")
    neg_count = sum(1 for d in decisions if d["state"] == "NEG")

    # Last checkpoint
    log_path = root / CHECKPOINT_LOG
    last_ckpt = "none"
    if log_path.exists():
        lines = log_path.read_text().strip().splitlines()
        if lines:
            last_ckpt = lines[-1]

    print(f"CTXP Status")
    print(f"{'=' * 50}")
    print(f"  Repo:        {root.name}")
    print(f"  Tokens:      {tokens} ({zone})")
    print(f"  Phases:      {len(phases)}")
    print(f"  Decisions:   {len(decisions)} total "
          f"(ZERO={zero_count}, POS={pos_count}, NEG={neg_count})")
    print(f"  Last ckpt:   {last_ckpt}")

    if phases:
        print(f"\n  Active Phases:")
        for p in phases:
            print(f"    {p['track']:30s} {p['phase']:40s} {p['status']}")

    # Next actions
    actions = []
    if zero_count > 0:
        labels = [d["label"] for d in decisions if d["state"] == "ZERO"]
        actions.append(f"Resolve ZERO decisions: {', '.join(labels[:3])}")
    if zone == "YELLOW":
        actions.append("Consider archiving resolved decisions")
    if zone == "RED":
        actions.append("ARCHIVE NOW — STATE.md exceeds 2K token budget")
    if not actions:
        actions.append("No immediate actions required")

    print(f"\n  Next Actions:")
    for a in actions:
        print(f"    - {a}")


def cmd_validate(args):
    """Parse STATE.md, verify schema, report token zone."""
    root = repo_root()
    state_text = read_file(root / STATE_FILE)

    if not state_text:
        print("FAIL: STATE.md not found.")
        sys.exit(1)

    violations = []

    # Check required sections
    sections = parse_sections(state_text)
    required = ["Phases", "Decisions", "Anti-Goals", "File Manifest"]
    for req in required:
        if req not in sections:
            violations.append(f"Missing required section: ## {req}")

    # Parse and validate decisions
    decisions = parse_decisions(state_text)
    seen_ids = set()
    for d in decisions:
        if d["id"] in seen_ids:
            violations.append(f"Duplicate decision ID: {d['id']}")
        seen_ids.add(d["id"])

        if d["state"] not in ("ZERO", "POS", "NEG"):
            violations.append(f"Decision {d['id']}: invalid state '{d['state']}'")

    # Token budget check
    tokens = estimate_tokens(state_text)
    zone = token_zone(tokens)

    print(f"CTXP Validate")
    print(f"{'=' * 50}")
    print(f"  Sections:    {', '.join(sections)}")
    print(f"  Decisions:   {len(decisions)}")
    print(f"  Tokens:      {tokens} ({zone})")

    if violations:
        print(f"\n  VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"    - {v}")
        print(f"\n  Result: FAIL")
        sys.exit(1)
    else:
        print(f"\n  Result: PASS (0 violations)")


def cmd_checkpoint(args):
    """Tag current git HEAD as ctxp-{timestamp}."""
    root = repo_root()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag_name = f"ctxp-{ts}"

    try:
        subprocess.run(
            ["git", "tag", tag_name],
            cwd=str(root),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create git tag: {e.stderr.strip()}")
        sys.exit(1)

    # Append to checkpoint log
    log_path = root / CHECKPOINT_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
        ).stdout.strip()
        f.write(f"{tag_name}  {head}  {datetime.now(timezone.utc).isoformat()}\n")

    print(f"  Checkpoint: {tag_name} (HEAD={head})")


def cmd_archive(args):
    """Move resolved (POS/NEG) decisions to archive if STATE.md > threshold."""
    root = repo_root()
    state_path = root / STATE_FILE
    archive_path = root / ARCHIVE_FILE
    state_text = read_file(state_path)

    if not state_text:
        print("ERROR: STATE.md not found.")
        sys.exit(1)

    tokens = estimate_tokens(state_text)
    if tokens <= ARCHIVE_THRESHOLD:
        print(f"  Token count ({tokens}) within limits — no archival needed.")
        return

    decisions = parse_decisions(state_text)
    to_archive = [d for d in decisions if d["state"] in ("POS", "NEG")]

    if not to_archive:
        print("  No resolved decisions to archive.")
        return

    # Append to archive file
    archive_text = read_file(archive_path)
    if not archive_text:
        archive_text = (
            "# DECISIONS_ARCHIVE.md — Resolved Decisions\n\n"
            "Append-only overflow for resolved decisions moved from STATE.md.\n\n"
            "| ID | Label | State | Detail | Archived |\n"
            "|----|-------|-------|--------|----------|\n"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for d in to_archive:
        archive_text += f"| {d['id']} | {d['label']} | {d['state']} | {d['detail']} | {now} |\n"

    write_file(archive_path, archive_text)

    # Remove archived rows from STATE.md
    archived_ids = {d["id"] for d in to_archive}
    new_lines = []
    for line in state_text.splitlines():
        m = DECISION_PATTERN.match(line)
        if m and int(m.group(1)) in archived_ids:
            continue
        new_lines.append(line)

    write_file(state_path, "\n".join(new_lines) + "\n")

    new_tokens = estimate_tokens("\n".join(new_lines))
    print(f"  Archived {len(to_archive)} decisions.")
    print(f"  Tokens: {tokens} → {new_tokens} ({token_zone(new_tokens)})")


def cmd_decision(args):
    """Handle decision subcommands: add, resolve."""
    if args.decision_cmd == "add":
        cmd_decision_add(args)
    elif args.decision_cmd == "resolve":
        cmd_decision_resolve(args)
    else:
        print(f"ERROR: Unknown decision subcommand: {args.decision_cmd}")
        sys.exit(1)


def cmd_decision_add(args):
    """Append new ZERO decision with auto-incremented ID."""
    root = repo_root()
    state_path = root / STATE_FILE
    state_text = read_file(state_path)

    if not state_text:
        print("ERROR: STATE.md not found.")
        sys.exit(1)

    next_id = max_decision_id(state_text) + 1
    label = args.label
    new_row = f"| {next_id} | {label} | ZERO | — |"

    # Insert before the next section after Decisions, or at end of Decisions table
    lines = state_text.splitlines()
    insert_idx = None
    in_decisions = False
    last_table_row = None

    for i, line in enumerate(lines):
        if "## Decisions" in line:
            in_decisions = True
            continue
        if in_decisions:
            if line.startswith("## "):
                insert_idx = i
                break
            if line.startswith("|") and "---" not in line and "ID" not in line:
                last_table_row = i

    if insert_idx is None:
        # No section after Decisions — append at end
        insert_idx = len(lines)

    # If we found table rows, insert after last one
    if last_table_row is not None:
        insert_idx = last_table_row + 1

    lines.insert(insert_idx, new_row)
    write_file(state_path, "\n".join(lines) + "\n")

    print(f"  Added decision #{next_id}: {label} (ZERO)")


def cmd_decision_resolve(args):
    """Resolve a ZERO decision to POS or NEG."""
    root = repo_root()
    state_path = root / STATE_FILE
    state_text = read_file(state_path)

    if not state_text:
        print("ERROR: STATE.md not found.")
        sys.exit(1)

    target_id = args.id
    new_state = args.resolution.upper()

    if new_state not in ("POS", "NEG"):
        print(f"ERROR: Resolution must be 'pos' or 'neg', got '{args.resolution}'")
        sys.exit(1)

    reason = args.reason or ""
    verification = args.verification or ""
    detail = reason
    if verification:
        detail += f" [verified: {verification}]"
    if not detail:
        detail = "—"

    decisions = parse_decisions(state_text)
    target = None
    for d in decisions:
        if d["id"] == target_id:
            target = d
            break

    if target is None:
        print(f"ERROR: Decision #{target_id} not found.")
        sys.exit(1)

    if target["state"] != "ZERO":
        print(f"ERROR: Decision #{target_id} is already {target['state']} — cannot re-resolve.")
        sys.exit(1)

    # Replace the row in STATE.md
    lines = state_text.splitlines()
    new_lines = []
    for line in lines:
        m = DECISION_PATTERN.match(line)
        if m and int(m.group(1)) == target_id:
            new_lines.append(f"| {target_id} | {target['label']} | {new_state} | {detail} |")
        else:
            new_lines.append(line)

    write_file(state_path, "\n".join(new_lines) + "\n")
    print(f"  Resolved decision #{target_id}: ZERO → {new_state}")
    if detail != "—":
        print(f"  Detail: {detail}")


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctxp",
        description="CTXP — Context Persistence Protocol CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Scaffold CTXP files")

    # status
    sub.add_parser("status", help="Print current state summary")

    # validate
    sub.add_parser("validate", help="Validate STATE.md schema")

    # checkpoint
    sub.add_parser("checkpoint", help="Tag git HEAD as ctxp checkpoint")

    # archive
    sub.add_parser("archive", help="Archive resolved decisions if over token limit")

    # decision
    dec = sub.add_parser("decision", help="Manage decisions")
    dec_sub = dec.add_subparsers(dest="decision_cmd")

    # decision add
    add_p = dec_sub.add_parser("add", help="Add a new ZERO decision")
    add_p.add_argument("label", help="Decision label/description")

    # decision resolve
    res_p = dec_sub.add_parser("resolve", help="Resolve a ZERO decision")
    res_p.add_argument("id", type=int, help="Decision ID to resolve")
    res_p.add_argument("resolution", choices=["pos", "neg", "POS", "NEG"],
                       help="Resolution: pos or neg")
    res_p.add_argument("--reason", "-r", default="", help="Reason for resolution")
    res_p.add_argument("--verification", "-v", default="", help="Verification method")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "validate": cmd_validate,
        "checkpoint": cmd_checkpoint,
        "archive": cmd_archive,
        "decision": cmd_decision,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
