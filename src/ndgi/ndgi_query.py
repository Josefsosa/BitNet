"""
NDGi Query CLI
Usage: python3 -m src.ndgi.ndgi_query <concept>
Returns top associated concepts and confidence.
"""
import sys
from src.ndgi.ndgi_graph_learn import infer, init_graph_schema
from src.ndgi.ndgi_ops import list_nodes


def query(concept: str):
    init_graph_schema()
    results = infer(concept, top_n=10)
    if not results:
        print(f"NDGi: no learned associations for '{concept}'")
        return
    print(f"\nNDGi associations for '{concept}':")
    print("-" * 40)
    for r in results:
        bar = "#" * int(max(0, r['weight']) * 5)
        sign = "+" if r['weight'] >= 0 else "-"
        print(f"  {sign}{abs(r['weight']):.2f} {bar:20s} {r['concept']}")
    print()


def dump_all():
    init_graph_schema()
    nodes = list_nodes("")
    print(f"\nNDGi graph: {len(nodes)} nodes")
    for n in nodes[:20]:
        print(f"  {n}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        dump_all()
    else:
        query(sys.argv[1])
