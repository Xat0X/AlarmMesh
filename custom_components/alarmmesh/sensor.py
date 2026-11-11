"""Read-only source-information completeness, not a fire-safety assessment."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import AlarmMeshEntity
from .runtime import AlarmMeshConfigEntry
from .status import SourceAvailability


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmMeshConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add exactly one enum overview, independent of source reachability."""
    async_add_entities([AlarmMeshSourceAvailabilitySensor(entry)])
    entry.runtime_data.initialized_platforms.add(Platform.SENSOR)


class AlarmMeshSourceAvailabilitySensor(AlarmMeshEntity, SensorEntity):
    """Expose the valid runtime availability result, including not configured."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "source_availability"
    _attr_options = [availability.value for availability in SourceAvailability]

    def __init__(self, entry: AlarmMeshConfigEntry) -> None:
        super().__init__(entry, "source_availability")

    @property
    def native_value(self) -> str:
        """Return a stable enum option from the shared result."""
        return self._runtime.result.source_availability.value
