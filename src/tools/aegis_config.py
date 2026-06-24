"""
Aegis Config — load/save/merge configuration from ~/.aegis/config.json.

Precedence: CLI args > config file > hardcoded defaults.
"""

import os
import json
import copy
from datetime import datetime

AEGIS_CONFIG_DIR = os.path.expanduser("~/.aegis")
AEGIS_CONFIG_FILE = os.path.join(AEGIS_CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "version": 1,
    "inference": {
        "endpoint": "http://localhost:8080/v1/chat/completions",
        "type": "bitnet_local",
    },
    "persona": "",
    "ndgi": {
        "memory_mode": "ternary",
        "base_url": "http://localhost:8000",
    },
    "agents": {
        "photnx": True,
        "sentinel": True,
        "trutch": True,
        "ciba": True,
        "archon": True,
        "pathfndr": True,
    },
}


def load_config() -> dict:
    """Load from ~/.aegis/config.json, merge with DEFAULT_CONFIG.

    Missing keys are filled from defaults. Returns a complete config dict.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    if os.path.isfile(AEGIS_CONFIG_FILE):
        try:
            with open(AEGIS_CONFIG_FILE, "r") as f:
                user = json.load(f)
            _deep_merge(config, user)
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config: dict) -> None:
    """Write config to ~/.aegis/config.json with timestamp."""
    os.makedirs(AEGIS_CONFIG_DIR, exist_ok=True)
    config["_saved_at"] = datetime.now().isoformat()
    with open(AEGIS_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def merge_config_into_globals(config: dict) -> dict:
    """Return a dict of overrides for startup globals.

    Keys: api_url, ndgi_base, persona, enabled_agents.
    """
    return {
        "api_url": config.get("inference", {}).get(
            "endpoint", DEFAULT_CONFIG["inference"]["endpoint"]
        ),
        "ndgi_base": config.get("ndgi", {}).get(
            "base_url", DEFAULT_CONFIG["ndgi"]["base_url"]
        ),
        "persona": config.get("persona", ""),
        "enabled_agents": config.get("agents", DEFAULT_CONFIG["agents"]),
    }


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (mutates base)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
