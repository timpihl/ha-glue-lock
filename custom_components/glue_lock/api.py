"""Client for the Glue cloud API.

This module has no Home Assistant imports, so it can be tested on its own.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

API_URL = "https://user-api.gluehome.com"
REQUEST_TIMEOUT = 30
USER_AGENT = "HomeAssistant-GlueLock"
API_KEY_SCOPES = ["events.read", "locks.read", "locks.write"]

OPERATION_LOCK = "lock"
OPERATION_UNLOCK = "unlock"

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"


class GlueApiError(Exception):
    """The Glue API could not be reached or returned an error."""


class GlueAuthError(GlueApiError):
    """The Glue API did not accept the credentials."""


@dataclass(frozen=True)
class GlueLock:
    """A lock as reported by the Glue API."""

    id: str
    serial_number: str
    description: str
    firmware_version: str | None
    battery: int | None
    connection_status: str | None
    last_event_type: str | None
    last_event_time: str | None

    @property
    def model(self) -> str | None:
        """The first four characters of the serial number identify the model."""
        return self.serial_number[:4] or None

    @property
    def event_key(self) -> str:
        """Identify the last lock event, so a new event can be detected."""
        return f"{self.last_event_type}@{self.last_event_time}"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> GlueLock:
        """Build a lock from an API response."""
        event = data.get("lastLockEvent") or {}
        return cls(
            id=data["id"],
            serial_number=data.get("serialNumber") or "",
            description=data.get("description") or "Glue Lock",
            firmware_version=data.get("firmwareVersion"),
            battery=data.get("batteryStatus"),
            connection_status=data.get("connectionStatus"),
            last_event_type=event.get("eventType"),
            last_event_time=event.get("eventTime"),
        )


@dataclass(frozen=True)
class GlueOperation:
    """A lock or unlock operation."""

    id: str
    status: str
    reason: str | None = None

    @property
    def finished(self) -> bool:
        """Return True when Glue has reported a final status."""
        return self.status != STATUS_PENDING

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> GlueOperation:
        """Build an operation from an API response."""
        return cls(id=data["id"], status=data["status"], reason=data.get("reason"))


async def _describe_error(response: aiohttp.ClientResponse) -> str:
    try:
        body = await response.json(content_type=None)
        title = body.get("title") or f"HTTP {response.status}"
        detail = body.get("detail")
        return f"{title}: {detail}" if detail else title
    except Exception:  # noqa: BLE001 - any unreadable body gets the generic text
        return f"HTTP {response.status} {response.reason or ''}".strip()


async def _request(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    auth: aiohttp.BasicAuth | None = None,
    json: Any = None,
) -> Any:
    try:
        async with session.request(
            method,
            f"{API_URL}{path}",
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            auth=auth,
            json=json,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            if response.status in (401, 403):
                raise GlueAuthError("Glue did not accept the credentials")
            if response.status >= 400:
                raise GlueApiError(await _describe_error(response))
            return await response.json(content_type=None)
    except asyncio.TimeoutError as err:
        raise GlueApiError("Timeout while talking to the Glue API") from err
    except (aiohttp.ClientError, ValueError) as err:
        raise GlueApiError(f"Could not talk to the Glue API: {err}") from err


async def create_api_key(
    session: aiohttp.ClientSession, username: str, password: str, name: str
) -> str:
    """Create an API key with the Glue account. The password is not kept."""
    data = await _request(
        session,
        "POST",
        "/v1/api-keys",
        auth=aiohttp.BasicAuth(username, password),
        json={"name": name, "scopes": API_KEY_SCOPES},
    )
    api_key = data.get("apiKey") if isinstance(data, dict) else None
    if not api_key:
        raise GlueApiError("Glue did not return an API key")
    return api_key


class GlueApiClient:
    """Talk to the Glue API with an API key."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._headers = {"Authorization": f"Api-Key {api_key}"}

    async def get_locks(self) -> list[GlueLock]:
        """Return all locks in the account."""
        data = await self._request("GET", "/v1/locks")
        return _parse(lambda: [GlueLock.from_json(item) for item in data or []])

    async def get_lock(self, lock_id: str) -> GlueLock:
        """Return one lock."""
        data = await self._request("GET", f"/v1/locks/{lock_id}")
        return _parse(lambda: GlueLock.from_json(data))

    async def create_operation(self, lock_id: str, operation_type: str) -> GlueOperation:
        """Send a lock or unlock operation."""
        data = await self._request(
            "POST", f"/v1/locks/{lock_id}/operations", json={"type": operation_type}
        )
        return _parse(lambda: GlueOperation.from_json(data))

    async def get_operation(self, lock_id: str, operation_id: str) -> GlueOperation:
        """Read the status of an operation. Never sends a new operation."""
        data = await self._request(
            "GET", f"/v1/locks/{lock_id}/operations/{operation_id}"
        )
        return _parse(lambda: GlueOperation.from_json(data))

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        return await _request(
            self._session, method, path, headers=self._headers, json=json
        )


def _parse(build: Any) -> Any:
    try:
        return build()
    except (KeyError, TypeError, AttributeError) as err:
        raise GlueApiError(f"Unexpected answer from the Glue API: {err!r}") from err
