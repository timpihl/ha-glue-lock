"""The Glue Lock integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GlueApiClient
from .coordinator import GlueConfigEntry, GlueCoordinator

PLATFORMS = [Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GlueConfigEntry) -> bool:
    """Set up Glue Lock from a config entry."""
    client = GlueApiClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = GlueCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlueConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: GlueConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
