"""Storage bootstrap, fixed source IDs and interrupted lifecycle regressions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_test_home_assistant,
)

from homeassistant import bootstrap, loader
from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import (
    RELOAD_AFTER_UPDATE_DELAY,
    ConfigEntryDisabler,
    ConfigEntryState,
    OperationNotAllowed,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN
from custom_components.alarmmesh.status import SourceStatus, evaluate_status

SOURCE = "binary_sensor.hall"
OTHER = "binary_sensor.kitchen"
THIRD = "binary_sensor.attic"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """One saved entry, with no simulated source state or setup yet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={CONF_SOURCE_ENTITY_IDS: [SOURCE]},
    )
    entry.add_to_hass(hass)
    return entry


def overview_ids(hass: HomeAssistant, entry_id: str) -> tuple[str, str]:
    """Resolve user-customizable IDs from their stable registry identities."""
    registry = er.async_get(hass)
    smoke = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry_id}_smoke")
    availability = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_source_availability"
    )
    assert smoke is not None and availability is not None
    return smoke, availability


def assert_overviews(
    hass: HomeAssistant, entry_id: str, smoke: str, availability: str
) -> None:
    smoke_id, availability_id = overview_ids(hass, entry_id)
    assert hass.states.get(smoke_id).state == smoke
    assert hass.states.get(availability_id).state == availability


async def save_sources(hass: HomeAssistant, entry_id: str, sources: list[str]) -> None:
    """Use the real options flow and wait for its supported automatic reload."""
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: sources}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


@asynccontextmanager
async def fresh_from_storage() -> AsyncIterator[HomeAssistant]:
    """Load a separate HA instance through its normal storage/bootstrap APIs."""
    async with async_test_home_assistant(load_registries=False) as fresh:
        # Same custom-integration enablement as the harness fixture for `hass`.
        fresh.data.pop(loader.DATA_CUSTOM_COMPONENTS)
        try:
            assert await bootstrap.async_load_base_functionality(fresh)
            yield fresh
        finally:
            for loaded in fresh.config_entries.async_entries():
                if loaded.state is ConfigEntryState.LOADED:
                    assert await fresh.config_entries.async_unload(loaded.entry_id)
            await fresh.async_stop(force=True)


@pytest.mark.parametrize("initial", ["on", "off", None])
async def test_storage_bootstrap_uses_current_sources(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict, initial: str | None
) -> None:
    """Start a fresh HA object from saved entries/registry, not an entry reload."""
    # add_to_hass intentionally does not save MockConfigEntry fixtures. A real
    # supported update schedules the initial persisted configuration for this test.
    hass.config_entries.async_update_entry(entry, title="Saved AlarmMesh")
    hass.states.async_set(SOURCE, "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    expected_registry = []
    for entity_id in overview_ids(hass, entry.entry_id):
        registered = registry.async_get(entity_id)
        renamed = registry.async_update_entity(
            entity_id,
            name=f"Custom {registered.domain}",
            new_entity_id=f"{registered.domain}.saved_alarmmesh_overview",
        )
        expected_registry.append(renamed)
    await hass.async_block_till_done()
    old_runtime = entry.runtime_data
    await hass.async_stop(force=True)
    assert "core.config_entries" in hass_storage
    assert "core.entity_registry" in hass_storage
    stored_options = deepcopy(hass_storage["core.config_entries"])

    async with fresh_from_storage() as fresh:
        restored = fresh.config_entries.async_get_entry(entry.entry_id)
        assert restored is not None and restored is not entry
        assert not hasattr(restored, "runtime_data")
        if initial is not None:
            fresh.states.async_set(SOURCE, initial)
        assert await fresh.config_entries.async_setup(restored.entry_id)
        assert restored.runtime_data is not old_runtime
        assert restored.options == entry.options
        assert_overviews(
            fresh,
            restored.entry_id,
            "unavailable" if initial is None else initial,
            "incomplete" if initial is None else "complete",
        )
        for expected in expected_registry:
            current = er.async_get(fresh).async_get(expected.entity_id)
            assert current.id == expected.id
            assert current.unique_id == expected.unique_id
            assert current.name == expected.name
        if initial is None:
            assert restored.runtime_data.source_statuses[SOURCE] is SourceStatus.MISSING
            fresh.states.async_set(SOURCE, "on")
            await fresh.async_block_till_done()
            assert_overviews(fresh, restored.entry_id, "on", "complete")
        assert old_runtime.source_statuses == {SOURCE: SourceStatus.SMOKE_REPORTED}
        assert hass_storage["core.config_entries"] == stored_options


@pytest.mark.parametrize("failure", ["false", "exception"])
@pytest.mark.parametrize("failed_platform", ["binary_sensor", "sensor"])
async def test_failed_platform_unload_reports_failure_and_recovers_after_restart(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_storage: dict,
    failure: str,
    failed_platform: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Respect HA's non-recoverable FAILED_UNLOAD; bootstrap, never force its state."""
    hass.config_entries.async_update_entry(entry, title="Saved AlarmMesh")
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    options = deepcopy(dict(entry.options))
    kwargs = (
        {"return_value": False}
        if failure == "false"
        else {"side_effect": RuntimeError("Simulated platform unload failure")}
    )
    with patch(
        f"homeassistant.components.{failed_platform}.async_unload_entry", **kwargs
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    # HA converts an exception in a forwarded platform into False; the entry
    # reports the generic failure while the platform log preserves its cause.
    assert entry.reason == "Unload failed"
    if failure == "exception":
        assert "Simulated platform unload failure" in caplog.text
    assert entry.runtime_data is old_runtime
    smoke_id, availability_id = overview_ids(hass, entry.entry_id)
    removed_id = smoke_id if failed_platform == "sensor" else availability_id
    surviving_id = availability_id if failed_platform == "sensor" else smoke_id
    assert hass.states.get(removed_id).state == "unavailable"
    assert hass.states.get(surviving_id).state == (
        "complete" if failed_platform == "sensor" else "off"
    )

    # The failed platform's listener and shared source subscription must remain
    # live. The successfully removed platform must stay detached.
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "unavailable")
        await hass.async_block_till_done()
        calc.assert_called_once()
        assert hass.states.get(surviving_id).state == (
            "incomplete" if failed_platform == "sensor" else "unavailable"
        )
        calc.reset_mock()
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        calc.assert_called_once()
    assert hass.states.get(removed_id).state == "unavailable"
    assert hass.states.get(surviving_id).state == (
        "complete" if failed_platform == "sensor" else "on"
    )
    assert entry.options == options
    with pytest.raises(OperationNotAllowed, match="non recoverable"):
        await hass.config_entries.async_reload(entry.entry_id)

    await hass.async_stop(force=True)
    assert "core.config_entries" in hass_storage
    async with fresh_from_storage() as fresh:
        restored = fresh.config_entries.async_get_entry(entry.entry_id)
        assert restored.state is ConfigEntryState.NOT_LOADED
        fresh.states.async_set(SOURCE, "on")
        assert await fresh.config_entries.async_setup(restored.entry_id)
        assert restored.options == options
        assert_overviews(fresh, restored.entry_id, "on", "complete")
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            fresh.states.async_set(SOURCE, "off")
            await fresh.async_block_till_done()
            calc.assert_called_once()
        assert_overviews(fresh, restored.entry_id, "off", "complete")


@pytest.mark.parametrize("recovering", ["unknown", "unavailable", None])
async def test_recovering_source_cannot_clear_other_smoke(
    hass: HomeAssistant, entry: MockConfigEntry, recovering: str | None
) -> None:
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: [SOURCE, OTHER]}
    )
    hass.states.async_set(SOURCE, "on")
    if recovering is not None:
        hass.states.async_set(OTHER, recovering)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert_overviews(hass, entry.entry_id, "on", "incomplete")
    hass.states.async_set(OTHER, "off")
    await hass.async_block_till_done()
    assert_overviews(hass, entry.entry_id, "on", "complete")


class SimulatedSmokeSource(BinarySensorEntity):
    """A real HA entity with simulated reports, for registry lifecycle tests."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_unique_id = "simulated_smoke_source"
    _attr_name = "Simulated smoke source"
    _attr_is_on = True


@pytest.mark.parametrize("operation", ["rename", "remove"])
async def test_source_registry_change_keeps_selected_ids_fixed(
    hass: HomeAssistant, entry: MockConfigEntry, operation: str
) -> None:
    assert await async_setup_component(hass, "binary_sensor", {})
    source = SimulatedSmokeSource()
    await hass.data[binary_sensor.DATA_COMPONENT].async_add_entities([source])
    old_id = source.entity_id
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: [old_id]}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    original_options = deepcopy(dict(entry.options))
    registry = er.async_get(hass)
    if operation == "rename":
        new_id = "binary_sensor.renamed_source"
        registry.async_update_entity(old_id, new_entity_id=new_id)
    else:
        registry.async_remove(old_id)
    await hass.async_block_till_done()
    assert hass.states.get(old_id) is None
    assert entry.runtime_data.source_entity_ids == (old_id,)
    assert entry.runtime_data.source_statuses == {old_id: SourceStatus.MISSING}
    assert entry.options == original_options
    assert_overviews(hass, entry.entry_id, "unavailable", "incomplete")
    if operation == "rename":
        assert source.entity_id == new_id
        source._attr_is_on = False
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            source.async_write_ha_state()
            await hass.async_block_till_done()
            calc.assert_not_called()
        await save_sources(hass, entry.entry_id, [new_id])
        assert_overviews(hass, entry.entry_id, "off", "complete")
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            hass.states.async_set(old_id, "on")
            await hass.async_block_till_done()
            calc.assert_not_called()
        source._attr_is_on = True
        source.async_write_ha_state()
        await hass.async_block_till_done()
        assert_overviews(hass, entry.entry_id, "on", "complete")


async def test_repeated_option_switches_and_return_to_old_source(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    for source in (SOURCE, OTHER, THIRD):
        hass.states.async_set(source, "off", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtimes = []
    for selected in (OTHER, THIRD, SOURCE, OTHER, SOURCE):
        old_runtimes.append(
            (entry.runtime_data, entry.runtime_data.source_statuses.copy())
        )
        await save_sources(hass, entry.entry_id, [selected])
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            for source in (SOURCE, OTHER, THIRD):
                if source != selected:
                    current = hass.states.get(source)
                    hass.states.async_set(
                        source,
                        "off" if current.state == "on" else "on",
                        {"device_class": "smoke"},
                    )
            await hass.async_block_till_done()
            calc.assert_not_called()
            current = hass.states.get(selected)
            changed = "off" if current.state == "on" else "on"
            hass.states.async_set(selected, changed, {"device_class": "smoke"})
            await hass.async_block_till_done()
            calc.assert_called_once()
        assert_overviews(hass, entry.entry_id, changed, "complete")
        assert entry.options == {CONF_SOURCE_ENTITY_IDS: [selected]}
        for old, snapshot in old_runtimes:
            assert old.source_statuses == snapshot


async def test_save_unreachable_source(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "binary_sensor",
        "test",
        "kitchen",
        suggested_object_id="kitchen",
        original_device_class="smoke",
    )
    hass.states.async_set(SOURCE, "on", {"device_class": "smoke"})
    hass.states.async_set(OTHER, "unavailable")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await save_sources(hass, entry.entry_id, [OTHER])
    assert entry.options == {CONF_SOURCE_ENTITY_IDS: [OTHER]}
    assert_overviews(hass, entry.entry_id, "unavailable", "incomplete")
    hass.states.async_set(OTHER, "off")
    await hass.async_block_till_done()
    assert_overviews(hass, entry.entry_id, "off", "complete")


@pytest.mark.parametrize("invalid", [None, [], [SOURCE, SOURCE], [OTHER]])
async def test_cancel_or_invalid_options_during_smoke(
    hass: HomeAssistant, entry: MockConfigEntry, invalid: list[str] | None
) -> None:
    hass.states.async_set(SOURCE, "on", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data
    original_options = deepcopy(dict(entry.options))
    result = await hass.config_entries.options.async_init(entry.entry_id)
    if invalid is not None:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SOURCE_ENTITY_IDS: invalid}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]
    hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert entry.options == original_options
    assert_overviews(hass, entry.entry_id, "on", "complete")
    hass.states.async_set(SOURCE, "off")
    await hass.async_block_till_done()
    assert_overviews(hass, entry.entry_id, "off", "complete")


async def test_disable_and_reenable_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    hass.states.async_set(SOURCE, "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    assert await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(entry, "runtime_data")
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "off")
        await hass.async_block_till_done()
        calc.assert_not_called()
    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    assert entry.runtime_data is not old_runtime
    assert_overviews(hass, entry.entry_id, "off", "complete")
    assert old_runtime.source_statuses == {SOURCE: SourceStatus.SMOKE_REPORTED}


async def test_disable_and_reenable_both_overviews(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    registry = er.async_get(hass)
    ids = overview_ids(hass, entry.entry_id)
    for entity_id in ids:
        registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    disabled_runtime = entry.runtime_data
    with patch(
        "custom_components.alarmmesh.entity.AlarmMeshEntity.async_write_ha_state",
        autospec=True,
        side_effect=Entity.async_write_ha_state,
    ) as write:
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        write.assert_not_called()
    assert disabled_runtime.source_statuses[SOURCE] is SourceStatus.SMOKE_REPORTED
    assert old_runtime.source_statuses[SOURCE] is SourceStatus.NO_SMOKE_REPORTED
    with patch(
        "custom_components.alarmmesh.entity.AlarmMeshEntity.async_write_ha_state",
        autospec=True,
        side_effect=Entity.async_write_ha_state,
    ) as write:
        # Install the spy before entity subscriptions capture the bound callback.
        for entity_id in ids:
            registry.async_update_entity(entity_id, disabled_by=None)
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1)
        )
        await hass.async_block_till_done()
        assert entry.runtime_data is not disabled_runtime
        assert_overviews(hass, entry.entry_id, "on", "complete")
        write.reset_mock()
        hass.states.async_set(SOURCE, "off")
        await hass.async_block_till_done()
        assert write.call_count == 2
    assert_overviews(hass, entry.entry_id, "off", "complete")


@pytest.mark.parametrize("operation", ["unload", "reload"])
async def test_changes_at_lifecycle_boundaries(
    hass: HomeAssistant, entry: MockConfigEntry, operation: str
) -> None:
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    real_unload = hass.config_entries.async_unload_platforms

    async def unload_with_change(*args):
        hass.states.async_set(SOURCE, "on")
        return await real_unload(*args)

    with patch.object(
        hass.config_entries, "async_unload_platforms", side_effect=unload_with_change
    ):
        if operation == "reload":
            assert await hass.config_entries.async_reload(entry.entry_id)
        else:
            assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    snapshot = old_runtime.source_statuses.copy()
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "off")
        await hass.async_block_till_done()
        assert calc.call_count == (1 if operation == "reload" else 0)
    assert old_runtime.source_statuses == snapshot
    if operation == "unload":
        assert await hass.config_entries.async_setup(entry.entry_id)
    assert_overviews(hass, entry.entry_id, "off", "complete")


async def test_old_unchanged_report_does_not_expire(
    hass: HomeAssistant, entry: MockConfigEntry, freezer
) -> None:
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        freezer.tick(timedelta(days=90))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        calc.assert_not_called()
    assert_overviews(hass, entry.entry_id, "off", "complete")
