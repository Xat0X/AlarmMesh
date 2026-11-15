"""Real HA lifecycle/storage/clock; all phone actions are explicit mocks."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import outputs as outputs
from test_linking_runtime import setup

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.maintenance import DEFAULT


async def settle(hass, entry):
    for _ in range(20):
        await hass.async_block_till_done()
        panel = entry.runtime_data.panel
        tasks = [panel.linking._task, panel.effects._task, panel.maintenance.task]
        if not any(tasks):
            return
        for task in tasks:
            if task is not None:
                await task
    pytest.fail("Maintenance did not settle")


async def prepare(hass, catalog_devices):
    add, _ = catalog_devices
    device = add(
        "SMSZB-120",
        "Develco",
        domain="siren",
        key="warning",
        idle="off",
        attrs={"supported_features": 31, "available_tones": ["burglar"]},
    )
    device["battery"] = device["register"](
        "sensor", "battery", "72", {"unit_of_measurement": "%"}
    )
    device["fault"] = device["register"]("binary_sensor", "fault", "off", {})
    entry = await setup(hass, [device["source"]])
    return entry, device


async def enable(hass, entry, **changes):
    m = entry.runtime_data.panel.maintenance
    value = {
        **deepcopy(DEFAULT),
        "enabled": True,
        "recipients": [
            {"service": "mobile_app_simulation_a", "enabled": True},
            {"service": "mobile_app_simulation_b", "enabled": True},
        ],
        **changes,
    }
    await m.save(value, m.revision, True)
    await settle(hass, entry)
    return m


async def advance(hass, entry, freezer, **delta):
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle(hass, entry)


async def test_default_off_preserves_old_settings_and_never_sends(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    original = deepcopy(entry.runtime_data.panel.effects.settings.value)
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    hass.states.async_set(d["fault"], "on")
    await settle(hass, entry)
    m = entry.runtime_data.panel.maintenance
    assert m.value == DEFAULT and not outputs[0] and not m.records
    assert entry.runtime_data.panel.effects.settings.value == original
    assert m.cancel_timer is None


async def test_battery_dedup_unknown_no_false_recovery_and_new_problem(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry, recovery=True)
    hass.states.async_set(d["battery"], "20", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    for value in ("19", "unknown", "unavailable", "18"):
        hass.states.async_set(d["battery"], value, {"unit_of_measurement": "%"})
        await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_set(d["battery"], "80", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 4
    hass.states.async_set(d["battery"], "9", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 6
    assert entry.runtime_data.result.smoke_status.name == "NO_SMOKE_REPORTED"


@pytest.mark.parametrize("minutes", [5, 15, 30, 60])
async def test_outage_delay_and_short_interruption(
    hass, catalog_devices, outputs, freezer, minutes
):
    entry, d = await prepare(hass, catalog_devices)
    m = await enable(hass, entry, delay=minutes, recovery=True)
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert m.cancel_timer is not None and not outputs[0]
    await advance(hass, entry, freezer, minutes=minutes - 1)
    assert not outputs[0]
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert m.cancel_timer is None
    await advance(hass, entry, freezer, minutes=minutes + 1)
    assert not outputs[0]
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    await advance(hass, entry, freezer, minutes=minutes)
    assert len(outputs[0]) == 2
    hass.states.async_set(d["source"], "unknown", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(outputs[0]) == 4


async def test_recipient_failure_isolated_and_not_retried(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry)
    outputs[1].add("mobile_app_simulation_a")
    hass.states.async_set(d["fault"], "on")
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    receipts = next(
        row
        for row in entry.runtime_data.panel.maintenance.snapshot()["issues"]
        if row["kind"] == "fault"
    )["receipts"]
    assert receipts["mobile_app_simulation_a"]["problem"] == "failed"
    assert receipts["mobile_app_simulation_b"]["problem"] == "accepted"
    outputs[1].clear()
    entry.runtime_data.panel.maintenance.changed()
    await settle(hass, entry)
    assert len(outputs[0]) == 2


async def test_reload_no_replay_and_new_startup_problem_is_quiet(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry)
    hass.states.async_set(d["battery"], "10", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    old = entry.runtime_data.panel.maintenance
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert len(outputs[0]) == 2 and old.closed and old.cancel_timer is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_set(d["fault"], "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    assert any(
        r["reason"] == "maintenance_baseline"
        for r in entry.runtime_data.panel.maintenance.snapshot()["issues"]
    )
    hass.states.async_set(d["fault"], "off")
    await settle(hass, entry)
    hass.states.async_set(d["fault"], "on")
    await settle(hass, entry)
    assert len(outputs[0]) == 4


async def test_identity_replacement_or_missing_does_not_recover_old_problem(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry, recovery=True)
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_remove(d["source"])
    hass.states.async_set(d["battery"], "unknown", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    er.async_get(hass).async_update_entity(
        d["source"], new_unique_id="replacement_smoke_zigbee2mqtt"
    )
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    hass.states.async_set(d["battery"], "95", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2


@pytest.mark.parametrize("value,unit", [("unknown", "%"), ("95", "V"), ("nan", "%")])
async def test_unknown_or_invalid_battery_never_alerts(
    hass, catalog_devices, outputs, value, unit
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry)
    hass.states.async_set(d["battery"], value, {"unit_of_measurement": unit})
    await settle(hass, entry)
    assert not outputs[0]


async def test_smoke_priority_and_unload_cleans_pending_timer(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    m = await enable(hass, entry)
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert (
        entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
        and not outputs[0]
    )
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert m.cancel_timer is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert m.closed and m.paused and m.cancel_timer is None and m.task is None
    m.changed()
    assert m.task is None


@pytest.mark.parametrize(
    "change",
    [
        {"delay": 1},
        {"delay": True},
        {"service": "switch.turn_on"},
        {"recipients": [{"service": "other_provider", "enabled": True}]},
    ],
)
async def test_invalid_settings_never_replace_saved_choices(
    hass, catalog_devices, outputs, change
):
    entry, _ = await prepare(hass, catalog_devices)
    m = entry.runtime_data.panel.maintenance
    original = deepcopy(m.value)
    with pytest.raises(AutomationError):
        await m.save({**original, **change}, m.revision, True)
    assert m.value == original and m.revision == 0 and not outputs[0]


async def test_corrupt_optional_storage_fails_closed_without_breaking_smoke(
    hass, catalog_devices, outputs
):
    entry, _ = await prepare(hass, catalog_devices)
    m = entry.runtime_data.panel.maintenance
    with (
        patch.object(m.store, "async_load", AsyncMock(return_value={"schema": 99})),
        patch.object(m.store, "async_save", AsyncMock()) as save,
    ):
        await m.load()
        assert m.fault == "maintenance_storage_error"
        save.assert_not_called()
    assert (
        entry.runtime_data.result.smoke_status.name == "NO_SMOKE_REPORTED"
        and not outputs[0]
    )


async def test_cached_good_battery_with_missing_source_is_not_recovery(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    await enable(hass, entry, recovery=True)
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_remove(d["source"])
    hass.states.async_set(d["battery"], "90", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(outputs[0]) == 4


async def test_reload_restarts_pending_outage_observation(
    hass, catalog_devices, outputs, freezer
):
    entry, d = await prepare(hass, catalog_devices)
    m = await enable(hass, entry, delay=5)
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    await advance(hass, entry, freezer, minutes=4)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert m.closed and m.cancel_timer is None
    await advance(hass, entry, freezer, minutes=1)
    assert not outputs[0]
    await advance(hass, entry, freezer, minutes=4)
    assert len(outputs[0]) == 2


async def test_disabling_cancels_pending_delivery_timer(hass, catalog_devices, outputs):
    entry, d = await prepare(hass, catalog_devices)
    m = await enable(hass, entry)
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert m.cancel_timer is not None
    await m.save({**deepcopy(m.value), "enabled": False}, m.revision, False)
    assert m.cancel_timer is None and m.task is None and not outputs[0]


async def test_intent_storage_failure_prevents_delivery(hass, catalog_devices, outputs):
    entry, d = await prepare(hass, catalog_devices)
    m = await enable(hass, entry)
    with patch.object(
        m.store,
        "async_save",
        AsyncMock(side_effect=OSError("private fixture storage error")),
    ):
        hass.states.async_set(d["fault"], "on")
        await settle(hass, entry)
    assert m.fault == "maintenance_storage_error" and not outputs[0]
    assert entry.runtime_data.result.smoke_status.name == "NO_SMOKE_REPORTED"


async def test_enabling_requires_exact_confirmation_and_current_revision(
    hass, catalog_devices, outputs
):
    entry, _ = await prepare(hass, catalog_devices)
    m = entry.runtime_data.panel.maintenance
    value = {
        **deepcopy(DEFAULT),
        "enabled": True,
        "recipients": [{"service": "mobile_app_simulation_a", "enabled": True}],
    }
    with pytest.raises(AutomationError, match="confirmation"):
        await m.save(value, 0, False)
    with pytest.raises(AutomationError, match="conflict"):
        await m.save(value, False, True)
    assert m.value == DEFAULT and m.revision == 0 and not outputs[0]


@pytest.mark.parametrize("cancel", [False, True])
async def test_startup_observation_waits_for_ha_started_and_listener_is_owned(
    hass, catalog_devices, outputs, cancel
):
    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
    from homeassistant.core import CoreState

    from custom_components.alarmmesh.maintenance import Maintenance

    entry, d = await prepare(hass, catalog_devices)
    old = await enable(hass, entry)
    await old.pause()
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    fresh = Maintenance(hass, entry, entry.runtime_data.panel.linking, lambda: None)
    await fresh.load()
    with patch.object(hass, "state", CoreState.starting):
        fresh.start()
        assert fresh.paused and fresh.startup_unsubscribe is not None
    if cancel:
        await fresh.close()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    if fresh.task:
        await fresh.task
    assert not outputs[0] and fresh.startup_unsubscribe is None
    if not cancel:
        assert any(
            row["reason"] == "maintenance_baseline"
            for row in fresh.snapshot()["issues"]
        )
        await fresh.close()
