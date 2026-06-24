"""
NDGi Knowledge Nodes — persistent facts about project, env, user, tasks, learnings.
Injected into every LLM prompt so the model always knows context.

Categories:
  ENV   — ports, paths, tool versions, OS
  PROJ  — stack, deps, architecture decisions
  USER  — preferences, patterns, name, style
  TASK  — what's in progress, what's blocked
  LEARN — things the model got wrong, corrections

Storage: JSON file at LOG_DIR/knowledge_nodes.json
"""
import json
import os
import re
import time
from src.ndgi.ndgi_init import LOG_DIR

MAX_PROMPT_NODES = 20  # Limit injected nodes to avoid context bloat


class KnowledgeStore:
    CATEGORIES = ("ENV", "PROJ", "USER", "TASK", "LEARN")

    def __init__(self, path: str = None):
        self.path = path or str(LOG_DIR / "knowledge_nodes.json")
        self.nodes: dict[str, dict] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.nodes = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.nodes = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.nodes, f, indent=2)

    def _next_id(self) -> str:
        existing = [int(k.split("-")[1]) for k in self.nodes if k.startswith("KN-")]
        n = max(existing, default=0) + 1
        return f"KN-{n:03d}"

    def remember(self, key: str, value: str, category: str = "PROJ",
                 source: str = "user") -> tuple[str, bool]:
        """
        Store or update a knowledge node. Returns (node_id, was_updated).
        """
        # Update existing key if present
        for kid, node in self.nodes.items():
            if node.get("key", "").lower() == key.lower():
                node["value"] = value
                node["source"] = source
                node["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                node["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save()
                return kid, True

        cat = category.upper() if category.upper() in self.CATEGORIES else "PROJ"
        kid = self._next_id()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.nodes[kid] = {
            "id": kid,
            "type": "knowledge",
            "key": key,
            "value": value,
            "category": cat,
            "source": source,
            "confidence": 1.0,
            "trit": 1,
            "created": now,
            "last_used": now,
            "connections": [],
        }
        self._save()
        return kid, False

    def get(self, key: str) -> dict | None:
        """Retrieve a knowledge node by key (case-insensitive). Updates last_used."""
        for node in self.nodes.values():
            if node.get("key", "").lower() == key.lower():
                node["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save()
                return node
        return None

    def search(self, query: str) -> list[dict]:
        """Search nodes by key or value substring."""
        q = query.lower()
        return [n for n in self.nodes.values()
                if q in n.get("key", "").lower() or q in n.get("value", "").lower()]

    def list_all(self) -> list[dict]:
        return list(self.nodes.values())

    def list_by_category(self, category: str) -> list[dict]:
        """Return nodes filtered by category."""
        cat = category.upper()
        return [n for n in self.nodes.values() if n.get("category") == cat]

    def update_knowledge(self, key: str, new_value: str) -> bool:
        """Update value for an existing node by key. Returns True if found."""
        for node in self.nodes.values():
            if node.get("key", "").lower() == key.lower():
                node["value"] = new_value
                node["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                node["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save()
                return True
        return False

    def delete_knowledge(self, key: str) -> str | None:
        """Delete a specific node by exact key match. Returns removed ID or None."""
        for kid, node in list(self.nodes.items()):
            if node.get("key", "").lower() == key.lower():
                # Remove connections referencing this node
                for other in self.nodes.values():
                    conns = other.get("connections", [])
                    if kid in conns:
                        conns.remove(kid)
                del self.nodes[kid]
                self._save()
                return kid
        return None

    def forget(self, target: str) -> list[str]:
        """Remove nodes whose key matches target. Returns list of removed IDs."""
        removed = []
        for kid, node in list(self.nodes.items()):
            if target.lower() in node.get("key", "").lower():
                removed.append(kid)
                del self.nodes[kid]
        if removed:
            # Clean up stale connections
            for node in self.nodes.values():
                conns = node.get("connections", [])
                node["connections"] = [c for c in conns if c not in removed]
            self._save()
        return removed

    def connect(self, key_a: str, key_b: str) -> bool:
        """Create a bidirectional connection between two nodes by key."""
        node_a, node_b = None, None
        id_a, id_b = None, None
        for kid, node in self.nodes.items():
            if node.get("key", "").lower() == key_a.lower():
                node_a, id_a = node, kid
            if node.get("key", "").lower() == key_b.lower():
                node_b, id_b = node, kid
        if not node_a or not node_b or id_a == id_b:
            return False
        if id_b not in node_a.get("connections", []):
            node_a.setdefault("connections", []).append(id_b)
        if id_a not in node_b.get("connections", []):
            node_b.setdefault("connections", []).append(id_a)
        self._save()
        return True

    def get_related_nodes(self, node_id: str) -> list[dict]:
        """Return nodes connected to the given node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        conns = node.get("connections", [])
        return [self.nodes[c] for c in conns if c in self.nodes]

    def _relevance_score(self, node: dict) -> float:
        """Score a node for prompt injection relevance (higher = more relevant)."""
        score = node.get("confidence", 1.0)
        # Boost recently used nodes
        last_used = node.get("last_used", node.get("created", ""))
        if last_used:
            try:
                lu = time.mktime(time.strptime(last_used, "%Y-%m-%d %H:%M:%S"))
                age_hours = (time.time() - lu) / 3600
                score += max(0, 2.0 - age_hours / 12)  # decay over 24h
            except (ValueError, OverflowError):
                pass
        # Boost connected nodes
        score += len(node.get("connections", [])) * 0.1
        # Category priority: ENV > TASK > PROJ > USER > LEARN
        cat_boost = {"ENV": 0.5, "TASK": 0.4, "PROJ": 0.3, "USER": 0.2, "LEARN": 0.1}
        score += cat_boost.get(node.get("category", "PROJ"), 0)
        return score

    def prompt_block(self, max_nodes: int = MAX_PROMPT_NODES) -> str:
        """Compact knowledge summary for injection into LLM system prompt.
        Selects the most relevant nodes up to max_nodes to avoid context bloat."""
        if not self.nodes:
            return ""
        # Sort by relevance, take top N
        sorted_nodes = sorted(self.nodes.values(),
                              key=lambda n: self._relevance_score(n), reverse=True)
        selected = sorted_nodes[:max_nodes]
        lines = ["KNOWLEDGE NODES (facts I know about this project):"]
        for node in selected:
            conf = node.get("confidence", 1.0)
            conf_tag = f" [{conf:.0%}]" if conf < 1.0 else ""
            lines.append(f"  [{node['category']}] {node['key']}: {node['value']}{conf_tag}")
        if len(self.nodes) > max_nodes:
            lines.append(f"  ... ({len(self.nodes) - max_nodes} more nodes available)")
        return "\n".join(lines)

    def inject_knowledge_into_prompt(self, query: str = "",
                                     max_nodes: int = MAX_PROMPT_NODES) -> str:
        """Auto-select relevant nodes for a specific query and format for injection."""
        if not self.nodes:
            return ""
        if not query:
            return self.prompt_block(max_nodes)
        # Score nodes with query relevance boost
        q = query.lower()
        scored = []
        for node in self.nodes.values():
            score = self._relevance_score(node)
            # Boost nodes whose key or value matches query terms
            if q in node.get("key", "").lower() or q in node.get("value", "").lower():
                score += 3.0
            scored.append((score, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [n for _, n in scored[:max_nodes]]
        lines = ["WHAT I KNOW (relevant context):"]
        for node in selected:
            src_tag = f" (source: {node['source']})" if node.get("source") else ""
            lines.append(f"  [{node['category']}] {node['key']}: {node['value']}{src_tag}")
        return "\n".join(lines)

    def print_nodes(self):
        """Print formatted knowledge nodes to terminal."""
        if not self.nodes:
            print("\n[Knowledge] No nodes stored yet.")
            print("  Try: remember that NDGi proxy runs on port 8000\n")
            return
        cats: dict[str, list] = {}
        for node in self.nodes.values():
            cats.setdefault(node["category"], []).append(node)
        print("\nKNOWLEDGE NODES")
        print("-" * 50)
        for cat, nodes in sorted(cats.items()):
            print(f"  {cat}")
            for n in nodes:
                conns = n.get("connections", [])
                conn_str = f"  links:{len(conns)}" if conns else ""
                print(f"    {n['id']}  {n['key']}")
                print(f"         -> {n['value']}")
                print(f"           source:{n['source']}  {n.get('created', '')[:16]}{conn_str}")
        print()

    @staticmethod
    def parse_remember(text: str) -> tuple[str, str, str]:
        """
        Parse natural language remember command.
        'remember that NDGi runs on port 8000' -> (key, value, category)
        """
        t = re.sub(r'^remember\s+(that\s+)?', '', text, flags=re.I).strip()
        # Try "X is Y" / "X runs on Y" / "X uses Y" patterns
        for pat in (r'(.+?)\s+(?:is|are|=|runs on|uses|located at|lives at)\s+(.+)',):
            m = re.match(pat, t, re.I)
            if m:
                key = m.group(1).strip()[:80]
                val = m.group(2).strip()[:200]
                cat = _infer_category(key, val)
                return key, val, cat
        # Fallback: whole string as key
        return t[:80], "noted", _infer_category(t)


def _infer_category(key: str, value: str = "") -> str:
    """Infer knowledge category from key and value text."""
    combined = f"{key} {value}".lower()
    if any(w in combined for w in ("port", "path", "url", "host", "ip", "version", "os")):
        return "ENV"
    if any(w in combined for w in ("i prefer", "my ", "prefer", "like", "style", "name")):
        return "USER"
    if any(w in combined for w in ("task", "todo", "blocked", "working on", "next")):
        return "TASK"
    if any(w in combined for w in ("wrong", "mistake", "correction", "learned", "fix")):
        return "LEARN"
    return "PROJ"
