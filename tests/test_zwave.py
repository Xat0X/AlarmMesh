"""Cached real HA registries; no Z-Wave server, controller or device I/O."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_activity_reminders import settle
from test_linking_runtime import devices as devices
from test_linking_runtime import setup

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.capabilities import Capabilities
from custom_components.alarmmesh.config_flow import _validate_sources
from custom_components.alarmmesh.diagnostics import support_report


@pytest.fixture
def zwave_device(hass):
    owner = MockConfigEntry(domain="zwave_js", data={})
    owner.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=owner.entry_id,
        identifiers={("zwave_js", "PRIVATE_HOME_NODE")},
        model="Unknown Z-Wave smoke detector",
        model_id="PRIVATE_PRODUCT_ID",
        manufacturer="Virtual manufacturer",
    )

    def add(domain, cls, state="off", *, target=device, config=owner, attrs=None):
        registry = er.async_get(hass)
        entity = registry.async_get_or_create(
            domain,
            "zwave_js",
            f"PRIVATE_NETWORK_{len(registry.entities)}",
            config_entry=config,
            device_id=target.id,
            original_device_class=cls,
            suggested_object_id=f"simulated_zwave_{len(registry.entities)}",
            translation_key="self_test" if domain == "button" else None,
        )
        hass.states.async_set(entity.entity_id, state, attrs or {"device_class": cls})
        return entity.entity_id

    return add, device, owner


async def test_unknown_model_smoke_lifecycle_and_no_control(hass, zwave_device):
    add, _, _ = zwave_device
    source = add("binary_sensor", "smoke")
    add("button", None)  # A tempting translation key must never create a test.
    add("siren", None)
    assert _validate_sources(hass, [source]) is None
    entry = await setup(hass, [source])
    panel = entry.runtime_data.panel
    cap = panel.linking.capabilities.describe(source)
    assert cap["origin"] == "zwave_js" and cap["status"] == "detection_only"
    assert cap["controls"] == [] and cap["reason"] == "zwave_observation_only"
    assert not cap["zwave"]["self_test"] and panel.selftests.resolve(source) is None
    assert "zwave_js" not in hass.config.components
    for state, expected in [
        ("on", "SMOKE_REPORTED"),
        ("unavailable", "INDETERMINATE"),
        ("off", "NO_SMOKE_REPORTED"),
    ]:
        hass.states.async_set(source, state, {"device_class": "smoke"})
        await settle(hass, entry)
        assert entry.runtime_data.result.smoke_status.name == expected
    snapshot = panel.snapshot()
    assert snapshot["sources"][0]["model"] == "Unknown Z-Wave smoke detector"
    report = support_report(snapshot, "0.1.0", "2026.11.1")
    assert report["sources"][0]["provider"] == "zwave_js"
    assert "PRIVATE" not in str(report)


@pytest.mark.parametrize("original", ["carbon_monoxide", "heat", "problem", None])
async def test_overridden_non_smoke_rejected_even_in_old_saved_selection(
    hass, zwave_device, original
):
    add, _, _ = zwave_device
    source = add("binary_sensor", original, "on")
    er.async_get(hass).async_update_entity(source, device_class="smoke")
    hass.states.async_set(source, "on", {"device_class": "smoke"})
    assert _validate_sources(hass, [source]) == "wrong_device_class"
    assert Capabilities(hass).source_identity_changed(source)
    entry = await setup(hass, [source])
    assert entry.runtime_data.source_statuses[source].name == "UNKNOWN"
    assert entry.runtime_data.result.smoke_status.name == "INDETERMINATE"


async def test_maintenance_exact_device_owner_and_original_classes(hass, zwave_device):
    add, device, owner = zwave_device
    source = add("binary_sensor", "smoke")
    battery = add(
        "sensor",
        "battery",
        "73",
        attrs={"device_class": "battery", "unit_of_measurement": "%"},
    )
    low = add("binary_sensor", "battery", "on")
    fault = add("binary_sensor", "problem", "on")
    foreign = MockConfigEntry(domain="zwave_js", data={})
    foreign.add_to_hass(hass)
    add("sensor", "battery", "1", config=foreign)
    other = dr.async_get(hass).async_get_or_create(
        config_entry_id=owner.entry_id, identifiers={("zwave_js", "OTHER_NODE")}
    )
    add("sensor", "battery", "2", target=other)
    fake = add("binary_sensor", "carbon_monoxide", "on")
    er.async_get(hass).async_update_entity(fake, device_class="problem")
    cap = Capabilities(hass)
    details = cap.details(source)
    assert details["maintenance"] == {
        "battery_percent": 73,
        "battery_low": True,
        "fault": True,
    }
    assert {v["entity_id"] for v in details["values"]} == {battery, low, fault}
    hass.states.async_set(battery, "73", {"unit_of_measurement": "V"})
    hass.states.async_set(low, "unknown")
    hass.states.async_set(fault, "unavailable")
    assert cap.details(source)["maintenance"] == {
        "battery_percent": None,
        "battery_low": None,
        "fault": None,
    }


async def test_mixed_provider_group_preserves_smoke_priority_without_actions(
    hass, zwave_device, devices
):
    add, _, _ = zwave_device
    other, calls, _ = devices
    mqtt = other("mixed_zwave_mqtt")
    source = add("binary_sensor", "smoke")
    entry = await setup(hass, [source, mqtt["source"]])
    panel = entry.runtime_data.panel
    store = panel.groups
    await store.async_mutate(
        {
            "operation": "create",
            "name": "Mixed",
            "revision": store.revision,
            "members": [source, mqtt["source"]],
        },
        (source, mqtt["source"]),
    )
    hass.states.async_set(source, "on", {"device_class": "smoke"})
    hass.states.async_set(mqtt["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    snapshot = panel.snapshot()
    assert snapshot["groups"][0]["result"]["smoke"] == "SMOKE_REPORTED"
    assert snapshot["groups"][0]["linking"]["enabled"] is False and calls == []
