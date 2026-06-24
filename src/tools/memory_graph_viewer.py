"""
Aegis Memory Graph Viewer — Two-pane GTK+WebKit2 viewer for NDGi memory graph.

Left pane:  Gtk.Notebook with Sessions / Concepts / Vocabulary tabs
Right pane: D3.js force-directed graph (color by session or category)

Dark theme: #1e1e2e bg, #cdd6f4 fg (Aegis palette)

Usage:
    from tools.memory_graph_viewer import launch_viewer
    launch_viewer()                      # full graph
    launch_viewer(session_filter="Photonic Compute")  # session-filtered
"""

import os
import json
import sqlite3
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2, GLib, Pango, Gdk

NDGI_DB = os.path.expanduser("~/BitNet/logs/ndgi.db")

# Node cap for performance
MAX_NODES = 200
MAX_EDGES = 500

# Category color palette (HSL-based)
CATEGORY_COLORS = {
    "auto":      "#06b6d4",  # cyan
    "photonic":  "#10b981",  # green
    "agent":     "#3b82f6",  # blue
    "compute":   "#f59e0b",  # amber
    "security":  "#a855f7",  # purple
    "user":      "#ec4899",  # pink
}
DEFAULT_NODE_COLOR = "#64748b"


class MemoryGraphViewer:
    """GTK+WebKit2 two-pane memory graph viewer."""

    def __init__(self, session_filter=None):
        self.session_filter = session_filter
        self.concepts = []
        self.edges = []
        self.sessions = []
        self.custom_vocab = []
        self.base_vocab = []
        self.session_concept_map = {}  # concept_id -> set of session names
        self._load_data()

    def _load_data(self):
        """Load all data from SQLite."""
        if not os.path.isfile(NDGI_DB):
            return
        try:
            con = sqlite3.connect(NDGI_DB)

            # Concepts
            try:
                rows = con.execute(
                    "SELECT id, label, category, confidence, created_at FROM concepts"
                ).fetchall()
                self.concepts = [
                    {"id": r[0], "label": r[1], "category": r[2] or "auto",
                     "confidence": r[3] or 0.5, "created_at": r[4] or ""}
                    for r in rows
                ]
            except sqlite3.OperationalError:
                pass

            # Edges
            try:
                rows = con.execute(
                    "SELECT src, dst, weight, trit_sum, touch_count FROM concept_edges"
                ).fetchall()
                self.edges = [
                    {"src": r[0], "dst": r[1], "weight": r[2],
                     "trit_sum": r[3], "touch_count": r[4]}
                    for r in rows
                ]
            except sqlite3.OperationalError:
                pass

            # Sessions
            try:
                rows = con.execute(
                    "SELECT id, name, started_at, ended_at, concept_count, edge_count "
                    "FROM training_sessions ORDER BY started_at DESC"
                ).fetchall()
                self.sessions = [
                    {"id": r[0], "name": r[1], "started_at": r[2],
                     "ended_at": r[3], "concept_count": r[4], "edge_count": r[5]}
                    for r in rows
                ]
            except sqlite3.OperationalError:
                pass

            # Session-concept mapping
            try:
                rows = con.execute(
                    "SELECT sc.concept_id, ts.name "
                    "FROM session_concepts sc "
                    "JOIN training_sessions ts ON sc.session_id = ts.id"
                ).fetchall()
                for concept_id, session_name in rows:
                    self.session_concept_map.setdefault(concept_id, set()).add(session_name)
            except sqlite3.OperationalError:
                pass

            # Custom vocab
            try:
                rows = con.execute("SELECT word, added_at FROM custom_vocab").fetchall()
                self.custom_vocab = [{"word": r[0], "added_at": r[1]} for r in rows]
            except sqlite3.OperationalError:
                pass

            con.close()
        except sqlite3.Error:
            pass

        # Base vocab from ndgi_ingest
        try:
            from ndgi.ndgi_ingest import DOMAIN_VOCAB
            custom_words = {v["word"] for v in self.custom_vocab}
            self.base_vocab = sorted([w for w in DOMAIN_VOCAB if w not in custom_words])
        except ImportError:
            self.base_vocab = []

    def _filter_by_session(self):
        """Apply session filter if set. Returns (concepts, edges)."""
        if not self.session_filter:
            return self.concepts[:MAX_NODES], self.edges[:MAX_EDGES]

        # Get concept IDs in the session
        session_concepts = set()
        for cid, sessions in self.session_concept_map.items():
            if self.session_filter in sessions:
                session_concepts.add(cid)

        if not session_concepts:
            return self.concepts[:MAX_NODES], self.edges[:MAX_EDGES]

        concepts = [c for c in self.concepts if c["id"] in session_concepts]
        concept_ids = {c["id"] for c in concepts}
        edges = [e for e in self.edges
                 if e["src"] in concept_ids and e["dst"] in concept_ids]

        return concepts[:MAX_NODES], edges[:MAX_EDGES]

    def _build_sessions_tab(self):
        """Build sessions tab content."""
        lines = []
        if not self.sessions:
            lines.append("  (no training sessions)")
        else:
            for s in self.sessions:
                status = "ACTIVE" if not s["ended_at"] else "ended"
                lines.append(f"  {s['name']}")
                lines.append(f"    Started: {s['started_at'] or '?'}")
                if s["ended_at"]:
                    lines.append(f"    Ended:   {s['ended_at']}")
                lines.append(f"    Concepts: {s['concept_count']}  "
                             f"Edges: {s['edge_count']}  [{status}]")
                lines.append("")
        return "\n".join(lines)

    def _build_concepts_tab(self):
        """Build concepts tab content."""
        lines = []
        if not self.concepts:
            lines.append("  (no concepts)")
        else:
            # Sort by confidence descending
            sorted_concepts = sorted(self.concepts,
                                     key=lambda c: c["confidence"], reverse=True)
            lines.append(f"  Total: {len(sorted_concepts)} concepts\n")

            # Count edges per concept for degree
            degree = {}
            for e in self.edges:
                degree[e["src"]] = degree.get(e["src"], 0) + 1
                degree[e["dst"]] = degree.get(e["dst"], 0) + 1

            for c in sorted_concepts[:100]:
                d = degree.get(c["id"], 0)
                sessions = self.session_concept_map.get(c["id"], set())
                session_str = f"  [{', '.join(sorted(sessions))}]" if sessions else ""
                lines.append(
                    f"  {c['label']:25s}  conf={c['confidence']:.2f}  "
                    f"deg={d:3d}  [{c['category']}]{session_str}"
                )
            if len(sorted_concepts) > 100:
                lines.append(f"\n  ... and {len(sorted_concepts) - 100} more")
        return "\n".join(lines)

    def _build_vocab_tab(self):
        """Build vocabulary tab content."""
        lines = []
        lines.append(f"  Base vocabulary ({len(self.base_vocab)} terms):")
        lines.append(f"  {', '.join(self.base_vocab)}")
        lines.append("")
        lines.append(f"  Custom vocabulary ({len(self.custom_vocab)} terms):")
        if self.custom_vocab:
            for v in self.custom_vocab:
                lines.append(f"    {v['word']:25s}  added: {v['added_at'] or '?'}")
        else:
            lines.append("    (none)")
        return "\n".join(lines)

    def _build_html(self):
        """Generate D3.js force-directed graph HTML."""
        concepts, edges = self._filter_by_session()

        # Assign session colors using HSL hues
        session_names = sorted({s["name"] for s in self.sessions})
        session_colors = {}
        for i, name in enumerate(session_names):
            hue = (i * 360 // max(len(session_names), 1)) % 360
            session_colors[name] = f"hsl({hue}, 70%, 55%)"

        # Build nodes
        nodes = []
        node_ids = set()
        for c in concepts:
            sessions = sorted(self.session_concept_map.get(c["id"], set()))
            color = CATEGORY_COLORS.get(c["category"], DEFAULT_NODE_COLOR)
            if sessions:
                color = session_colors.get(sessions[0], color)
            radius = 4 + (c["confidence"] or 0.5) * 8
            nodes.append({
                "id": c["id"],
                "label": c["label"],
                "category": c["category"],
                "confidence": c["confidence"],
                "sessions": sessions,
                "radius": round(radius, 1),
                "color": color,
            })
            node_ids.add(c["id"])

        # Build links
        links = []
        for e in edges:
            if e["src"] in node_ids and e["dst"] in node_ids:
                width = max(1, min(abs(e["weight"]), 6))
                links.append({
                    "source": e["src"],
                    "target": e["dst"],
                    "weight": e["weight"],
                    "width": round(width, 1),
                })

        # Session options for dropdown
        session_options = json.dumps(["All"] + [s["name"] for s in self.sessions])
        nodes_json = json.dumps(nodes)
        links_json = json.dumps(links)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aegis Memory Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; background: #1e1e2e; color: #cdd6f4; font-family: 'JetBrains Mono', monospace; overflow: hidden; }}
        #header {{ position: absolute; top: 10px; left: 10px; background: rgba(30,30,46,0.95); padding: 12px 16px; border: 1px solid #45475a; border-radius: 6px; z-index: 10; }}
        #header h3 {{ margin: 0 0 6px 0; color: #89b4fa; font-size: 13px; }}
        #header .stats {{ font-size: 11px; color: #6c7086; }}
        select {{ background: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 11px; margin-top: 6px; }}
        .legend {{ display: flex; gap: 12px; margin-top: 8px; font-size: 10px; flex-wrap: wrap; }}
        .legend span {{ display: flex; align-items: center; gap: 4px; }}
        .legend .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .link {{ stroke-opacity: 0.35; }}
        .node {{ stroke: #1e1e2e; stroke-width: 1.5px; cursor: pointer; }}
        .node:hover {{ stroke: #cdd6f4; stroke-width: 2.5px; }}
        .label {{ fill: #a6adc8; font-size: 9px; pointer-events: none; }}
        #tooltip {{ position: absolute; display: none; background: rgba(30,30,46,0.95); border: 1px solid #45475a; padding: 10px; border-radius: 4px; font-size: 11px; max-width: 300px; z-index: 20; }}
    </style>
</head>
<body>
    <div id="header">
        <h3>[AEGIS] Memory Graph</h3>
        <div class="stats">Nodes: {len(nodes)} | Edges: {len(links)}</div>
        <div class="legend">
            <span><span class="dot" style="background:#06b6d4"></span> auto</span>
            <span><span class="dot" style="background:#10b981"></span> photonic</span>
            <span><span class="dot" style="background:#3b82f6"></span> agent</span>
            <span><span class="dot" style="background:#f59e0b"></span> compute</span>
            <span><span class="dot" style="background:#a855f7"></span> security</span>
        </div>
    </div>
    <div id="tooltip"></div>
    <svg id="graph"></svg>

    <script>
        const nodes = {nodes_json};
        const links = {links_json};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#graph")
            .attr("width", width)
            .attr("height", height);

        const tooltip = d3.select("#tooltip");

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(50))
            .force("charge", d3.forceManyBody().strength(-100))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => d.radius + 2));

        const link = svg.append("g").selectAll("line")
            .data(links).enter().append("line")
            .attr("class", "link")
            .attr("stroke", "#45475a")
            .attr("stroke-width", d => d.width);

        const node = svg.append("g").selectAll("circle")
            .data(nodes).enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.radius)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", (event, d) => {{
                let info = `<b>${{d.label}}</b>`;
                info += `<br>Confidence: ${{d.confidence.toFixed(2)}}`;
                info += `<br>Category: ${{d.category}}`;
                if (d.sessions.length) info += `<br>Sessions: ${{d.sessions.join(", ")}}`;
                const edgeCount = links.filter(l =>
                    (l.source.id || l.source) === d.id ||
                    (l.target.id || l.target) === d.id
                ).length;
                info += `<br>Edges: ${{edgeCount}}`;
                tooltip.html(info)
                    .style("display", "block")
                    .style("left", (event.pageX + 12) + "px")
                    .style("top", (event.pageY - 10) + "px");
            }})
            .on("mouseout", () => tooltip.style("display", "none"));

        const labels = svg.append("g").selectAll("text")
            .data(nodes).enter().append("text")
            .attr("class", "label")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(d => d.label.length > 20 ? d.label.slice(0, 20) : d.label);

        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("cx", d => d.x).attr("cy", d => d.y);
            labels.attr("x", d => d.x).attr("y", d => d.y);
        }});

        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }}
        function dragged(event, d) {{
            d.fx = event.x; d.fy = event.y;
        }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }}
    </script>
</body>
</html>"""

    def show(self):
        """Open the two-pane GTK window. Blocks until closed."""
        win = Gtk.Window(title="Aegis Memory Graph Viewer")
        win.set_default_size(1400, 800)
        win.connect("destroy", Gtk.main_quit)

        # ── Left pane: Notebook with tabs ─────────────────────────────────
        notebook = Gtk.Notebook()

        # Dark theme colors
        bg = Gdk.RGBA()
        bg.parse("#1e1e2e")
        fg = Gdk.RGBA()
        fg.parse("#cdd6f4")

        def make_text_tab(content, tab_label):
            buf = Gtk.TextBuffer()
            buf.set_text(content)
            view = Gtk.TextView(buffer=buf)
            view.set_monospace(True)
            view.set_editable(False)
            view.modify_font(Pango.FontDescription("monospace 10"))
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            view.set_left_margin(8)
            view.set_right_margin(8)
            view.set_top_margin(8)
            view.override_background_color(Gtk.StateFlags.NORMAL, bg)
            view.override_color(Gtk.StateFlags.NORMAL, fg)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.add(view)
            label = Gtk.Label(label=tab_label)
            notebook.append_page(scroll, label)
            return buf

        sessions_buf = make_text_tab(self._build_sessions_tab(), "Sessions")
        concepts_buf = make_text_tab(self._build_concepts_tab(), "Concepts")
        vocab_buf = make_text_tab(self._build_vocab_tab(), "Vocabulary")

        # ── Refresh button ────────────────────────────────────────────────
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header_label = Gtk.Label()
        header_label.set_markup(
            '<span foreground="#89b4fa" font_weight="bold">  MEMORY GRAPH  </span>'
        )
        left_box.pack_start(header_label, False, False, 4)
        left_box.pack_start(notebook, True, True, 0)

        btn_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        refresh_btn = Gtk.Button(label="Refresh  \u21bb")
        refresh_btn.set_tooltip_text("Reload data from DB (Ctrl+R)")
        btn_bar.pack_start(refresh_btn, True, True, 4)
        left_box.pack_start(btn_bar, False, False, 4)

        # ── Right pane: WebKit2 graph ─────────────────────────────────────
        webview = WebKit2.WebView()
        settings = webview.get_settings()
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-developer-extras", False)
        webview.set_settings(settings)

        html = self._build_html()
        webview.load_html(html, "file:///")

        render_label = Gtk.Label()
        render_label.set_markup(
            '<span foreground="#a6e3a1" font_weight="bold">  GRAPH  </span>'
        )

        render_scroll = Gtk.ScrolledWindow()
        render_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        render_scroll.add(webview)

        render_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        render_box.pack_start(render_label, False, False, 4)
        render_box.pack_start(render_scroll, True, True, 0)

        # ── Refresh callback ──────────────────────────────────────────────
        def on_refresh(_btn=None):
            self.concepts = []
            self.edges = []
            self.sessions = []
            self.custom_vocab = []
            self.session_concept_map = {}
            self._load_data()
            sessions_buf.set_text(self._build_sessions_tab())
            concepts_buf.set_text(self._build_concepts_tab())
            vocab_buf.set_text(self._build_vocab_tab())
            webview.load_html(self._build_html(), "file:///")

        refresh_btn.connect("clicked", on_refresh)

        # Ctrl+R keyboard shortcut
        accel = Gtk.AccelGroup()
        key, mod = Gtk.accelerator_parse("<Control>r")
        accel.connect(key, mod, 0, lambda *_: on_refresh())
        win.add_accel_group(accel)

        # ── Assemble panes ────────────────────────────────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(left_box, resize=True, shrink=False)
        paned.pack2(render_box, resize=True, shrink=False)
        paned.set_position(480)

        win.add(paned)
        win.show_all()
        Gtk.main()


def launch_viewer(session_filter=None):
    """Launch the memory graph viewer in a subprocess so the REPL isn't blocked."""
    import subprocess
    script = os.path.abspath(__file__)
    cmd = [sys.executable, script]
    if session_filter:
        cmd.extend(["--session", session_filter])
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aegis Memory Graph Viewer")
    parser.add_argument("--session", type=str, default=None,
                        help="Filter to a specific training session")
    args = parser.parse_args()

    # Add src to path for imports
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    viewer = MemoryGraphViewer(session_filter=args.session)
    viewer.show()
