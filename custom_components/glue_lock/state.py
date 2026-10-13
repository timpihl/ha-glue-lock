"""Pure state logic for Glue locks.

This module has no Home Assistant imports, so it can be tested on its own.
"""

from __future__ import annotations

import re

CONNECTION_STATUSES = ["connected", "busy", "disconnected", "offline"]

_LOCKED_EVENTS = {"pressAndGo", "localLock", "manualLock", "remoteLock"}
_UNLOCKED_EVENTS = {"localUnlock", "manualUnlock", "remoteUnlock"}

# Sensor states, in snake_case so they can be translated.
EVENT_STATES = [
    "press_and_go",
    "local_lock",
    "manual_lock",
    "remote_lock",
    "local_unlock",
    "manual_unlock",
    "remote_unlock",
    "unknown",
]


def is_locked_from_event(event_type: str | None) -> bool | None:
    """Return the lock state for the last lock event, or None when not known."""
    if event_type in _LOCKED_EVENTS:
        return True
    if event_type in _UNLOCKED_EVENTS:
        return False
    return None


def is_reachable(connection_status: str | None) -> bool:
    """Return True when the Glue Hub can reach the lock.

    busy means that the lock is working, so it is reachable.
    """
    return connection_status in ("connected", "busy")


def event_state(event_type: str | None) -> str | None:
    """Convert an API event type (camelCase) to a sensor state."""
    if not event_type:
        return None
    state = re.sub(r"(?<!^)(?=[A-Z])", "_", event_type).lower()
    return state if state in EVENT_STATES else "unknown"


def connection_state(connection_status: str | None) -> str | None:
    """Return the connection status as a sensor state."""
    return connection_status if connection_status in CONNECTION_STATUSES else None
