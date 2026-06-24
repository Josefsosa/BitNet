"""
NDGi Research Ingester
Ingest plain text or JSON -> extract concepts -> learn edges.
No external NLP deps. Keyword extraction via frequency + domain vocabulary.
"""
import re
import json
from datetime import datetime, timezone
from src.ndgi.ndgi_graph_learn import learn, init_graph_schema
from src.ndgi.ndgi_ops import log_action

# Domain vocabulary — photonics + AI + Aegis terms
DOMAIN_VOCAB = {
    "photonic","waveguide","trit","ternary","bitnet","ndgi","ooda",
    "manifold","sensor","laser","modulator","mach-zehnder","bet",
    "pathfinder","photnx","sentinel","trutch","archon","ciba",
    "inference","quantized","silicon","optical","fiber","beam",
    "fourier","diffraction","resonator","multiplexing","sdm","wdm",
    "paem","bssm","qpu","tst","skip-zero","pstla","trit_pos","trit_neg"
}

def extract_concepts(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", text.lower())
    return list({w for w in words if w in DOMAIN_VOCAB})

def ingest_text(text: str, trit: int = 1, source: str = "manual"):
    init_graph_schema()
    concepts = extract_concepts(text)
    if len(concepts) < 2:
        print(f"NDGi ingest: only {len(concepts)} concepts found -- skipping learn")
        return concepts
    ts = datetime.now(timezone.utc).isoformat()
    learn(concepts, trit, ts)
    log_action("NDGi-INGEST", f"trit={trit}", f"{source}: {len(concepts)} concepts")
    print(f"NDGi ingested {len(concepts)} concepts from {source}: {concepts}")
    return concepts

def ingest_json(path: str, trit: int = 1):
    with open(path) as f:
        data = json.load(f)
    text = json.dumps(data)
    return ingest_text(text, trit, source=path)

def ingest_kv(pairs: dict, trit: int = 1):
    text = " ".join(f"{k} {v}" for k, v in pairs.items())
    return ingest_text(text, trit, source="kv-injection")

if __name__ == "__main__":
    # Quick test
    sample = """
    The NDGi manifold uses Bessel beam non-diffractive profiles for
    analog matrix-vector multiplication. PHOTNX agent routes via
    PATHFINDER MoE using BET-encoded ternary weights with skip-zero
    optimization on the Q.ant QPU photonic TST accelerator.
    """
    concepts = ingest_text(sample, trit=1, source="test")
    print(f"Extracted: {concepts}")
