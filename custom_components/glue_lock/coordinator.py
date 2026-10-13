"""Data update coordinator for the Glue Lock integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GlueApiClient, GlueApiError, GlueAuthError, GlueLock
from .const import (
    CONF_FAST_POLL,
    CONF_POLL_INTERVAL,
    DEFAULT_FAST_POLL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    FAST_POLL_INTERVAL,
    FAST_POLL_WINDOW,
    MAX_FAILURES_BEFORE_UNAVAILABLE,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

GlueConfigEntry = ConfigEntry["GlueCoordinator"]


class GlueCoordinator(DataUpdateCoordinator[dict[str, GlueLock]]):
    """Read all locks of a Glue account with one request per poll."""

    config_entry: GlueConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: GlueConfigEntry, client: GlueApiClient
    ) -> None:
        """Initialize the coordinator."""
        seconds = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        self._poll_interval = timedelta(seconds=max(MIN_POLL_INTERVAL, seconds))
        self._fast_poll = bool(entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL))
        self._fast_poll_until = 0.0
        self._failures = 0
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._poll_interval,
        )

    def start_fast_polling(self) -> None:
        """Read the locks more often for a short time after an operation."""
        if not self._fast_poll:
            return
        self._fast_poll_until = monotonic() + FAST_POLL_WINDOW
        self.update_interval = timedelta(seconds=FAST_POLL_INTERVAL)

    async def _async_update_data(self) -> dict[str, GlueLock]:
        # The next poll is scheduled after this method, with this interval.
        if monotonic() >= self._fast_poll_until:
            self.update_interval = self._poll_interval

        try:
            locks = await self.client.get_locks()
        except GlueAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GlueApiError as err:
            self._failures += 1
            if self.data and self._failures < MAX_FAILURES_BEFORE_UNAVAILABLE:
                _LOGGER.warning(
                    "Could not read the locks from Glue (%s in a row): %s",
                    self._failures,
                    err,
                )
                return self.data
            raise UpdateFailed(str(err)) from err

        self._failures = 0
        return {lock.id: lock for lock in locks}
