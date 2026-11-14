"""Mock HA provider metadata/actions in a disposable environment; no transports.

MQTT/ZHA registry labels are deliberate test doubles, not running integrations.
Never install this fixture in a real HA instance. No account/storage edits.
"""

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

DOMAIN = "alarmmesh_simulation"
DEVICES = (
    ("a", "mqtt", "HS1SA-E-PLUS", "Heiman"),
    ("b", "mqtt", "JY-GZ-01AQ", "Aqara"),
    ("c", "zha", "SMSZB-120", "frient A/S"),
    ("d", "mqtt", "UNKNOWN-SIMULATION", "Simulation"),
)


async def async_setup(hass, _config):
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={"catalog": bool((_config.get(DOMAIN) or {}).get("catalog"))},
        )
    )
    return True


async def async_setup_entry(hass, entry):
    if entry.data.get("catalog"):
        from .catalog_fixture import async_setup_catalog

        return await async_setup_catalog(hass, entry)
    registry = er.async_get(hass)
    fixtures = {}
    outputs = {}
    calls = []

    def register(name, provider, device, domain, property_name, **extra):
        uid = (
            f"sim_{name}_{property_name}_zigbee2mqtt"
            if provider == "mqtt"
            else f"sim_{name}-{property_name}"
        )
        return registry.async_get_or_create(
            domain,
            provider,
            uid,
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=f"link_sim_{name}_{property_name}",
            original_name=f"SIMULATED {name.upper()} {property_name}",
            **extra,
        ).entity_id

    for name, provider, model, vendor in DEVICES:
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={
                (
                    provider,
                    f"zigbee2mqtt_sim_{name}"
                    if provider == "mqtt"
                    else f"simulation_{name}",
                )
            },
            model=model,
            model_id=model,
            manufacturer=vendor,
            name=f"SIMULATED {name.upper()} - no device",
        )
        source = register(
            name,
            provider,
            device,
            "binary_sensor",
            "smoke",
            original_device_class="smoke",
        )
        test = register(name, provider, device, "binary_sensor", "test")
        prop = (
            "buzzer"
            if name == "b"
            else "siren_for_automation_only"
            if name == "a"
            else "sounder"
        )
        target = (
            register(name, provider, device, "siren" if name == "c" else "select", prop)
            if name != "d"
            else None
        )
        setting = (
            register(name, provider, device, "switch", "linkage_alarm")
            if name == "b"
            else None
        )
        fixtures[name] = {
            "source": source,
            "test": test,
            "target": target,
            "setting": setting,
        }
        if target:
            outputs[target] = (
                "mute" if name == "b" else "off" if name == "c" else "stop"
            )

    def is_on(name):
        return hass.states.is_state(f"input_boolean.link_{name}", "on")

    @callback
    def update(_event=None):
        for name, item in fixtures.items():
            state = (
                "unavailable"
                if is_on(f"{name}_unreachable")
                else "on"
                if is_on(f"{name}_smoke")
                else "off"
            )
            hass.states.async_set(
                item["source"],
                state,
                {
                    "device_class": "smoke",
                    "friendly_name": f"SIMULATED {name.upper()} smoke",
                },
            )
            hass.states.async_set(
                item["test"], "on" if is_on(f"{name}_test") else "off"
            )
            if item["setting"]:
                hass.states.async_set(
                    item["setting"],
                    "on" if is_on("b_linkage") else "off",
                    {"friendly_name": "SIMULATED B linkage setting"},
                )
            if target := item["target"]:
                attrs = (
                    {"supported_features": 19}
                    if name == "c"
                    else {
                        "options": ["alarm", "mute"]
                        if name == "b"
                        else ["stop", "smoke_siren", "co_siren"]
                    }
                )
                attrs["friendly_name"] = f"SIMULATED {name.upper()} sounder"
                hass.states.async_set(
                    target,
                    "unavailable"
                    if is_on(f"{name}_control_unreachable")
                    else outputs[target],
                    attrs,
                )
        hass.states.async_set(
            "sensor.link_sim_requests",
            str(len(calls)),
            {
                "friendly_name": "SIMULATED requests (not physical sound)",
                "requests": calls[-30:],
            },
        )

    async def execute(call):
        target = call.data.get("entity_id")
        name = next(
            (key for key, item in fixtures.items() if item["target"] == target), None
        )
        if name is None:
            raise HomeAssistantError("Only explicit simulation targets are accepted")
        record = {
            "target": target,
            "action": call.service,
            "option": call.data.get("option"),
            "duration": call.data.get("duration"),
        }
        calls.append(record)
        if is_on(f"{name}_failure"):
            record["result"] = "simulated failure"
            update()
            raise HomeAssistantError("SIMULATED target failure; no device command")
        outputs[target] = call.data.get("option", "on")
        record["result"] = "simulated acceptance, not audible confirmation"
        update()

    # Restricted test doubles for the standard actions, not a broker/driver.
    hass.services.async_register("select", "select_option", execute)
    hass.services.async_register("siren", "turn_on", execute)
    helpers = [
        f"input_boolean.link_{name}_{flag}"
        for name, *_ in DEVICES
        for flag in ("smoke", "unreachable", "test", "control_unreachable", "failure")
    ]
    helpers.append("input_boolean.link_b_linkage")
    entry.async_on_unload(async_track_state_change_event(hass, helpers, update))
    update()
    hass.data[DOMAIN] = {"fixtures": fixtures, "calls": calls}
    return True
