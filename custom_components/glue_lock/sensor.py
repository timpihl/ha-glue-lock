"""Sensor platform for the Glue Lock integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import GlueLock
from .coordinator import GlueConfigEntry, GlueCoordinator
from .entity import GlueEntity
from .state import CONNECTION_STATUSES, EVENT_STATES, connection_state, event_state


@dataclass(frozen=True, kw_only=True)
class GlueSensorDescription(SensorEntityDescription):
    """Describe a Glue sensor."""

    value_fn: Callable[[GlueLock], str | int | datetime | None]


def _event_time(lock: GlueLock) -> datetime | None:
    return dt_util.parse_datetime(lock.last_event_time) if lock.last_event_time else None


SENSORS: tuple[GlueSensorDescription, ...] = (
    GlueSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda lock: lock.battery,
    ),
    GlueSensorDescription(
        key="connection_status",
        translation_key="connection_status",
        device_class=SensorDeviceClass.ENUM,
        options=CONNECTION_STATUSES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda lock: connection_state(lock.connection_status),
    ),
    GlueSensorDescription(
        key="last_event",
        translation_key="last_event",
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_STATES,
        value_fn=lambda lock: event_state(lock.last_event_type),
    ),
    GlueSensorDescription(
        key="last_event_time",
        translation_key="last_event_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_event_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of a Glue account."""
    coordinator = entry.runtime_data
    async_add_entities(
        GlueSensor(coordinator, lock_id, description)
        for lock_id in coordinator.data
        for description in SENSORS
    )


class GlueSensor(GlueEntity, SensorEntity):
    """A value that Glue reports for a lock."""

    entity_description: GlueSensorDescription

    def __init__(
        self,
        coordinator: GlueCoordinator,
        lock_id: str,
        description: GlueSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, lock_id)
        self.entity_description = description
        self._attr_unique_id = f"{lock_id}_{description.key}"

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the value from the latest lock data."""
        lock = self.glue_lock
        return self.entity_description.value_fn(lock) if lock else None
