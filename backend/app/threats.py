"""
Tracks cumulative detection counts per species, persisted to a JSON file.
"""

import json
import os
import threading
from pathlib import Path

_STORE_PATH = Path(os.getenv("THREAT_STORE_PATH", "threat_counts.json"))
_lock = threading.Lock()
_counts: dict[str, int] = {}


def _load() -> None:
    if _STORE_PATH.exists():
        try:
            _counts.update(json.loads(_STORE_PATH.read_text()))
        except (json.JSONDecodeError, OSError):
            pass


def _save() -> None:
    try:
        _STORE_PATH.write_text(json.dumps(_counts, indent=2))
    except OSError:
        pass


_load()


def record_threat(species: str) -> int:
    """Increment the count for *species* and persist. Returns new count."""
    with _lock:
        _counts[species] = _counts.get(species, 0) + 1
        _save()
        return _counts[species]


def get_threat_summary() -> list[dict]:
    """Return species sorted by detection count descending."""
    with _lock:
        return [
            {"species": s, "detections": c}
            for s, c in sorted(_counts.items(), key=lambda x: x[1], reverse=True)
        ]
