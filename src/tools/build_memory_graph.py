"""
Build Memory Graph — graph construction + export utilities.
Used by NDGiMemoryAgent and memory_graph_viewer.

Functions:
    build_full_graph()       — all concepts/edges/sessions
    build_session_graph(name) — filtered to a specific session
    export_to_file(graph, name) — write JSON to ~/.oakland/memory-graphs/
    get_graph_stats()        — quick counts without full load
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ndgi.ndgi_init import NDGI_DB

MEMORY_GRAPHS_DIR = Path.home() / ".oakland" / "memory-graphs"


def _con():
    return sqlite3.connect(NDGI_DB)


def build_full_graph() -> dict:
    """Load all concepts, edges, and sessions from SQLite."""
    with _con() as con:
        # Concepts
        try:
            concepts = [
                {"id": r[0], "label": r[1], "category": r[2],
                 "confidence": r[3], "created_at": r[4]}
                for r in con.execute(
                    "SELECT id, label, category, confidence, created_at "
                    "FROM concepts"
                ).fetchall()
            ]
        except sqlite3.OperationalError:
            concepts = []

        # Edges
        try:
            edges = [
                {"src": r[0], "dst": r[1], "weight": r[2],
                 "trit_sum": r[3], "touch_count": r[4], "last_ts": r[5]}
                for r in con.execute(
                    "SELECT src, dst, weight, trit_sum, touch_count, last_ts "
                    "FROM concept_edges"
                ).fetchall()
            ]
        except sqlite3.OperationalError:
            edges = []

        # Sessions
        try:
            sessions = [
                {"id": r[0], "name": r[1], "started_at": r[2],
                 "ended_at": r[3], "concept_count": r[4], "edge_count": r[5]}
                for r in con.execute(
                    "SELECT id, name, started_at, ended_at, concept_count, edge_count "
                    "FROM training_sessions ORDER BY started_at DESC"
                ).fetchall()
            ]
        except sqlite3.OperationalError:
            sessions = []

    return {
        "concepts": concepts,
        "edges": edges,
        "sessions": sessions,
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "concept_count": len(concepts),
            "edge_count": len(edges),
            "session_count": len(sessions),
        },
    }


def build_session_graph(session_name: str) -> dict:
    """Build graph filtered to concepts/edges belonging to a specific session."""
    with _con() as con:
        # Find session
        try:
            session_row = con.execute(
                "SELECT id, name, started_at, ended_at, concept_count, edge_count "
                "FROM training_sessions WHERE name=? "
                "ORDER BY started_at DESC LIMIT 1",
                (session_name,)
            ).fetchone()
        except sqlite3.OperationalError:
            return build_full_graph()

        if not session_row:
            return build_full_graph()

        sid = session_row[0]

        # Get session concept IDs
        try:
            concept_ids = [r[0] for r in con.execute(
                "SELECT DISTINCT concept_id FROM session_concepts WHERE session_id=?",
                (sid,)
            ).fetchall()]
        except sqlite3.OperationalError:
            concept_ids = []

        if not concept_ids:
            return {
                "concepts": [], "edges": [],
                "sessions": [{"id": session_row[0], "name": session_row[1],
                              "started_at": session_row[2], "ended_at": session_row[3],
                              "concept_count": session_row[4], "edge_count": session_row[5]}],
                "metadata": {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "session_filter": session_name,
                    "concept_count": 0, "edge_count": 0, "session_count": 1,
                },
            }

        placeholders = ",".join("?" * len(concept_ids))

        # Filtered concepts
        concepts = [
            {"id": r[0], "label": r[1], "category": r[2],
             "confidence": r[3], "created_at": r[4]}
            for r in con.execute(
                f"SELECT id, label, category, confidence, created_at "
                f"FROM concepts WHERE id IN ({placeholders})",
                concept_ids
            ).fetchall()
        ]

        # Filtered edges (both endpoints in session)
        edges = [
            {"src": r[0], "dst": r[1], "weight": r[2],
             "trit_sum": r[3], "touch_count": r[4], "last_ts": r[5]}
            for r in con.execute(
                f"SELECT src, dst, weight, trit_sum, touch_count, last_ts "
                f"FROM concept_edges "
                f"WHERE src IN ({placeholders}) AND dst IN ({placeholders})",
                concept_ids + concept_ids
            ).fetchall()
        ]

    session_info = {
        "id": session_row[0], "name": session_row[1],
        "started_at": session_row[2], "ended_at": session_row[3],
        "concept_count": session_row[4], "edge_count": session_row[5],
    }

    return {
        "concepts": concepts,
        "edges": edges,
        "sessions": [session_info],
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_filter": session_name,
            "concept_count": len(concepts),
            "edge_count": len(edges),
            "session_count": 1,
        },
    }


def export_to_file(graph: dict, name: str) -> str:
    """Write graph dict to ~/.oakland/memory-graphs/<name>_<timestamp>.json."""
    MEMORY_GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.json"
    path = MEMORY_GRAPHS_DIR / filename
    path.write_text(json.dumps(graph, indent=2))
    return str(path)


def get_graph_stats() -> dict:
    """Quick stats without full graph load."""
    with _con() as con:
        try:
            concept_count = con.execute(
                "SELECT COUNT(*) FROM concepts"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            concept_count = 0

        try:
            edge_count = con.execute(
                "SELECT COUNT(*) FROM concept_edges"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            edge_count = 0

        try:
            session_count = con.execute(
                "SELECT COUNT(*) FROM training_sessions"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            session_count = 0

        try:
            top_concepts = [
                {"concept": r[0], "degree": r[1]}
                for r in con.execute("""
                    SELECT c.id, COUNT(*) as degree
                    FROM concepts c
                    LEFT JOIN concept_edges e ON c.id = e.src OR c.id = e.dst
                    GROUP BY c.id
                    ORDER BY degree DESC
                    LIMIT 10
                """).fetchall()
            ]
        except sqlite3.OperationalError:
            top_concepts = []

    return {
        "concept_count": concept_count,
        "edge_count": edge_count,
        "session_count": session_count,
        "top_concepts": top_concepts,
    }
