"""Base entity for the Glue Lock integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GlueLock
from .const import DOMAIN, MANUFACTURER
from .coordinator import GlueCoordinator


class GlueEntity(CoordinatorEntity[GlueCoordinator]):
    """An entity that belongs to one Glue lock."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GlueCoordinator, lock_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._lock_id = lock_id
        lock = coordinator.data[lock_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_id)},
            manufacturer=MANUFACTURER,
            model=lock.model,
            name=lock.description,
            serial_number=lock.serial_number or None,
            sw_version=lock.firmware_version,
        )

    @property
    def glue_lock(self) -> GlueLock | None:
        """Return the latest data for this lock."""
        return self.coordinator.data.get(self._lock_id)

    @property
    def available(self) -> bool:
        """Return True when Glue reports this lock."""
        return super().available and self.glue_lock is not None
