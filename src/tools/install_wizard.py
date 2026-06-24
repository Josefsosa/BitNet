"""
Aegis Install Wizard — curses-based TUI for configuring ~/.aegis/config.json.

6-step flow:
  0. Welcome (PHOTNX banner)
  1. Model Selector (BitNet Local / Custom endpoint)
  2. Persona (jfs / rq / br)
  3. NDGi Memory Mode (Ternary / Binary)
  4. Agent Capabilities (checkbox: 6 agents)
  5. Summary + Confirm
"""

import curses
import copy
from tools.aegis_config import DEFAULT_CONFIG, save_config

# PHOTNX ASCII banner (matches display_splash in aegis-cli.py)
BANNER = r"""
    ██████╗ ██╗  ██╗ ██████╗ ████████╗███╗  ██╗██╗  ██╗
    ██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝████╗ ██║╚██╗██╔╝
    ██████╔╝███████║██║   ██║   ██║   ██╔██╗██║ ╚███╔╝
    ██╔═══╝ ██╔══██║██║   ██║   ██║   ██║╚████║ ██╔██╗
    ██║     ██║  ██║╚██████╔╝   ██║   ██║ ╚███║██╔╝╚██╗
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚══╝╚═╝  ╚═╝
"""

# Agent descriptions (from MOE_AGENTS in aegis-cli.py)
AGENT_INFO = {
    "photnx":   "Photonic hardware, NDGi manifold, optics, PAEM",
    "sentinel": "Security, trust gates, AES-256-GCM, BLAKE3, compliance",
    "trutch":   "TDD, test coverage, CI/CD, code quality",
    "ciba":     "Code generation, debugging, runnable code",
    "archon":   "System architecture, OODA analysis",
    "pathfndr": "Orchestration, task decomposition, planning",
}

PERSONA_INFO = {
    "jfs": ("Jose F. Sosa", "Founder & CEO — Engineering · Architecture"),
    "rq":  ("Robert Q.", "Co-Founder — Sales Architecture"),
    "br":  ("Bobbi R.", "Co-Founder — Sales Architecture"),
}

MODEL_OPTIONS = [
    ("BitNet Local (:8080)", "http://localhost:8080/v1/chat/completions", "bitnet_local"),
    ("Custom endpoint", "", "custom"),
]

MEMORY_OPTIONS = [
    ("Ternary (POS / ZERO / NEG)", "ternary"),
    ("Binary (pass / fail)", "binary"),
]


class InstallWizard:
    """Curses-based 6-step install wizard."""

    STEPS = ["Welcome", "Model", "Persona", "Memory Mode", "Agents", "Summary"]

    def __init__(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.step = 0
        self.cursor = 0
        # Agent checkbox state
        self.agent_checks = {k: True for k in AGENT_INFO}
        # Custom endpoint text
        self.custom_endpoint = ""
        # Selections
        self.model_sel = 0
        self.persona_sel = 0
        self.memory_sel = 0

    def run(self):
        """Launch the curses wizard. Returns config dict or None if cancelled."""
        try:
            return curses.wrapper(self._main)
        except KeyboardInterrupt:
            return None

    def _main(self, stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_WHITE, -1)
        curses.init_pair(5, curses.COLOR_RED, -1)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # Draw step indicator
            self._draw_step_bar(stdscr, w)

            if self.step == 0:
                result = self._step_welcome(stdscr, h, w)
            elif self.step == 1:
                result = self._step_model(stdscr, h, w)
            elif self.step == 2:
                result = self._step_persona(stdscr, h, w)
            elif self.step == 3:
                result = self._step_memory(stdscr, h, w)
            elif self.step == 4:
                result = self._step_agents(stdscr, h, w)
            elif self.step == 5:
                result = self._step_summary(stdscr, h, w)
            else:
                break

            if result == "quit":
                return None
            elif result == "done":
                self._apply_selections()
                save_config(self.config)
                return self.config
            elif result == "next":
                self.step += 1
                self.cursor = 0
            elif result == "back":
                if self.step > 0:
                    self.step -= 1
                    self.cursor = 0

    def _draw_step_bar(self, stdscr, w):
        """Draw step progress bar at top."""
        bar = ""
        for i, name in enumerate(self.STEPS):
            if i == self.step:
                bar += f" [{name}] "
            else:
                bar += f"  {name}  "
        try:
            stdscr.addnstr(0, 0, bar.center(w), w, curses.color_pair(1))
            stdscr.addnstr(1, 0, "─" * w, w, curses.color_pair(1))
        except curses.error:
            pass

    def _draw_nav_hint(self, stdscr, h, w, extra=""):
        """Draw navigation hints at bottom."""
        hint = "  ↑/↓ Navigate  │  ENTER Select  │  B Back  │  Q Quit"
        if extra:
            hint += f"  │  {extra}"
        try:
            stdscr.addnstr(h - 1, 0, hint.center(w), w, curses.color_pair(1))
        except curses.error:
            pass

    # ── Step 0: Welcome ───────────────────────────────────────────────────

    def _step_welcome(self, stdscr, h, w):
        row = 3
        for line in BANNER.splitlines():
            try:
                stdscr.addnstr(row, max(0, (w - len(line)) // 2), line, w,
                               curses.color_pair(1) | curses.A_BOLD)
            except curses.error:
                pass
            row += 1

        row += 1
        title = "AEGIS ORCHESTRATION — INSTALL WIZARD"
        try:
            stdscr.addnstr(row, max(0, (w - len(title)) // 2), title, w,
                           curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass

        row += 2
        subtitle = "Configure your Aegis instance: model endpoint, persona,"
        subtitle2 = "memory mode, and MoE agent capabilities."
        try:
            stdscr.addnstr(row, max(0, (w - len(subtitle)) // 2), subtitle, w,
                           curses.color_pair(4))
            stdscr.addnstr(row + 1, max(0, (w - len(subtitle2)) // 2), subtitle2, w,
                           curses.color_pair(4))
        except curses.error:
            pass

        row += 4
        prompt = "Press ENTER to begin  ·  Q to quit"
        try:
            stdscr.addnstr(row, max(0, (w - len(prompt)) // 2), prompt, w,
                           curses.color_pair(3))
        except curses.error:
            pass

        stdscr.refresh()
        return self._wait_enter_or_quit(stdscr)

    # ── Step 1: Model Selector ────────────────────────────────────────────

    def _step_model(self, stdscr, h, w):
        row = 3
        self._title(stdscr, row, w, "INFERENCE ENDPOINT")
        row += 2
        self._subtitle(stdscr, row, w, "Select your model backend:")
        row += 2

        for i, (label, endpoint, _) in enumerate(MODEL_OPTIONS):
            marker = "●" if i == self.model_sel else "○"
            attr = curses.color_pair(2) | curses.A_BOLD if i == self.model_sel else curses.color_pair(4)
            text = f"  {marker}  {label}"
            if endpoint:
                text += f"  →  {endpoint}"
            try:
                stdscr.addnstr(row, 4, text, w - 8, attr)
            except curses.error:
                pass
            row += 2

        # If custom selected, show text input
        if self.model_sel == 1:
            row += 1
            try:
                stdscr.addnstr(row, 6, "Endpoint URL: ", w - 10, curses.color_pair(3))
                stdscr.addnstr(row, 20, self.custom_endpoint + "█", w - 22,
                               curses.color_pair(4) | curses.A_BOLD)
            except curses.error:
                pass

        self._draw_nav_hint(stdscr, h, w)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (ord('b'), ord('B'), 27):  # ESC or B
            return "back"
        if key == curses.KEY_UP:
            self.model_sel = max(0, self.model_sel - 1)
        elif key == curses.KEY_DOWN:
            self.model_sel = min(len(MODEL_OPTIONS) - 1, self.model_sel + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            if self.model_sel == 1 and not self.custom_endpoint:
                return None  # need endpoint input
            return "next"
        elif self.model_sel == 1:
            # Text input for custom endpoint
            if key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                self.custom_endpoint = self.custom_endpoint[:-1]
            elif 32 <= key <= 126:
                self.custom_endpoint += chr(key)
        return None

    # ── Step 2: Persona ───────────────────────────────────────────────────

    def _step_persona(self, stdscr, h, w):
        row = 3
        self._title(stdscr, row, w, "PERSONA SELECTION")
        row += 2
        self._subtitle(stdscr, row, w, "Choose your Aegis identity:")
        row += 2

        persona_keys = list(PERSONA_INFO.keys())
        for i, pid in enumerate(persona_keys):
            name, title = PERSONA_INFO[pid]
            marker = "●" if i == self.persona_sel else "○"
            attr = curses.color_pair(2) | curses.A_BOLD if i == self.persona_sel else curses.color_pair(4)
            text = f"  {marker}  [{pid}] {name} — {title}"
            try:
                stdscr.addnstr(row, 4, text, w - 8, attr)
            except curses.error:
                pass
            row += 2

        self._draw_nav_hint(stdscr, h, w)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (ord('b'), ord('B'), 27):
            return "back"
        if key == curses.KEY_UP:
            self.persona_sel = max(0, self.persona_sel - 1)
        elif key == curses.KEY_DOWN:
            self.persona_sel = min(len(persona_keys) - 1, self.persona_sel + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return "next"
        return None

    # ── Step 3: Memory Mode ───────────────────────────────────────────────

    def _step_memory(self, stdscr, h, w):
        row = 3
        self._title(stdscr, row, w, "NDGi MEMORY MODE")
        row += 2
        self._subtitle(stdscr, row, w, "Select memory evaluation mode:")
        row += 2

        for i, (label, _) in enumerate(MEMORY_OPTIONS):
            marker = "●" if i == self.memory_sel else "○"
            attr = curses.color_pair(2) | curses.A_BOLD if i == self.memory_sel else curses.color_pair(4)
            text = f"  {marker}  {label}"
            try:
                stdscr.addnstr(row, 4, text, w - 8, attr)
            except curses.error:
                pass
            row += 2

        row += 1
        if self.memory_sel == 0:
            desc = "Ternary: TRIT_POS (+1) = confirmed, TRIT_ZERO (0) = hold, TRIT_NEG (-1) = reject"
        else:
            desc = "Binary: PASS = proceed, FAIL = reject. No intermediate state."
        try:
            stdscr.addnstr(row, 6, desc, w - 10, curses.color_pair(1))
        except curses.error:
            pass

        self._draw_nav_hint(stdscr, h, w)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (ord('b'), ord('B'), 27):
            return "back"
        if key == curses.KEY_UP:
            self.memory_sel = max(0, self.memory_sel - 1)
        elif key == curses.KEY_DOWN:
            self.memory_sel = min(len(MEMORY_OPTIONS) - 1, self.memory_sel + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return "next"
        return None

    # ── Step 4: Agent Capabilities ────────────────────────────────────────

    def _step_agents(self, stdscr, h, w):
        row = 3
        self._title(stdscr, row, w, "MoE AGENT CAPABILITIES")
        row += 2
        self._subtitle(stdscr, row, w, "Toggle agents with SPACE (at least 1 required):")
        row += 2

        agent_keys = list(AGENT_INFO.keys())
        for i, aid in enumerate(agent_keys):
            check = "■" if self.agent_checks[aid] else "□"
            is_cursor = (i == self.cursor)
            if is_cursor:
                attr = curses.color_pair(6) | curses.A_BOLD
            elif self.agent_checks[aid]:
                attr = curses.color_pair(2)
            else:
                attr = curses.color_pair(4)
            text = f"  {check}  {aid.upper():10s} {AGENT_INFO[aid]}"
            try:
                stdscr.addnstr(row, 4, text, w - 8, attr)
            except curses.error:
                pass
            row += 2

        # Show warning if none selected
        enabled = sum(1 for v in self.agent_checks.values() if v)
        if enabled == 0:
            row += 1
            try:
                stdscr.addnstr(row, 6, "⚠  At least one agent must be enabled!",
                               w - 10, curses.color_pair(5) | curses.A_BOLD)
            except curses.error:
                pass

        self._draw_nav_hint(stdscr, h, w, "SPACE Toggle")
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (ord('b'), ord('B'), 27):
            return "back"
        if key == curses.KEY_UP:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_DOWN:
            self.cursor = min(len(agent_keys) - 1, self.cursor + 1)
        elif key == ord(' '):
            aid = agent_keys[self.cursor]
            self.agent_checks[aid] = not self.agent_checks[aid]
        elif key in (curses.KEY_ENTER, 10, 13):
            if enabled > 0:
                return "next"
        return None

    # ── Step 5: Summary ───────────────────────────────────────────────────

    def _step_summary(self, stdscr, h, w):
        row = 3
        self._title(stdscr, row, w, "CONFIGURATION SUMMARY")
        row += 2

        # Model
        model_label, endpoint, mtype = MODEL_OPTIONS[self.model_sel]
        if self.model_sel == 1:
            endpoint = self.custom_endpoint
        self._kv(stdscr, row, w, "Endpoint", f"{endpoint}  ({mtype})")
        row += 2

        # Persona
        pid = list(PERSONA_INFO.keys())[self.persona_sel]
        pname, ptitle = PERSONA_INFO[pid]
        self._kv(stdscr, row, w, "Persona", f"[{pid}] {pname} — {ptitle}")
        row += 2

        # Memory mode
        _, mem_mode = MEMORY_OPTIONS[self.memory_sel]
        self._kv(stdscr, row, w, "Memory", mem_mode.upper())
        row += 2

        # Agents
        enabled = [k.upper() for k, v in self.agent_checks.items() if v]
        disabled = [k.upper() for k, v in self.agent_checks.items() if not v]
        self._kv(stdscr, row, w, "Agents ON", " · ".join(enabled) if enabled else "(none)")
        row += 1
        if disabled:
            self._kv(stdscr, row, w, "Agents OFF", " · ".join(disabled))
        row += 3

        # Save path
        try:
            stdscr.addnstr(row, 6, "Save to: ~/.aegis/config.json", w - 10,
                           curses.color_pair(1))
        except curses.error:
            pass
        row += 2

        prompt = "ENTER Save  │  B Go back  │  Q Quit without saving"
        try:
            stdscr.addnstr(row, max(0, (w - len(prompt)) // 2), prompt, w,
                           curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (ord('b'), ord('B'), 27):
            return "back"
        if key in (curses.KEY_ENTER, 10, 13):
            return "done"
        return None

    # ── Helpers ───────────────────────────────────────────────────────────

    def _apply_selections(self):
        """Apply wizard selections into self.config."""
        # Model
        _, endpoint, mtype = MODEL_OPTIONS[self.model_sel]
        if self.model_sel == 1:
            endpoint = self.custom_endpoint
        self.config["inference"]["endpoint"] = endpoint
        self.config["inference"]["type"] = mtype

        # Persona
        pid = list(PERSONA_INFO.keys())[self.persona_sel]
        self.config["persona"] = pid

        # Memory mode
        _, mem_mode = MEMORY_OPTIONS[self.memory_sel]
        self.config["ndgi"]["memory_mode"] = mem_mode

        # Agents
        self.config["agents"] = dict(self.agent_checks)

    def _title(self, stdscr, row, w, text):
        try:
            stdscr.addnstr(row, max(0, (w - len(text)) // 2), text, w,
                           curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass

    def _subtitle(self, stdscr, row, w, text):
        try:
            stdscr.addnstr(row, 6, text, w - 10, curses.color_pair(4))
        except curses.error:
            pass

    def _kv(self, stdscr, row, w, key, val):
        try:
            stdscr.addnstr(row, 6, f"{key + ':':14s}", 14, curses.color_pair(3))
            stdscr.addnstr(row, 20, val, w - 24, curses.color_pair(4) | curses.A_BOLD)
        except curses.error:
            pass

    def _wait_enter_or_quit(self, stdscr):
        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return "quit"
        if key in (curses.KEY_ENTER, 10, 13):
            return "next"
        return None
