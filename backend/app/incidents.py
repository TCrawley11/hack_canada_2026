import threading
from collections import deque
from datetime import datetime, timezone

_lock = threading.Lock()
_log: deque[dict] = deque(maxlen=20)


def log_incident(species: str, script: str) -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "species": species,
        "script": script,
    }
    with _lock:
        _log.append(entry)
    return entry


def get_incidents() -> list[dict]:
    with _lock:
        return list(_log)
