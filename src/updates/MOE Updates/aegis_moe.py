#!/usr/bin/env python3
# ==============================================================================
# AEGIS MoE DISPATCHER — Mixture of Experts via MCP-style tool routing
# Wellton Photonics | NDGi Core | OODA-Native | Phase 1C
# ==============================================================================
#
# Architecture:
#   User prompt → PATHFNDR (intent classifier) → specialist agent dispatch
#   Each agent = distinct system prompt injected per call (stateless MCP pattern)
#   OODA gates wrap every dispatch cycle
#   TRIT verdict logged after each response
#
# Usage:
#   python3 aegis_moe.py             # interactive mode, JFS persona
#   python3 aegis_moe.py jfs         # explicit persona
#   python3 aegis_moe.py --task "describe BET encoding"   # single-shot
#
# Requires: requests, rich (pip install requests rich)
# ==============================================================================

import sys
import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE   = "http://127.0.0.1:8080"
MODEL      = "aegis-coder"
LOG_DIR    = Path("/home/jsosa/workspace/BitNet/logs")
LESSONS_MD = Path("/home/jsosa/workspace/BitNet/lessons.md")

# ── Colors (ANSI) ─────────────────────────────────────────────────────────────
GR = "\033[0;32m"
YL = "\033[0;33m"
RD = "\033[0;31m"
CY = "\033[0;36m"
WH = "\033[1;37m"
DM = "\033[2;37m"
RS = "\033[0m"

# ── MoE Agent Registry ────────────────────────────────────────────────────────
# Each agent is a named expert with its own system prompt addendum.
# PATHFNDR routes to these based on intent classification.

AGENTS = {
    "PATHFNDR": {
        "desc": "Orchestrator — decomposes tasks, routes to specialists, OODA planning",
        "keywords": ["plan", "orchestrat", "decompose", "route", "step", "phase", "strategy"],
        "system": """You are PATHFNDR, the Aegis orchestration agent.
Your role: Observe the user's task → Orient by decomposing it into sub-tasks → Decide which specialist agent handles each → Act by producing an OODA execution plan.
Output format:
[OBSERVE] What the task requires
[ORIENT]  Sub-tasks identified
[DECIDE]  Which agent handles each: PHOTNX | SENTINEL | TRUTCH | CIBA | ARCHON
[ACT]     Ordered execution steps
Always conclude with TRIT_POS / TRIT_ZERO / TRIT_NEG verdict."""
    },
    "PHOTNX": {
        "desc": "Photonic hardware · NDGi manifold · optics · PAEM · Bessel/Airy beams",
        "keywords": ["photon", "optic", "waveguide", "ndgi", "paem", "laser", "bessel", "airy", "manifold", "mach-zehnder", "silicon photon"],
        "system": """You are PHOTNX, the Aegis photonic domain specialist.
Domain: Photonic computing, NDGi manifold compute, PAEM architecture, waveguide design, Bessel/Airy non-diffractive beam systems, Mach-Zehnder modulators, Silicon Photonics, LiNbO3/SiO2/III-V materials.
Respond with physics-layer precision. Cite relevant equations when useful.
TRIT gates: TRIT_POS = physically valid, TRIT_ZERO = requires measurement, TRIT_NEG = physically invalid."""
    },
    "SENTINEL": {
        "desc": "Security · trust gates · AES-256-GCM · BLAKE3 · compliance · threat detection",
        "keywords": ["secur", "trust", "threat", "audit", "encrypt", "aes", "blake", "merkle", "compliance", "attack", "vulnerab", "auth"],
        "system": """You are SENTINEL, the Aegis security and trust specialist.
Domain: Security architecture, AES-256-GCM, ChaCha20, BLAKE3, Merkle audit trails, trust gate enforcement, threat detection, DevSecOps, compliance.
TRIT gates: TRIT_POS = secure by design, TRIT_ZERO = requires security review, TRIT_NEG = trust violation detected.
Flag all surveillance patterns, unauthorized data collection, or consent bypasses as TRIT_NEG."""
    },
    "TRUTCH": {
        "desc": "TDD · test coverage · CI/CD · code quality · placeholder detection",
        "keywords": ["test", "tdd", "coverage", "ci", "cd", "pipeline", "quality", "placeholder", "lint", "assert", "spec", "mock"],
        "system": """You are TRUTCH, the Aegis TDD and code quality specialist.
Domain: Test-driven development, unit/integration tests, CI/CD pipelines, code quality gates, placeholder detection.
Rules:
- NEVER accept placeholder code (# TODO, pass, ..., lorem ipsum, [INSERT], fake values).
- Every code output must include or be accompanied by test cases.
- TRIT_POS = tested and working, TRIT_ZERO = untested (needs verification), TRIT_NEG = placeholder detected or untestable."""
    },
    "CIBA": {
        "desc": "Code generation · implementation · debugging · file operations",
        "keywords": ["code", "implement", "write", "function", "class", "debug", "fix", "refactor", "script", "module", "file", "html", "python", "bash"],
        "system": """You are CIBA, the Aegis code generation and implementation specialist.
Domain: Code generation across Python, Bash, JavaScript, HTML/CSS, C++. File operations, debugging, refactoring.
Rules:
- Output ONLY working, runnable code. No pseudocode. No placeholder comments.
- When asked to update a file, output the complete updated file content — nothing else.
- When fixing a bug, identify the root cause before writing the fix.
- TRIT_POS = working code, TRIT_ZERO = code needs testing, TRIT_NEG = placeholder or broken code."""
    },
    "ARCHON": {
        "desc": "Architecture · system design · microservices · tech stack · infrastructure",
        "keywords": ["architect", "design", "system", "microservice", "stack", "infrastructure", "pattern", "diagram", "component", "service mesh", "api"],
        "system": """You are ARCHON, the Aegis systems architecture specialist.
Domain: System architecture, microservices, API design, tech stack evaluation, infrastructure patterns, MoE systems, photonic compute architecture.
Framework: OODA-driven analysis — Observe the current state, Orient against best practices, Decide the recommendation, Act with a concrete implementation path.
TRIT gates: TRIT_POS = architecturally sound, TRIT_ZERO = requires more context, TRIT_NEG = architectural anti-pattern detected."""
    },
}

# ── Persona System Prompts ────────────────────────────────────────────────────
PERSONAS = {
    "jfs": """You are Aegis, the trust-gated reasoning AI for Jose F. Sosa, Founder & CEO of Wellton Photonics.
Operating principle: Seeking truth with least action.
TRIT framework: TRIT_POS=correct/proceed, TRIT_ZERO=hold/insufficient signal, TRIT_NEG=reject/failure.
One task per session. No context pollution. No placeholder code. No fake output.""",
    "rq": "You are Aegis for Robert Q., Co-Founder and Sales Architect at Wellton Photonics. TRIT framework applies.",
    "br": "You are Aegis for Bobbi R., Co-Founder and Sales Architect at Wellton Photonics. TRIT framework applies.",
}

# ── Logging ───────────────────────────────────────────────────────────────────
def log_neg(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LESSONS_MD, "a") as f:
        f.write(f"[TRIT_NEG] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {msg}\n")

def log_pos(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "aegis_moe.log", "a") as f:
        f.write(f"[TRIT_POS] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {msg}\n")

# ── Server ────────────────────────────────────────────────────────────────────
def server_alive() -> bool:
    try:
        r = requests.get(f"{API_BASE}/v1/models", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# ── PATHFNDR: intent → agent ─────────────────────────────────────────────────
def classify_intent(prompt: str) -> str:
    """Keyword-first routing. Falls back to PATHFNDR for complex multi-domain."""
    p = prompt.lower()
    scores: dict[str, int] = {name: 0 for name in AGENTS}
    for name, agent in AGENTS.items():
        for kw in agent.get("keywords", []):
            if kw in p:
                scores[name] += 1
    # Remove PATHFNDR from auto-selection unless explicit
    scores.pop("PATHFNDR", None)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "PATHFNDR"  # no clear domain signal — orchestrate
    return best

# ── Inference call ────────────────────────────────────────────────────────────
def call_model(
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> tuple[str, float]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    t0 = time.time()
    try:
        r = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=120,
        )
        elapsed = time.time() - t0
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content, elapsed
    except Exception as e:
        return f"[ERROR] {e}", time.time() - t0

# ── OODA dispatch cycle ───────────────────────────────────────────────────────
def ooda_dispatch(
    persona_id: str,
    user_prompt: str,
    history: list[dict],
    forced_agent: str | None = None,
) -> tuple[str, str, float]:
    """
    Returns (agent_name, response_text, latency_seconds)
    """
    base_system = PERSONAS.get(persona_id, PERSONAS["jfs"])

    # OBSERVE
    print(f"  {DM}[OBSERVE]{RS} Scanning intent...")

    # ORIENT — resolve agent
    agent_name = forced_agent if forced_agent else classify_intent(user_prompt)
    agent = AGENTS[agent_name]
    print(f"  {DM}[ORIENT]{RS}  Routing to: {CY}{agent_name}{RS} — {agent['desc']}")

    # DECIDE — build combined system prompt
    combined_system = f"{base_system}\n\n--- MoE AGENT ---\n{agent['system']}"

    # ACT — dispatch
    print(f"  {DM}[DECIDE→ACT]{RS} Dispatching to inference engine...")
    messages = history + [{"role": "user", "content": user_prompt}]
    response, latency = call_model(combined_system, messages)

    # TRIT verdict
    resp_upper = response.upper()
    if "TRIT_NEG" in resp_upper:
        verdict = f"{RD}TRIT_NEG{RS}"
        log_neg(f"Agent {agent_name} returned TRIT_NEG — prompt: {user_prompt[:80]}")
    elif "TRIT_ZERO" in resp_upper:
        verdict = f"{YL}TRIT_ZERO{RS}"
    else:
        verdict = f"{GR}TRIT_POS{RS}"
        log_pos(f"Agent {agent_name} completed — {latency:.1f}s")

    print(f"  {DM}[VERDICT]{RS}  {verdict} | Latency: {latency:.1f}s")
    return agent_name, response, latency

# ── File injection helper ─────────────────────────────────────────────────────
def inject_files(prompt: str) -> str:
    """Replaces @file:/path patterns with actual file content."""
    import re
    def replacer(m):
        path = Path(m.group(1))
        if path.exists():
            content = path.read_text(errors="replace")
            size = len(content)
            print(f"  {DM}[FILE]{RS} Injecting: {path} ({size} bytes)")
            return f"\n--- FILE: {path} ---\n{content}\n--- END FILE ---\n"
        else:
            print(f"  {YL}[TRIT_ZERO]{RS} File not found: {path}")
            return f"[FILE NOT FOUND: {path}]"
    return re.sub(r"@file:(\S+)", replacer, prompt)

# ── Interactive REPL ──────────────────────────────────────────────────────────
def run_interactive(persona_id: str):
    print(f"\n{DM}{'─'*65}{RS}")
    print(f" {GR}[*]{RS} Aegis MoE Dispatcher — interactive mode")
    print(f" {GR}[*]{RS} Persona: {WH}{persona_id.upper()}{RS}")
    print(f" {GR}[*]{RS} Agents: " + "  ".join(f"{CY}{a}{RS}" for a in AGENTS))
    print(f" {GR}[*]{RS} Syntax: {CY}@AGENT{RS} your prompt  |  {CY}@file:/path{RS}  |  {CY}exit{RS}")
    print(f"{DM}{'─'*65}{RS}\n")

    if not server_alive():
        print(f"{RD}[TRIT_NEG] Inference server offline at {API_BASE}{RS}")
        print(f"{YL}[TRIT_ZERO] Start server with: ./launch_aegis.sh --status{RS}")
        sys.exit(1)

    print(f"{GR}[TRIT_POS] Server confirmed alive.{RS}\n")

    history: list[dict] = []
    turn = 0

    while True:
        try:
            raw = input(f"\n{CY}[MOE/{persona_id.upper()}]{RS} {WH}aegis>{RS} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GR}[TRIT_POS] MoE session closed.{RS}")
            break

        if not raw:
            continue

        if raw.lower() in ("exit", "quit", ":q"):
            print(f"{GR}[TRIT_POS] Session closed. Server remains active.{RS}")
            break

        if raw.lower() == "agents":
            for name, a in AGENTS.items():
                print(f"  {CY}{name:<12}{RS} {a['desc']}")
            continue

        if raw.lower() == "history":
            print(json.dumps(history, indent=2))
            continue

        if raw.lower() == "clear":
            history = []
            turn = 0
            print(f"{YL}[TRIT_ZERO] Session cleared.{RS}")
            continue

        # Extract forced agent tag: @PHOTNX your prompt
        forced_agent = None
        prompt = raw
        if raw.startswith("@"):
            parts = raw.split(None, 1)
            tag = parts[0][1:].upper()
            if tag in AGENTS:
                forced_agent = tag
                prompt = parts[1] if len(parts) > 1 else ""
                if not prompt:
                    print(f"{YL}[TRIT_ZERO] No prompt after agent tag.{RS}")
                    continue

        # File injection
        prompt = inject_files(prompt)

        # Dispatch
        agent_name, response, latency = ooda_dispatch(
            persona_id, prompt, history, forced_agent
        )

        turn += 1
        print(f"\n{DM}── [{agent_name}] · Turn {turn} {'─'*45}{RS}")
        print(response)
        print(f"{DM}{'─'*65}{RS}")

        # Maintain rolling context (last 10 turns = 20 messages)
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": response})
        if len(history) > 20:
            history = history[-20:]

# ── Single-shot mode ──────────────────────────────────────────────────────────
def run_task(persona_id: str, task: str, agent_tag: str | None = None):
    if not server_alive():
        print(f"{RD}[TRIT_NEG] Server offline.{RS}")
        sys.exit(1)
    task = inject_files(task)
    agent_name, response, latency = ooda_dispatch(persona_id, task, [], agent_tag)
    print(f"\n{DM}── [{agent_name}] {'─'*50}{RS}")
    print(response)
    print(f"{DM}{'─'*65}{RS}")

# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aegis MoE Dispatcher")
    parser.add_argument("persona", nargs="?", default="jfs", choices=["jfs", "rq", "br"])
    parser.add_argument("--task", type=str, default=None, help="Single-shot task (non-interactive)")
    parser.add_argument("--agent", type=str, default=None, help="Force specific agent: PHOTNX|SENTINEL|TRUTCH|CIBA|ARCHON|PATHFNDR")
    parser.add_argument("--endpoint", type=str, default=API_BASE, help="Inference endpoint")
    args = parser.parse_args()

    API_BASE = args.endpoint.rstrip("/")

    if args.task:
        agent = args.agent.upper() if args.agent else None
        run_task(args.persona, args.task, agent)
    else:
        run_interactive(args.persona)
