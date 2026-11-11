"""Read-only combined smoke report from the existing runtime result."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import AlarmMeshEntity
from .runtime import AlarmMeshConfigEntry
from .status import SmokeStatus


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmMeshConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add exactly one smoke overview without polling or restoring state."""
    async_add_entities([AlarmMeshSmokeSensor(entry)])
    entry.runtime_data.initialized_platforms.add(Platform.BINARY_SENSOR)


class AlarmMeshSmokeSensor(AlarmMeshEntity, BinarySensorEntity):
    """Indeterminate smoke is unavailable, never an explicit no-smoke report."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_translation_key = "smoke"

    def __init__(self, entry: AlarmMeshConfigEntry) -> None:
        super().__init__(entry, "smoke")

    @property
    def available(self) -> bool:
        """A smoke report stays available even when other sources are missing."""
        return self._runtime.result.smoke_status is not SmokeStatus.INDETERMINATE

    @property
    def is_on(self) -> bool | None:
        """Return only the existing combined report, without recalculating it."""
        smoke = self._runtime.result.smoke_status
        if smoke is SmokeStatus.INDETERMINATE:
            return None
        return smoke is SmokeStatus.SMOKE_REPORTED
