"""Tests for the pure state logic."""

from __future__ import annotations

import pytest

import glue_state as state


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("pressAndGo", True),
        ("localLock", True),
        ("manualLock", True),
        ("remoteLock", True),
        ("localUnlock", False),
        ("manualUnlock", False),
        ("remoteUnlock", False),
        ("unknown", None),
        ("somethingNew", None),
        (None, None),
    ],
)
def test_is_locked_from_event(event_type, expected):
    assert state.is_locked_from_event(event_type) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("connected", True),
        ("busy", True),
        ("disconnected", False),
        ("offline", False),
        (None, False),
    ],
)
def test_is_reachable(status, expected):
    assert state.is_reachable(status) is expected


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("pressAndGo", "press_and_go"),
        ("remoteUnlock", "remote_unlock"),
        ("unknown", "unknown"),
        ("somethingNew", "unknown"),
        (None, None),
    ],
)
def test_event_state(event_type, expected):
    assert state.event_state(event_type) == expected


def test_every_known_event_has_a_sensor_state():
    events = ["pressAndGo", "localLock", "manualLock", "remoteLock",
              "localUnlock", "manualUnlock", "remoteUnlock", "unknown"]
    assert sorted(state.event_state(event) for event in events) == sorted(state.EVENT_STATES)


def test_connection_state_drops_unknown_values():
    assert state.connection_state("busy") == "busy"
    assert state.connection_state("somethingNew") is None
    assert state.connection_state(None) is None
