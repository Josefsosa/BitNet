"""
NDGi Operations — logging, node listing, and OODA learning hook.
Interfaces with the NDGi SQLite DB at /home/jsosa/BitNet/logs/ndgi.db.
"""
import sqlite3
from datetime import datetime, timezone
from src.ndgi.ndgi_init import NDGI_DB


def _con():
    return sqlite3.connect(NDGI_DB)


def _ensure_actions_table():
    with _con() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent     TEXT,
                action    TEXT,
                summary   TEXT
            )
        """)


def log_action(agent: str, action: str, summary: str):
    """Log an NDGi action (ingest, learn, prune, etc.) to the actions table."""
    _ensure_actions_table()
    ts = datetime.now(timezone.utc).isoformat()
    with _con() as con:
        con.execute(
            "INSERT INTO actions (timestamp, agent, action, summary) VALUES (?,?,?,?)",
            (ts, agent, action, summary)
        )


def list_nodes(prefix: str, limit: int = 30) -> list[str]:
    """Return node labels matching a prefix from the nodes table."""
    with _con() as con:
        if prefix:
            rows = con.execute(
                "SELECT label FROM nodes WHERE label LIKE ? ORDER BY id DESC LIMIT ?",
                (f"{prefix}%", limit)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT label FROM nodes ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
    return [r[0] for r in rows]


def learn_from_cycle(prompt: str, file_path: str, agent: str, trit: int):
    """
    Called after each OODA cycle. Extracts concepts and updates graph.
    Import inline to avoid circular import.
    """
    from src.ndgi.ndgi_ingest import extract_concepts
    from src.ndgi.ndgi_graph_learn import learn, init_graph_schema
    init_graph_schema()
    concepts = extract_concepts(f"{prompt} {file_path} {agent}")
    if len(concepts) >= 2:
        ts = datetime.now(timezone.utc).isoformat()
        learn(concepts, trit, ts)
        log_action(agent, "LEARN-CYCLE", f"trit={trit} concepts={len(concepts)}")
