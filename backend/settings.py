"""
Settings module — persistent config for editable agent parameters.

Stores settings in data/settings.json so they survive restarts.
"""

import json
import os
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

_DEFAULTS = {
    "search_role": "software engineer",
}


def get_settings() -> dict:
    """Load settings from disk, falling back to defaults."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            # Merge with defaults so new keys are always present
            merged = {**_DEFAULTS, **saved}
            return merged
        except Exception:
            pass
    return dict(_DEFAULTS)


def update_settings(updates: dict) -> dict:
    """Update settings and persist to disk. Returns the full settings dict."""
    current = get_settings()
    # Only allow known keys
    for key in _DEFAULTS:
        if key in updates:
            current[key] = updates[key]
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)
    return current
