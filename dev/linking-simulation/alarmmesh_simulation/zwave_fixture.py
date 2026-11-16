"""Registry-only virtual Z-Wave JS device. No controller or Z-Wave connection."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event


async def async_setup_zwave_fixture(hass, entry):
    owner = next(
        (
            e
            for e in hass.config_entries.async_entries("zwave_js")
            if e.unique_id == "alarmmesh_simulation_registry_only"
        ),
        None,
    )
    if owner is None:
        owner = ConfigEntry(
            domain="zwave_js",
            title="SIMULATED Z-Wave JS (no controller)",
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
                return False
            return await original(manager, entry_id, *args, **kwargs)

        with patch.object(manager_type, "async_setup", inert_setup):
            await hass.config_entries.async_add(owner)
    assert owner.source == SOURCE_IGNORE and owner.data == {}
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=owner.entry_id,
        identifiers={("zwave_js", "SIMULATED_NO_RADIO_NODE")},
        manufacturer="SIMULATION",
        model="Virtual smoke/CO detector",
        name="SIMULATED Z-Wave JS detector",
    )
    rows = []
    for domain, key, cls in (
        ("binary_sensor", "smoke", "smoke"),
        ("binary_sensor", "co", "carbon_monoxide"),
        ("binary_sensor", "fault", "problem"),
        ("binary_sensor", "battery_low", "battery"),
        ("sensor", "battery", "battery"),
    ):
        entity = er.async_get(hass).async_get_or_create(
            domain,
            "zwave_js",
            f"SIMULATED-ZWAVE-{key}",
            config_entry=owner,
            device_id=device.id,
            original_device_class=cls,
            suggested_object_id=f"simulated_zwave_{key}",
            original_name=f"SIMULATED Z-Wave {key}",
        )
        rows.append((entity.entity_id, key, cls))

    @callback
    def update(_event=None):
        unavailable = hass.states.is_state("input_boolean.zwave_unavailable", "on")
        for entity_id, key, cls in rows:
            active = hass.states.is_state(f"input_boolean.zwave_{key}", "on")
            value = (
                "unavailable"
                if unavailable
                else (
                    "12"
                    if hass.states.is_state("input_boolean.zwave_battery_low", "on")
                    else "76"
                )
                if key == "battery"
                else "on"
                if active
                else "off"
            )
            if unavailable:
                value = "unavailable"
            attrs = {"device_class": cls, "friendly_name": f"SIMULATED Z-Wave {key}"}
            if key == "battery":
                attrs["unit_of_measurement"] = "%"
            hass.states.async_set(entity_id, value, attrs)

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            [
                f"input_boolean.zwave_{k}"
                for k in ("smoke", "co", "fault", "battery_low", "unavailable")
            ],
            update,
        )
    )
    update()
