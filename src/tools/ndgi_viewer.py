"""
Aegis NDGi Viewer — Two-pane GTK+WebKit2 viewer for NDGi training data.

Left pane:  raw data dump (knowledge nodes, session state, concept graph)
Right pane: D3.js force-directed graph (color-coded by source)

Usage:
    from tools.ndgi_viewer import launch_viewer
    launch_viewer()
"""

import os
import json
import sqlite3

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2, GLib, Pango

# ANSI for terminal output before GTK window opens
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

WORKSPACE_ROOT = os.path.expanduser("~/workspace/aegis-ternary")
LOG_DIR = os.path.join(WORKSPACE_ROOT, "docs/workon/runner_logs")
KNOWLEDGE_FILE = os.path.join(LOG_DIR, "knowledge_nodes.json")
SESSION_FILE = os.path.join(LOG_DIR, "ndgi_session.json")
NDGI_DB = os.path.expanduser("~/BitNet/logs/ndgi.db")


class NdgiViewer:
    """GTK+WebKit2 two-pane NDGi training data viewer."""

    def __init__(self):
        self.knowledge = self._load_json(KNOWLEDGE_FILE)
        self.session = self._load_json(SESSION_FILE)
        self.concepts = []
        self.edges = []
        self._load_concept_graph()

    def _load_json(self, path):
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _load_concept_graph(self):
        if not os.path.isfile(NDGI_DB):
            return
        try:
            con = sqlite3.connect(NDGI_DB)
            # Concepts
            try:
                rows = con.execute(
                    "SELECT id, label, category, confidence FROM concepts"
                ).fetchall()
                self.concepts = [
                    {"id": r[0], "label": r[1], "category": r[2], "confidence": r[3]}
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
            con.close()
        except sqlite3.Error:
            pass

    def _build_raw_data(self):
        """Assemble raw text dump from all data sources."""
        lines = []

        # Knowledge nodes
        lines.append("═" * 60)
        lines.append("  KNOWLEDGE NODES")
        lines.append("═" * 60)
        if isinstance(self.knowledge, dict):
            for kid, node in self.knowledge.items():
                if isinstance(node, dict):
                    cat = node.get("category", "?")
                    key = node.get("key", kid)
                    val = node.get("value", "")
                    lines.append(f"  [{cat:8s}] {key}")
                    lines.append(f"            → {val}")
                    lines.append("")
                else:
                    lines.append(f"  {kid}: {node}")
                    lines.append("")
        else:
            lines.append("  (no data)")
        lines.append("")

        # Session state
        lines.append("═" * 60)
        lines.append("  NDGi SESSION STATE")
        lines.append("═" * 60)
        if isinstance(self.session, dict) and self.session:
            for sid, snode in self.session.items():
                if isinstance(snode, dict):
                    path = snode.get("path", sid)
                    trit = snode.get("trit", "?")
                    op = snode.get("op", "?")
                    ts = snode.get("ts", "")
                    lines.append(f"  {path}")
                    lines.append(f"    trit={trit}  op={op}  ts={ts}")
                    lines.append("")
                else:
                    lines.append(f"  {sid}: {snode}")
                    lines.append("")
        else:
            lines.append("  (no session data)")
        lines.append("")

        # Concept graph
        lines.append("═" * 60)
        lines.append("  CONCEPT GRAPH")
        lines.append("═" * 60)
        if self.concepts:
            lines.append(f"  Nodes: {len(self.concepts)}  Edges: {len(self.edges)}")
            lines.append("")
            for c in self.concepts[:50]:  # cap at 50 for readability
                lines.append(
                    f"  [{c['category']:8s}] {c['label']:30s}  "
                    f"conf={c['confidence']:.2f}"
                )
            if len(self.concepts) > 50:
                lines.append(f"  ... and {len(self.concepts) - 50} more")
            lines.append("")
            lines.append("  Top edges by weight:")
            sorted_edges = sorted(self.edges, key=lambda e: abs(e["weight"]), reverse=True)
            for e in sorted_edges[:30]:
                sign = "+" if e["weight"] >= 0 else ""
                lines.append(
                    f"    {e['src']:25s} ─── {e['dst']:25s}  "
                    f"w={sign}{e['weight']:.1f}  touches={e['touch_count']}"
                )
            if len(self.edges) > 30:
                lines.append(f"    ... and {len(self.edges) - 30} more edges")
        else:
            lines.append("  (no concept graph data)")
        lines.append("")

        return "\n".join(lines)

    def _build_graph_nodes_and_links(self):
        """Build D3.js nodes and links from all data sources."""
        nodes = []
        links = []
        node_ids = set()

        # Knowledge nodes → green
        if isinstance(self.knowledge, dict):
            for kid, node in self.knowledge.items():
                nid = f"k_{kid}"
                label = kid
                if isinstance(node, dict):
                    label = node.get("key", kid)
                nodes.append({
                    "id": nid, "label": label, "group": "knowledge",
                    "category": node.get("category", "") if isinstance(node, dict) else "",
                    "value": node.get("value", "") if isinstance(node, dict) else str(node),
                })
                node_ids.add(nid)

        # Session nodes → blue
        if isinstance(self.session, dict):
            for sid, snode in self.session.items():
                nid = f"s_{sid}"
                label = sid
                if isinstance(snode, dict):
                    label = snode.get("path", sid)
                    if len(label) > 30:
                        label = "…" + label[-28:]
                nodes.append({
                    "id": nid, "label": label, "group": "ndgi",
                    "op": snode.get("op", "") if isinstance(snode, dict) else "",
                    "ts": snode.get("ts", "") if isinstance(snode, dict) else "",
                })
                node_ids.add(nid)

        # Concept graph nodes → cyan
        for c in self.concepts:
            nid = f"c_{c['id']}"
            nodes.append({
                "id": nid, "label": c["label"], "group": "concept",
                "category": c["category"],
            })
            node_ids.add(nid)

        # Concept edges
        for e in self.edges:
            src = f"c_{e['src']}"
            dst = f"c_{e['dst']}"
            if src in node_ids and dst in node_ids:
                links.append({
                    "source": src, "target": dst,
                    "value": max(1, min(abs(e["weight"]), 5)),
                })

        return nodes, links

    def _build_html(self):
        """Generate D3.js force-directed graph HTML."""
        nodes, links = self._build_graph_nodes_and_links()
        nodes_json = json.dumps(nodes)
        links_json = json.dumps(links)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aegis NDGi Training Data Viewer</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; background: #0b0d0f; color: #e2e8f0; font-family: 'JetBrains Mono', monospace; overflow: hidden; }}
        #info {{ position: absolute; top: 15px; left: 15px; background: rgba(15,23,42,0.9); padding: 16px; border: 1px solid #1e293b; border-radius: 6px; z-index: 10; }}
        #info h3 {{ margin: 0 0 8px 0; color: #38bdf8; font-size: 14px; }}
        .legend {{ display: flex; gap: 16px; margin-top: 8px; font-size: 11px; }}
        .legend span {{ display: flex; align-items: center; gap: 4px; }}
        .legend .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
        .link {{ stroke-opacity: 0.4; }}
        .node {{ stroke: #0b0d0f; stroke-width: 1.5px; cursor: pointer; }}
        .node:hover {{ stroke: #f1f5f9; stroke-width: 2.5px; }}
        .label {{ fill: #94a3b8; font-size: 10px; pointer-events: none; }}
        #tooltip {{ position: absolute; display: none; background: rgba(15,23,42,0.95); border: 1px solid #334155; padding: 10px; border-radius: 4px; font-size: 11px; max-width: 300px; z-index: 20; }}
        #toggle {{ position: absolute; top: 15px; right: 15px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-family: monospace; font-size: 12px; z-index: 10; }}
        #toggle:hover {{ background: #334155; }}
    </style>
</head>
<body>
    <div id="info">
        <h3>[AEGIS] NDGi Training Data</h3>
        <div style="font-size:11px; color:#64748b;">
            Nodes: {len(nodes)} | Links: {len(links)}
        </div>
        <div class="legend">
            <span><span class="dot" style="background:#3b82f6"></span> NDGi Session</span>
            <span><span class="dot" style="background:#10b981"></span> Knowledge</span>
            <span><span class="dot" style="background:#06b6d4"></span> Concept Graph</span>
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

        const colorMap = {{
            "ndgi": "#3b82f6",
            "knowledge": "#10b981",
            "concept": "#06b6d4"
        }};

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(60))
            .force("charge", d3.forceManyBody().strength(-120))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(20));

        const link = svg.append("g").selectAll("line")
            .data(links).enter().append("line")
            .attr("class", "link")
            .attr("stroke", "#334155")
            .attr("stroke-width", d => Math.max(1, d.value));

        const node = svg.append("g").selectAll("circle")
            .data(nodes).enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.group === "knowledge" ? 6 : d.group === "concept" ? 7 : 8)
            .attr("fill", d => colorMap[d.group] || "#64748b")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", (event, d) => {{
                let info = `<b>${{d.label}}</b><br>Group: ${{d.group}}`;
                if (d.op) info += `<br>Op: ${{d.op}}`;
                if (d.ts) info += `<br>Time: ${{d.ts}}`;
                if (d.category) info += `<br>Cat: ${{d.category}}`;
                if (d.value) info += `<br>Val: ${{String(d.value).slice(0, 100)}}`;
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
            .text(d => d.label.length > 25 ? d.label.slice(-25) : d.label);

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
        win = Gtk.Window(title="Aegis NDGi Training Data Viewer")
        win.set_default_size(1400, 800)
        win.connect("destroy", Gtk.main_quit)

        # ── Left pane: raw data ───────────────────────────────────────
        source_buf = Gtk.TextBuffer()
        source_buf.set_text(self._build_raw_data())

        source_view = Gtk.TextView(buffer=source_buf)
        source_view.set_monospace(True)
        source_view.set_editable(False)
        source_view.modify_font(Pango.FontDescription("monospace 10"))
        source_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        source_view.set_left_margin(8)
        source_view.set_right_margin(8)
        source_view.set_top_margin(8)

        # Dark theme
        from gi.repository import Gdk
        bg = Gdk.RGBA()
        bg.parse("#1e1e2e")
        fg = Gdk.RGBA()
        fg.parse("#cdd6f4")
        source_view.override_background_color(Gtk.StateFlags.NORMAL, bg)
        source_view.override_color(Gtk.StateFlags.NORMAL, fg)

        source_scroll = Gtk.ScrolledWindow()
        source_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        source_scroll.add(source_view)

        source_label = Gtk.Label()
        source_label.set_markup(
            '<span foreground="#89b4fa" font_weight="bold">  RAW DATA  </span>'
        )

        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        source_box.pack_start(source_label, False, False, 4)
        source_box.pack_start(source_scroll, True, True, 0)

        # ── Refresh button ────────────────────────────────────────────
        btn_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        refresh_btn = Gtk.Button(label="Refresh  ↻")
        refresh_btn.set_tooltip_text("Reload data from disk/DB (Ctrl+R)")
        btn_bar.pack_start(refresh_btn, True, True, 4)
        source_box.pack_start(btn_bar, False, False, 4)

        # ── Right pane: WebKit2 graph ─────────────────────────────────
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

        # ── Refresh callback ──────────────────────────────────────────
        def on_refresh(_btn=None):
            self.knowledge = self._load_json(KNOWLEDGE_FILE)
            self.session = self._load_json(SESSION_FILE)
            self.concepts = []
            self.edges = []
            self._load_concept_graph()
            source_buf.set_text(self._build_raw_data())
            webview.load_html(self._build_html(), "file:///")

        refresh_btn.connect("clicked", on_refresh)

        # Ctrl+R keyboard shortcut
        accel = Gtk.AccelGroup()
        key, mod = Gtk.accelerator_parse("<Control>r")
        accel.connect(key, mod, 0, lambda *_: on_refresh())
        win.add_accel_group(accel)

        # ── Assemble panes ────────────────────────────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(source_box, resize=True, shrink=False)
        paned.pack2(render_box, resize=True, shrink=False)
        paned.set_position(500)

        win.add(paned)
        win.show_all()
        Gtk.main()


def launch_viewer():
    """Launch the NDGi viewer in a subprocess so the REPL isn't blocked."""
    import subprocess
    import sys
    script = os.path.abspath(__file__)
    subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    viewer = NdgiViewer()
    viewer.show()
