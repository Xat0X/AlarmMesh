"""AlarmMesh foundation: config entry lifecycle without device behavior."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load an empty entry; no entities, services, or listeners are registered."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an empty entry; no runtime resources need cleanup yet."""
    return True
