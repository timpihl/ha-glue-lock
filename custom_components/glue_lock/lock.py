"""Lock platform for the Glue Lock integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .api import (
    OPERATION_LOCK,
    OPERATION_UNLOCK,
    STATUS_COMPLETED,
    STATUS_PENDING,
    GlueApiError,
    GlueOperation,
)
from .const import FAST_POLL_WINDOW, OPERATION_POLL_ATTEMPTS, OPERATION_POLL_INTERVAL
from .coordinator import GlueConfigEntry, GlueCoordinator
from .entity import GlueEntity
from .state import is_locked_from_event, is_reachable

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the locks of a Glue account."""
    coordinator = entry.runtime_data
    async_add_entities(
        GlueLockEntity(coordinator, lock_id) for lock_id in coordinator.data
    )


class GlueLockEntity(GlueEntity, LockEntity):
    """A Glue lock.

    The lock state always comes from the last lock event that Glue reports,
    never from the request. A failed lock operation is never shown as locked.
    """

    _attr_name = None

    def __init__(self, coordinator: GlueCoordinator, lock_id: str) -> None:
        """Initialize the lock."""
        super().__init__(coordinator, lock_id)
        self._attr_unique_id = lock_id
        self._operating = False
        # The operation that waits for a new lock event: "lock", "unlock" or None.
        self._pending: str | None = None
        self._pending_event_key: str | None = None
        self._cancel_pending_timeout: CALLBACK_TYPE | None = None

    @property
    def available(self) -> bool:
        """Return True when the Glue Hub can reach the lock."""
        lock = self.glue_lock
        return super().available and is_reachable(lock.connection_status)

    @property
    def is_locked(self) -> bool | None:
        """Return the state from the last lock event."""
        lock = self.glue_lock
        return is_locked_from_event(lock.last_event_type) if lock else None

    @property
    def is_locking(self) -> bool:
        """Return True while a lock operation waits for its lock event."""
        return self._pending == OPERATION_LOCK

    @property
    def is_unlocking(self) -> bool:
        """Return True while an unlock operation waits for its lock event."""
        return self._pending == OPERATION_UNLOCK

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self._async_operate(OPERATION_LOCK)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self._async_operate(OPERATION_UNLOCK)

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the timer when the entity is removed."""
        self._clear_pending()
        await super().async_will_remove_from_hass()

    async def _async_operate(self, operation_type: str) -> None:
        """Send one operation to Glue. An operation is never sent again automatically."""
        lock = self.glue_lock
        if lock is None:
            raise HomeAssistantError("The lock is no longer in the Glue account")
        if self._operating:
            raise HomeAssistantError(
                f"{lock.description}: another operation is in progress"
            )

        self._operating = True
        self._clear_pending()
        self._pending = operation_type
        self._pending_event_key = lock.event_key
        self.async_write_ha_state()

        keep_pending = False
        try:
            client = self.coordinator.client
            created = await client.create_operation(self._lock_id, operation_type)
            operation = await self._async_wait_for(created)
            if operation.status not in (STATUS_COMPLETED, STATUS_PENDING):
                reason = f" ({operation.reason})" if operation.reason else ""
                raise HomeAssistantError(
                    f"{lock.description}: {operation_type} {operation.status}{reason}"
                )
            if operation.status == STATUS_PENDING:
                _LOGGER.warning(
                    "%s: %s is still pending. The next poll sets the lock state",
                    lock.description,
                    operation_type,
                )
            keep_pending = True
        except GlueApiError as err:
            raise HomeAssistantError(
                f"{lock.description}: {operation_type} request failed: {err}"
            ) from err
        finally:
            self._operating = False
            if keep_pending:
                # Show locking/unlocking until Glue reports the new lock event.
                self._cancel_pending_timeout = async_call_later(
                    self.hass, FAST_POLL_WINDOW, self._async_pending_timed_out
                )
            else:
                self._pending = None
                self.async_write_ha_state()
            self.coordinator.start_fast_polling()
            await self.coordinator.async_refresh()

    async def _async_wait_for(self, created: GlueOperation) -> GlueOperation:
        """Poll the status of an operation until it is final. Only reads the status."""
        operation = created
        for _ in range(OPERATION_POLL_ATTEMPTS):
            if operation.finished:
                break
            await asyncio.sleep(OPERATION_POLL_INTERVAL)
            try:
                operation = await self.coordinator.client.get_operation(
                    self._lock_id, created.id
                )
            except GlueApiError:
                # Keep the last known status and try again.
                continue
        return operation

    @callback
    def _handle_coordinator_update(self) -> None:
        lock = self.glue_lock
        if (
            self._pending
            and not self._operating
            and lock is not None
            and lock.event_key != self._pending_event_key
        ):
            self._clear_pending()
        super()._handle_coordinator_update()

    @callback
    def _async_pending_timed_out(self, _now: datetime) -> None:
        self._cancel_pending_timeout = None
        self._pending = None
        self.async_write_ha_state()

    @callback
    def _clear_pending(self) -> None:
        if self._cancel_pending_timeout:
            self._cancel_pending_timeout()
            self._cancel_pending_timeout = None
        self._pending = None
