"""
Aegis Graph Viewer — Enhanced terminal graph display and
fixed D3.js browser visualization.

Terminal: progress bars, relative timestamps, sort options.
Browser: D3.js force-directed layout with color-coded node types.
"""

import os
import json
import time
import webbrowser
import tempfile
from datetime import datetime

WORKSPACE_ROOT = os.path.expanduser("~/workspace/aegis-ternary")
LOG_DIR = os.path.join(WORKSPACE_ROOT, "docs/workon/runner_logs")
NDGI_SESSION_FILE = os.path.join(LOG_DIR, "ndgi_session.json")
KNOWLEDGE_FILE = os.path.join(LOG_DIR, "knowledge_nodes.json")
AUDIT_FILE = os.path.join(LOG_DIR, "ai_audit_trail.json")

# ANSI
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; BL = "\033[1;34m"; DM = "\033[0;36m"
MG = "\033[0;35m"; WH = "\033[1;37m"; RS = "\033[0m"


class GraphViewer:
    def __init__(self, ndgi_session=None, knowledge_store=None, audit_store=None):
        self.ndgi = ndgi_session
        self.knowledge = knowledge_store
        self.audit = audit_store

    def _load_ndgi_nodes(self):
        """Load NDGi session nodes (dict: path -> {trit, hash, op, ts, attempts})."""
        if self.ndgi and hasattr(self.ndgi, 'nodes'):
            return self.ndgi.nodes
        try:
            if os.path.exists(NDGI_SESSION_FILE):
                return json.load(open(NDGI_SESSION_FILE))
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _load_knowledge_nodes(self):
        """Load knowledge nodes (dict: id -> {key, value, category, ...})."""
        if self.knowledge and hasattr(self.knowledge, 'nodes'):
            return self.knowledge.nodes
        try:
            if os.path.exists(KNOWLEDGE_FILE):
                return json.load(open(KNOWLEDGE_FILE))
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _load_audit_nodes(self):
        """Load audit trail entries (dict: id -> entry)."""
        if self.audit and hasattr(self.audit, 'entries'):
            return self.audit.entries
        try:
            if os.path.exists(AUDIT_FILE):
                return json.load(open(AUDIT_FILE))
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _relative_time(self, ts_str):
        """Convert timestamp string to relative time like '3h ago'."""
        try:
            # Try multiple formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%d %H:%M:%S%z"):
                try:
                    dt = datetime.strptime(ts_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return ts_str

            now = datetime.now()
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            diff = now - dt
            secs = int(diff.total_seconds())

            if secs < 60:
                return f"{secs}s ago"
            elif secs < 3600:
                return f"{secs // 60}m ago"
            elif secs < 86400:
                return f"{secs // 3600}h ago"
            else:
                return f"{secs // 86400}d ago"
        except Exception:
            return ts_str

    def _trit_bar(self, trit):
        """Render a progress bar for trit state."""
        if trit == 1:
            return f"{GR}[████████████]{RS} 100%"
        elif trit == -1:
            return f"{RD}[............]{RS}   0%"
        else:
            return f"{YL}[######......]{RS}  50%"

    def terminal_graph(self, sort_by="trit", show_hash=False):
        """Enhanced terminal graph with progress bars and relative timestamps."""
        nodes = self._load_ndgi_nodes()

        if not nodes:
            print(f"\n{YL}[GRAPH]{RS} No NDGi session nodes recorded.\n")
            return

        # Sort
        items = list(nodes.items())
        if sort_by == "time":
            items.sort(key=lambda x: x[1].get("ts", ""), reverse=True)
        elif sort_by == "trit":
            items.sort(key=lambda x: x[1].get("trit", 0), reverse=True)
        elif sort_by == "path":
            items.sort(key=lambda x: x[0])

        # Stats
        pos = sum(1 for _, n in items if n.get("trit") == 1)
        neg = sum(1 for _, n in items if n.get("trit") == -1)
        zero = len(items) - pos - neg

        print(f"\n{CY}╔══ NDGi SESSION GRAPH ══╗{RS}  "
              f"{GR}+{pos}{RS} {YL}○{zero}{RS} {RD}-{neg}{RS}  "
              f"({len(items)} nodes, sorted by {sort_by})\n")

        for path, node in items:
            trit = node.get("trit", 0)
            op = node.get("op", "?")
            ts = node.get("ts", "")
            content_hash = node.get("hash", "")
            attempts = node.get("attempts", 1)

            # Relative path
            try:
                rel = os.path.relpath(path, WORKSPACE_ROOT)
            except ValueError:
                rel = path

            # Trit symbol
            bar = self._trit_bar(trit)
            rel_time = self._relative_time(ts)

            # Operation color
            op_clr = GR if "create" in op else CY if "replace" in op else YL

            line = (f"  {bar}  {op_clr}{op:18s}{RS}  {rel}")
            if show_hash and content_hash:
                line += f"  {DM}#{content_hash}{RS}"
            line += f"  {DM}{rel_time}{RS}"
            if attempts > 1:
                line += f"  {YL}(x{attempts}){RS}"
            print(line)

        print()

    def browser_graph(self, output_path=None, include_knowledge=True):
        """Generate D3.js force-directed graph and open in browser."""
        ndgi_nodes = self._load_ndgi_nodes()
        knowledge_nodes = self._load_knowledge_nodes() if include_knowledge else {}
        audit_nodes = self._load_audit_nodes() if include_knowledge else {}

        d3_nodes = []
        d3_links = []
        seen = set()

        # NDGi session nodes (blue)
        for path, node in ndgi_nodes.items():
            try:
                label = os.path.relpath(path, WORKSPACE_ROOT)
            except ValueError:
                label = os.path.basename(path)
            node_id = f"ndgi:{label}"
            if node_id not in seen:
                d3_nodes.append({
                    "id": node_id,
                    "label": label,
                    "group": "ndgi",
                    "trit": node.get("trit", 0),
                    "op": node.get("op", ""),
                    "ts": node.get("ts", "")
                })
                seen.add(node_id)

        # Knowledge nodes (green) — handles dict format correctly
        for kid, knode in knowledge_nodes.items():
            if isinstance(knode, dict):
                label = knode.get("key", kid)
                node_id = f"kn:{label}"
                if node_id not in seen:
                    d3_nodes.append({
                        "id": node_id,
                        "label": label,
                        "group": "knowledge",
                        "category": knode.get("category", "PROJ"),
                        "value": knode.get("value", "")
                    })
                    seen.add(node_id)

        # Audit nodes (orange)
        for aid, anode in audit_nodes.items():
            if isinstance(anode, dict):
                label = anode.get("relative_path", aid)
                node_id = f"aud:{aid}"
                if node_id not in seen:
                    d3_nodes.append({
                        "id": node_id,
                        "label": f"{aid}: {label}",
                        "group": "audit",
                        "op": anode.get("operation", ""),
                        "trit": anode.get("trit_result", 0)
                    })
                    seen.add(node_id)

        # Build links — connect nodes of same group sequentially
        ndgi_ids = [n["id"] for n in d3_nodes if n["group"] == "ndgi"]
        kn_ids = [n["id"] for n in d3_nodes if n["group"] == "knowledge"]
        aud_ids = [n["id"] for n in d3_nodes if n["group"] == "audit"]

        for ids in (ndgi_ids, kn_ids, aud_ids):
            for i in range(1, len(ids)):
                d3_links.append({"source": ids[i - 1], "target": ids[i], "value": 1})

        # Cross-links: audit -> ndgi (same file)
        for anode in d3_nodes:
            if anode["group"] == "audit":
                for nnode in d3_nodes:
                    if nnode["group"] == "ndgi" and nnode["label"] in anode["label"]:
                        d3_links.append({"source": anode["id"], "target": nnode["id"], "value": 2})

        html = self._generate_html(d3_nodes, d3_links)

        if output_path is None:
            output_path = os.path.join(WORKSPACE_ROOT, "src/tests/ndgi_memory_graph.html")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)

        print(f"\n{GR}[GRAPH]{RS} D3.js graph written: {output_path}")
        print(f"  {DM}Nodes: {len(d3_nodes)}  Links: {len(d3_links)}{RS}")

        try:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")
            print(f"  {GR}Opened in browser.{RS}\n")
        except Exception:
            print(f"  {YL}Open manually: file://{os.path.abspath(output_path)}{RS}\n")

    def _generate_html(self, nodes, links):
        """Generate the D3.js HTML content."""
        nodes_json = json.dumps(nodes)
        links_json = json.dumps(links)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aegis NDGi Graph — All Sources</title>
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
    </style>
</head>
<body>
    <div id="info">
        <h3>[AEGIS] NDGi Memory Graph</h3>
        <div style="font-size:11px; color:#64748b;">
            Nodes: {len(nodes)} | Links: {len(links)}
        </div>
        <div class="legend">
            <span><span class="dot" style="background:#3b82f6"></span> NDGi Session</span>
            <span><span class="dot" style="background:#10b981"></span> Knowledge</span>
            <span><span class="dot" style="background:#f59e0b"></span> Audit Trail</span>
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
            "audit": "#f59e0b"
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
            .attr("stroke-width", d => d.value === 2 ? 2 : 1);

        const node = svg.append("g").selectAll("circle")
            .data(nodes).enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.group === "knowledge" ? 6 : 8)
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
                if (d.value) info += `<br>Val: ${{d.value}}`;
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
