"""Ignored registry-only Matter owner and explicit virtual attributes. No server."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event


async def async_setup_matter_fixture(hass, entry):
    owner = next(
        (
            e
            for e in hass.config_entries.async_entries("matter")
            if e.unique_id == "alarmmesh_simulation_registry_only"
        ),
        None,
    )
    if owner is not None and owner.source != SOURCE_IGNORE:
        # Remove only the earlier registry-only fixture, never any real owner.
        assert (
            owner.data == {} and owner.unique_id == "alarmmesh_simulation_registry_only"
        )
        await hass.config_entries.async_remove(owner.entry_id)
        owner = None
    if owner is None:
        owner = ConfigEntry(
            domain="matter",
            title="SIMULATED registry-only Matter (ignored, no server)",
            data={},
            options={},
            version=1,
            minor_version=1,
            source=SOURCE_IGNORE,
            unique_id="alarmmesh_simulation_registry_only",
            discovery_keys={},
            subentries_data=[],
        )
        manager_type = type(hass.config_entries)
        original = manager_type.async_setup

        async def inert_setup(manager, entry_id, *args, **kwargs):
            if entry_id == owner.entry_id:
                return False  # I/O replacement for this ignored fixture only.
            return await original(manager, entry_id, *args, **kwargs)

        with patch.object(manager_type, "async_setup", inert_setup):
            await hass.config_entries.async_add(owner)
    assert (
        owner.source == SOURCE_IGNORE and owner.disabled_by is None and owner.data == {}
    )
    registry = er.async_get(hass)
    fixtures = {}
    for letter, model, vendor in (
        ("a", "HS1SA-M", "HEIMAN"),
        ("b", "MSC-1", "SENSEREO LIMITED"),
    ):
        root = f"SIMULATION-MATTER-{letter}-MatterNodeDevice"
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=owner.entry_id,
            identifiers={("matter", "deviceid_" + root)},
            manufacturer=vendor,
            model=model,
            model_id="2" if letter == "b" else None,
            name=f"SIMULATED Matter {letter.upper()} - {model}",
        )
        rows = {}
        for domain, key, cluster, attribute, cls, translation in (
            ("binary_sensor", "SmokeCoAlarmSmokeStateSensor", 92, 1, "smoke", None),
            (
                "binary_sensor",
                "SmokeCoAlarmCOStateSensor",
                92,
                2,
                "carbon_monoxide",
                None,
            ),
            (
                "binary_sensor",
                "SmokeCoAlarmInterconnectSmokeAlarmSensor",
                92,
                8,
                "smoke",
                "interconnected_smoke_alarm",
            ),
            (
                "binary_sensor",
                "SmokeCoAlarmTestInProgressSensor",
                92,
                5,
                "running",
                "test_in_progress",
            ),
            (
                "binary_sensor",
                "SmokeCoAlarmHardwareFaultAlertSensor",
                92,
                6,
                "problem",
                "hardware_fault",
            ),
            (
                "binary_sensor",
                "SmokeCoAlarmEndfOfServiceSensor",
                92,
                7,
                "problem",
                "end_of_service",
            ),
            ("sensor", "PowerSource", 47, 12, "battery", None),
            (
                "button",
                "SmokeCoAlarmSelfTestRequest",
                92,
                65529,
                None,
                "self_test_request",
            ),
        ):
            entity = registry.async_get_or_create(
                domain,
                "matter",
                f"{root}-1-{key}-{cluster}-{attribute}",
                config_entry=owner,
                device_id=device.id,
                suggested_object_id=(
                    f"simulated_matter_{letter}_" + (translation or key.lower())
                ),
                original_device_class=cls,
                translation_key=translation,
                original_name=f"SIMULATED Matter {letter.upper()} {translation or key}",
            )
            rows[key] = (entity.entity_id, cls)
        fixtures[letter] = rows

    @callback
    def update(*_args):
        for letter, rows in fixtures.items():
            absent = hass.states.is_state(
                f"input_boolean.matter_{letter}_unavailable", "on"
            )
            for key, (entity_id, cls) in rows.items():
                helper = {
                    "SmokeCoAlarmSmokeStateSensor": "smoke",
                    "SmokeCoAlarmCOStateSensor": "co",
                    "SmokeCoAlarmInterconnectSmokeAlarmSensor": "interconnect",
                    "SmokeCoAlarmTestInProgressSensor": "test",
                    "SmokeCoAlarmHardwareFaultAlertSensor": "fault",
                    "SmokeCoAlarmEndfOfServiceSensor": "expired",
                }.get(key)
                state = (
                    "unavailable"
                    if absent
                    else (
                        "on"
                        if hass.states.is_state(
                            f"input_boolean.matter_{letter}_{helper}", "on"
                        )
                        else "off"
                    )
                    if helper
                    else "12"
                    if key == "PowerSource"
                    and hass.states.is_state(
                        f"input_boolean.matter_{letter}_battery_low", "on"
                    )
                    else "78"
                    if key == "PowerSource"
                    else "unknown"
                )
                attrs = {
                    "friendly_name": f"SIMULATED Matter {letter.upper()} · {key}",
                    **({"device_class": cls} if cls else {}),
                }
                if key == "PowerSource":
                    attrs["unit_of_measurement"] = "%"
                hass.states.async_set(entity_id, state, attrs)

    helpers = [
        f"input_boolean.matter_{letter}_{kind}"
        for letter in "ab"
        for kind in (
            "smoke",
            "co",
            "interconnect",
            "test",
            "fault",
            "expired",
            "unavailable",
            "battery_low",
        )
    ]
    entry.async_on_unload(async_track_state_change_event(hass, helpers, update))
    update()
    return {
        rows["SmokeCoAlarmSelfTestRequest"][0]: f"input_boolean.matter_{letter}_test"
        for letter, rows in fixtures.items()
    }
