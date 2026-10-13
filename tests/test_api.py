"""Tests for the Glue API client. They never call the real Glue API."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

import glue_api as api

LOCK_JSON = {
    "id": "00000000-0000-4000-8000-000000000001",
    "serialNumber": "GLUE-TEST-0001",
    "description": "Front door",
    "firmwareVersion": "2.5",
    "batteryStatus": 100,
    "lastLockEvent": {"eventType": "pressAndGo", "eventTime": "2026-10-01T16:24:55Z"},
    "connectionStatus": "connected",
}


class FakeResponse:
    def __init__(self, status=200, body=None, reason="OK"):
        self.status = status
        self.reason = reason
        self._body = body

    async def json(self, content_type=None):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Records requests and answers them from a queue."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def run(coro):
    return asyncio.run(coro)


def test_get_locks_parses_the_response_and_sends_the_api_key():
    session = FakeSession(FakeResponse(body=[LOCK_JSON]))
    locks = run(api.GlueApiClient(session, "secret").get_locks())

    assert len(locks) == 1
    lock = locks[0]
    assert lock.id == LOCK_JSON["id"]
    assert lock.description == "Front door"
    assert lock.model == "GLUE"
    assert lock.battery == 100
    assert lock.connection_status == "connected"
    assert lock.last_event_type == "pressAndGo"
    assert lock.event_key == "pressAndGo@2026-10-01T16:24:55Z"

    method, url, kwargs = session.calls[0]
    assert (method, url) == ("GET", "https://user-api.gluehome.com/v1/locks")
    assert kwargs["headers"]["Authorization"] == "Api-Key secret"


def test_lock_without_event_has_no_state():
    data = {k: v for k, v in LOCK_JSON.items() if k != "lastLockEvent"}
    lock = api.GlueLock.from_json(data)
    assert lock.last_event_type is None
    assert lock.last_event_time is None


def test_empty_lock_list():
    session = FakeSession(FakeResponse(body=None))
    assert run(api.GlueApiClient(session, "secret").get_locks()) == []


def test_create_operation_posts_the_type():
    session = FakeSession(FakeResponse(status=201, body={"id": "op-1", "status": "pending"}))
    operation = run(api.GlueApiClient(session, "secret").create_operation("lock-1", "unlock"))

    assert operation.id == "op-1"
    assert not operation.finished
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://user-api.gluehome.com/v1/locks/lock-1/operations")
    assert kwargs["json"] == {"type": "unlock"}


def test_get_operation_reads_the_status():
    session = FakeSession(FakeResponse(body={"id": "op-1", "status": "failed", "reason": "doorOpen"}))
    operation = run(api.GlueApiClient(session, "secret").get_operation("lock-1", "op-1"))

    assert operation.finished
    assert operation.status == "failed"
    assert operation.reason == "doorOpen"
    assert session.calls[0][:2] == ("GET", "https://user-api.gluehome.com/v1/locks/lock-1/operations/op-1")


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_raises_auth_error(status):
    session = FakeSession(FakeResponse(status=status, body={}))
    with pytest.raises(api.GlueAuthError):
        run(api.GlueApiClient(session, "wrong").get_locks())


def test_api_error_includes_title_and_detail():
    session = FakeSession(FakeResponse(status=409, body={"title": "Conflict", "detail": "Lock is busy"}))
    with pytest.raises(api.GlueApiError, match="Conflict: Lock is busy"):
        run(api.GlueApiClient(session, "secret").create_operation("lock-1", "lock"))


def test_api_error_without_json_body():
    session = FakeSession(FakeResponse(status=502, body=ValueError("no json"), reason="Bad Gateway"))
    with pytest.raises(api.GlueApiError, match="HTTP 502 Bad Gateway") as err:
        run(api.GlueApiClient(session, "secret").get_locks())
    assert not isinstance(err.value, api.GlueAuthError)


@pytest.mark.parametrize("error", [aiohttp.ClientConnectionError("down"), asyncio.TimeoutError()])
def test_network_errors_become_api_errors(error):
    session = FakeSession(error)
    with pytest.raises(api.GlueApiError):
        run(api.GlueApiClient(session, "secret").get_locks())


def test_unexpected_answer_becomes_api_error():
    session = FakeSession(FakeResponse(body={"status": "pending"}))
    with pytest.raises(api.GlueApiError, match="Unexpected answer"):
        run(api.GlueApiClient(session, "secret").get_operation("lock-1", "op-1"))


def test_create_api_key_uses_basic_auth_and_returns_the_key():
    session = FakeSession(FakeResponse(status=201, body={"apiKey": "new-key"}))
    key = run(api.create_api_key(session, "user", "password", "home-assistant"))

    assert key == "new-key"
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://user-api.gluehome.com/v1/api-keys")
    assert kwargs["auth"] == aiohttp.BasicAuth("user", "password")
    assert kwargs["json"] == {
        "name": "home-assistant",
        "scopes": ["events.read", "locks.read", "locks.write"],
    }
    assert "Authorization" not in kwargs["headers"]


def test_create_api_key_with_wrong_password():
    session = FakeSession(FakeResponse(status=401, body={}))
    with pytest.raises(api.GlueAuthError):
        run(api.create_api_key(session, "user", "wrong", "home-assistant"))


def test_create_api_key_without_key_in_answer():
    session = FakeSession(FakeResponse(status=201, body={}))
    with pytest.raises(api.GlueApiError):
        run(api.create_api_key(session, "user", "password", "home-assistant"))
