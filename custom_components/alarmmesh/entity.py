"""Shared push-only lifecycle for the two AlarmMesh overview entities."""

from homeassistant.helpers.entity import Entity

from .runtime import AlarmMeshConfigEntry


class AlarmMeshEntity(Entity):
    """Read the entry-owned result and subscribe only while added to HA."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: AlarmMeshConfigEntry, suffix: str) -> None:
        """Use entry identity, independent of selection, names or state values."""
        self._runtime = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"

    async def async_added_to_hass(self) -> None:
        """Subscribe before HA writes the initial state from current properties."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._runtime.async_add_listener(self.async_write_ha_state)
        )
