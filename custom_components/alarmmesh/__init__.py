"""Observe local smoke states and optionally dispatch explicitly configured actions."""

from homeassistant.const import Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_SOURCE_ENTITY_IDS
from .groups import GroupStore
from .panel import PanelController, async_prepare
from .runtime import (
    AlarmMeshConfigEntry,
    AlarmMeshRuntimeData,
    source_status_from_state,
)
from .status import evaluate_status

PLATFORMS = (Platform.BINARY_SENSOR, Platform.SENSOR)


async def async_setup_entry(hass: HomeAssistant, entry: AlarmMeshConfigEntry) -> bool:
    """Subscribe before taking the initial snapshot, without yielding in between."""
    sources = tuple(entry.options.get(CONF_SOURCE_ENTITY_IDS, ()))
    runtime = AlarmMeshRuntimeData(sources, {}, evaluate_status(()))
    entry.runtime_data = runtime
    entry.async_on_unload(runtime.async_clear_listeners)

    @callback
    def async_source_changed(event: Event[EventStateChangedData]) -> None:
        """Update only the selected source whose local state changed."""
        runtime.source_statuses[event.data["entity_id"]] = source_status_from_state(
            event.data["new_state"]
        )
        runtime.async_set_result(evaluate_status(runtime.source_statuses.values()))
        runtime.async_notify_observers()

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
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        # The pinned HA version may log a platform failure without raising it
        # from async_forward_entry_setups. Disabled entities still initialize
        # their platform, so readiness is independent of entity subscriptions.
        if runtime.initialized_platforms != set(PLATFORMS):
            raise ConfigEntryError("Could not set up both AlarmMesh overview platforms")
        runtime.panel = PanelController(hass, entry, await async_prepare(hass))
        await runtime.panel.async_start()
    except Exception:
        if runtime.panel is not None:
            await runtime.panel.async_close()
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        # HA runs async_on_unload callbacks when entry setup fails as well.
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlarmMeshConfigEntry) -> bool:
    """Remove entities before HA stops sources and clears entry runtime data."""
    panel = entry.runtime_data.panel
    if panel is not None:
        await panel.linking.pause()
    try:
        unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except Exception:
        if panel is not None:
            panel.hub.publish()
        raise
    if unloaded and entry.runtime_data.panel is not None:
        await entry.runtime_data.panel.async_close()
    elif panel is not None:
        panel.hub.publish()  # Keep actions paused after a failed teardown.
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AlarmMeshConfigEntry) -> None:
    """Remove only this entry's organizational groups on explicit entry deletion."""
    await GroupStore(hass, entry.entry_id).store.async_remove()
