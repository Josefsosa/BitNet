"""
NDGi Concept Graph — weighted learning edges.
Nodes: concepts (file paths, agent names, task types, keywords).
Edges: co-occurrence weight, trit-signed (+1 positive, -1 negative).
Learning: weight += trit on each co-occurrence.
Inference: given a concept, return top-N associated concepts by weight.
"""
import sqlite3
from src.ndgi.ndgi_init import NDGI_DB

def _con(): return sqlite3.connect(NDGI_DB)

def init_graph_schema():
    with _con() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS concept_edges (
                src TEXT,
                dst TEXT,
                weight REAL DEFAULT 0.0,
                trit_sum INTEGER DEFAULT 0,
                touch_count INTEGER DEFAULT 0,
                last_ts TEXT,
                PRIMARY KEY (src, dst)
            );
            CREATE TABLE IF NOT EXISTS concepts (
                id TEXT PRIMARY KEY,
                label TEXT,
                category TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT
            );
        """)

def learn(concepts: list[str], trit: int, timestamp: str):
    """
    Record co-occurrence of all concept pairs in this cycle.
    trit=1 reinforces, trit=-1 weakens edge weights.
    """
    with _con() as con:
        for i in range(len(concepts)):
            for j in range(i+1, len(concepts)):
                src, dst = sorted([concepts[i], concepts[j]])
                con.execute("""
                    INSERT INTO concept_edges (src, dst, weight, trit_sum, touch_count, last_ts)
                    VALUES (?,?,?,?,1,?)
                    ON CONFLICT(src,dst) DO UPDATE SET
                        weight = weight + ?,
                        trit_sum = trit_sum + ?,
                        touch_count = touch_count + 1,
                        last_ts = ?
                """, (src, dst, float(trit), trit, timestamp,
                      float(trit), trit, timestamp))
        # Ensure concepts are registered as nodes
        for c in concepts:
            con.execute("""
                INSERT INTO concepts (id, label, category, created_at)
                VALUES (?,?,?,?)
                ON CONFLICT(id) DO NOTHING
            """, (c, c, "auto", timestamp))

def infer(concept: str, top_n: int = 5) -> list[dict]:
    """Return top-N associated concepts by edge weight."""
    with _con() as con:
        rows = con.execute("""
            SELECT dst as peer, weight FROM concept_edges WHERE src=?
            UNION
            SELECT src as peer, weight FROM concept_edges WHERE dst=?
            ORDER BY weight DESC LIMIT ?
        """, (concept, concept, top_n)).fetchall()
    return [{"concept": r[0], "weight": r[1]} for r in rows]

def confidence(concept: str) -> float:
    """Return normalized confidence for a concept (0.0-1.0)."""
    with _con() as con:
        row = con.execute(
            "SELECT confidence FROM concepts WHERE id=?", (concept,)
        ).fetchone()
    return row[0] if row else 0.5
