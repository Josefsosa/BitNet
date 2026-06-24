"""
NDGi initialization constants.
Central DB path used by all NDGi Python modules.
"""
from pathlib import Path

LOG_DIR = Path("/home/jsosa/BitNet/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

NDGI_DB = str(LOG_DIR / "ndgi.db")
