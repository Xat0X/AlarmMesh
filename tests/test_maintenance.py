"""Maintenance is cached, device-bound evidence, never a smoke/health decision."""

import pytest
from test_catalog import catalog_devices as catalog_devices
from test_linking_runtime import setup

from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.capabilities import Capabilities


async def test_maintenance_unknown_without_device_bound_evidence(hass, catalog_devices):
    add, calls = catalog_devices
    item = add("Unreviewed model", "Unknown vendor")
    hass.states.async_set("sensor.unrelated_battery", "8", {"device_class": "battery"})
    cap = Capabilities(hass)
    info = cap.describe(item["source"])
    assert info["status"] == "detection_only" and not info["controls"]
    assert info["details"]["maintenance"] == {
        "battery_percent": None,
        "battery_low": None,
        "fault": None,
    }
    assert not calls


@pytest.mark.parametrize("unit", ["V", "mV", "°C", ["%"], {"unit": "%"}])
async def test_conflicting_battery_unit_is_not_presented_as_percentage(
    hass, catalog_devices, unit
):
    add, calls = catalog_devices
    item = add("HS1SA-E-PLUS", "Heiman")
    item["register"]("sensor", "battery", "95", {"unit_of_measurement": unit})
    details = Capabilities(hass).details(item["source"])
    assert details["maintenance"]["battery_percent"] is None
    raw = next(row for row in details["values"] if row["key"] == "battery")
    assert raw["value"] == 95 and raw["unit"] == unit
    assert not calls


async def test_live_battery_pushes_and_unload_detaches_without_smoke_change(
    hass, catalog_devices
):
    add, calls = catalog_devices
    item = add("SMSZB-120", "Develco")
    battery = item["register"]("sensor", "battery", "72", {"unit_of_measurement": "%"})
    entry = await setup(hass, [item["source"]])
    panel = entry.runtime_data.panel
    result = entry.runtime_data.result
    observations = []

    def listener():
        observations.append(panel.snapshot())

    panel.hub.listeners.add(listener)
    hass.states.async_set(battery, "12", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert (
        observations[-1]["sources"][0]["capability"]["details"]["maintenance"][
            "battery_percent"
        ]
        == 12.0
    )
    assert entry.runtime_data.result == result
    assert panel.snapshot()["selftest"] is None and not calls
    assert await hass.config_entries.async_unload(entry.entry_id)
    observations.clear()
    hass.states.async_set(battery, "8", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert observations == []
    panel.hub.listeners.discard(listener)


@pytest.mark.parametrize(
    "value", ["unknown", "unavailable", "nan", "inf", "-1", "101", "bad"]
)
async def test_invalid_battery_stays_unknown(hass, catalog_devices, value):
    add, calls = catalog_devices
    item = add("HS1SA-E-PLUS", "Heiman")
    item["register"]("sensor", "battery", value, {"unit_of_measurement": "%"})
    details = Capabilities(hass).details(item["source"])
    assert details["maintenance"]["battery_percent"] is None
    assert not calls


async def test_bound_battery_and_fault_never_change_smoke(hass, catalog_devices):
    add, calls = catalog_devices
    item = add("SMSZB-120", "Develco")
    battery = item["register"]("sensor", "battery", "12", {"unit_of_measurement": "%"})
    low = item["register"]("binary_sensor", "battery_low", "off", {})
    fault = item["register"]("binary_sensor", "fault", "on", {})
    cap = Capabilities(hass)
    assert cap.details(item["source"])["maintenance"] == {
        "battery_percent": 12.0,
        "battery_low": False,
        "fault": True,
    }
    hass.states.async_set(battery, "80", {"unit_of_measurement": "%"})
    hass.states.async_set(low, "on")
    hass.states.async_set(fault, "unknown")
    assert cap.details(item["source"])["maintenance"] == {
        "battery_percent": 80.0,
        "battery_low": True,
        "fault": None,
    }
    assert hass.states.is_state(item["source"], "off")
    assert not calls


async def test_zha_diagnostics_require_same_device_and_provider(hass, catalog_devices):
    add, calls = catalog_devices
    item = add("SMSZB-120", "Develco", origin="zha", domain="siren", key="warning")
    item["register"]("sensor", "battery", "19", {"device_class": "battery"}, "battery")
    item["register"](
        "binary_sensor", "battery_low", "on", {"device_class": "battery"}, "battery"
    )
    fault = item["register"](
        "binary_sensor", "fault", "on", {"device_class": "problem"}, "problem"
    )
    assert Capabilities(hass).details(item["source"])["maintenance"]["fault"] is True
    er.async_get(hass).async_update_entity(fault, device_id=None)
    assert Capabilities(hass).details(item["source"])["maintenance"] == {
        "battery_percent": 19.0,
        "battery_low": True,
        "fault": None,
    }
    assert not calls
