"""Passively observe selected local source states without alarm actions."""

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_SOURCE_ENTITY_IDS
from .runtime import (
    AlarmMeshConfigEntry,
    AlarmMeshRuntimeData,
    source_status_from_state,
)
from .status import evaluate_status


async def async_setup_entry(hass: HomeAssistant, entry: AlarmMeshConfigEntry) -> bool:
    """Subscribe before taking the initial snapshot, without yielding in between."""
    sources = tuple(entry.options.get(CONF_SOURCE_ENTITY_IDS, ()))
    runtime = AlarmMeshRuntimeData(sources, {}, evaluate_status(()))
    entry.runtime_data = runtime

    @callback
    def async_source_changed(event: Event[EventStateChangedData]) -> None:
        """Update only the selected source whose local state changed."""
        runtime.source_statuses[event.data["entity_id"]] = source_status_from_state(
            event.data["new_state"]
        )
        runtime.result = evaluate_status(runtime.source_statuses.values())

    if sources:
        entry.async_on_unload(
            async_track_state_change_event(hass, sources, async_source_changed)
        )

    # All of setup above and this snapshot run in one event-loop turn. The
    # listener is already installed, so changes cannot fall into a setup gap.
    runtime.source_statuses.update(
        (entity_id, source_status_from_state(hass.states.get(entity_id)))
        for entity_id in sources
    )
    runtime.result = evaluate_status(runtime.source_statuses.values())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlarmMeshConfigEntry) -> bool:
    """Let Home Assistant run async_on_unload callbacks and clear runtime_data."""
    return True
