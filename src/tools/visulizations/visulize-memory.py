import json
import os

NODE_CACHE = "docs/workon/runner_logs/knowledge_nodes.json"
OUTPUT_HTML = "src/tests/ndgi_memory_graph.html"

def generate_interactive_graph():
    print("🧬 Extracting live NDGi Knowledge Nodes for UI Rendering...")
    
    # Fallback simulation if json is empty or being rebuilt by the session proxy
    nodes_data = []
    if os.path.exists(NODE_CACHE):
        try:
            with open(NODE_CACHE, "r") as f:
                nodes_data = json.load(f)
        except:
            pass

    # Standardize data format into D3 links/nodes
    d3_nodes = []
    d3_links = []
    seen_nodes = set()

    # Process live nodes safely without recursive nesting loops
    for entry in nodes_data:
        if isinstance(entry, dict):
            node_id = entry.get("key", "Unknown_Node")
            node_cat = entry.get("cat", "PROJ")
            node_val = entry.get("val", "")
            
            if node_id not in seen_nodes:
                d3_nodes.append({"id": node_id, "group": node_cat, "details": str(node_val)})
                seen_nodes.add(node_id)

    # Auto-connect relevant infrastructure nodes to prevent orphaned graph views
    for i, node in enumerate(d3_nodes):
        if i > 0:
            d3_links.append({"source": d3_nodes[i-1]["id"], "target": node["id"], "value": 1})

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aegis NDGi Live Session Graph Topology</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; background-color: #0b0d0f; color: #e2e8f0; font-family: monospace; }}
        #title {{ position: absolute; top: 15px; left: 15px; background: rgba(15,23,42,0.85); padding: 12px; border: 1px solid #1e293b; border-radius: 4px; }}
        .node {{ stroke: #0b0d0f; stroke-width: 1.5px; cursor: pointer; }}
        .link {{ stroke: #334155; stroke-opacity: 0.6; stroke-width: 1.5px; }}
        text {{ fill: #94a3b8; font-size: 11px; pointer-events: none; }}
    </style>
</head>
<body>
    <div id="title">
        <span style="color:#38bdf8">[AEGIS SYSTEM ENGINE]</span><br>
        Live NDGi Knowledge Manifold Graph<br>
        Active Nodes: {len(d3_nodes)}
    </div>
    <svg width="100vw" height="100vh" id="graph"></svg>

    <script>
        const data = {{
            nodes: {json.dumps(d3_nodes)},
            links: {json.dumps(d3_links)}
        }};

        const svg = d3.select("#graph"),
              width = window.innerWidth,
              height = window.innerHeight;

        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(80))
            .force("charge", d3.forceManyBody().strength(-150))
            .force("center", d3.forceCenter(width / 2, height / 2));

        const link = svg.append("g").selectAll("line")
            .data(data.links).enter().append("line").attr("class", "link");

        const node = svg.append("g").selectAll("circle")
            .data(data.nodes).enter().append("circle")
            .attr("r", 8)
            .attr("class", "node")
            .attr("fill", d => {{
                if(d.group === "TASK") return "#f59e0b";
                if(d.group === "LEARN") return "#10b981";
                return "#3b82f6";
            }});

        node.append("title").text(d => `${{d.id}}\\nCategory: ${{d.group}}\\nVal: ${{d.details}}`);

        const labels = svg.append("g").selectAll("text")
            .data(data.nodes).enter().append("text")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(d => d.id.split('/').pop());

        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node.attr("cx", d => d.x).attr("cy", d => d.y);
            labels.attr("x", d => d.x).attr("y", d => d.y);
        }});
    </script>
</body>
</html>
"""
    
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html_content)
    print(f"✨ High-fidelity interactive UI generated perfectly at: {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_interactive_graph()