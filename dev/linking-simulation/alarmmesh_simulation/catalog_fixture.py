"""Expanded registry/action test doubles; explicitly not MQTT/ZHA driver tests."""

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

DEVICES = (
    (
        "a",
        "mqtt",
        "HS1SA-E-PLUS",
        "Heiman",
        "select",
        "siren_for_automation_only",
        0,
        [],
        "stop",
        None,
    ),
    (
        "b",
        "mqtt",
        "JY-GZ-01AQ",
        "Aqara",
        "select",
        "buzzer",
        0,
        [],
        "mute",
        "linkage_alarm",
    ),
    ("c", "zha", "SMSZB-120", "frient A/S", "siren", "sounder", 17, [], "off", None),
    ("d", "mqtt", "UNKNOWN-SIMULATION", "Simulation", None, None, 0, [], "off", None),
    (
        "e",
        "mqtt",
        "S1-M",
        "Heiman",
        "select",
        "siren_for_automation_only",
        0,
        [],
        "stop",
        None,
    ),
    ("f", "zha", "S1-TL", "HEIMAN", "siren", "sounder", 17, [], "off", None),
    (
        "g",
        "zha",
        "lumi.sensor_smoke.acn03",
        "LUMI",
        "switch",
        "buzzer_manual_alarm",
        0,
        [],
        "off",
        "linkage_alarm",
    ),
    ("h", "mqtt", "8750001213", "Bosch", "select", "alarm", 0, [], "stop", None),
    (
        "i",
        "mqtt",
        "BSD-2",
        "Bosch",
        "siren",
        "alarm_control",
        5,
        ["smoke", "burglar"],
        "off",
        "broadcast_alarms",
    ),
    (
        "j",
        "mqtt",
        "FAM-300Z",
        "ShinaSystem",
        "switch",
        "force_smoke_alarm",
        0,
        [],
        "off",
        "remote_control_permission",
    ),
    (
        "k",
        "mqtt",
        "HS15A-M",
        "Heiman",
        "siren",
        "sounder",
        21,
        ["burglar"],
        "off",
        None,
    ),
    ("l", "mqtt", "W599001", "Schneider Electric", None, None, 0, [], "off", None),
    ("m", "mqtt", "TS0601_smoke_1", "Tuya", None, None, 0, [], "off", None),
    ("n", "mqtt", "94430", "Frient", "siren", "sounder", 21, ["burglar"], "off", None),
    (
        "o",
        "mqtt",
        "HM-636THV-AC-M",
        "Heiman",
        "select",
        "siren_for_automation_only",
        0,
        [],
        "stop",
        None,
    ),
    ("p", "mqtt", "R7049", "Woox", None, None, 0, [], "off", None),
)


async def async_setup_catalog(hass, entry):
    registry = er.async_get(hass)
    fixtures, calls, outputs = {}, [], {}
    for (
        name,
        provider,
        model,
        vendor,
        domain,
        key,
        features,
        tones,
        idle,
        gate,
    ) in DEVICES:
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
            model_id=model,
            model=model,
            manufacturer=vendor,
            sw_version="SIMULATED-2.2.0",
            name=f"SIMULATED {name.upper()}",
        )

        def register(
            domain, prop, *, provider=provider, name=name, device=device, **kwargs
        ):
            return registry.async_get_or_create(
                domain,
                provider,
                f"sim_{name}_{prop}_zigbee2mqtt"
                if provider == "mqtt"
                else f"sim_{name}-{prop}",
                config_entry=entry,
                device_id=device.id,
                suggested_object_id=f"catalog_{name}_{prop}",
                translation_key=prop if provider == "zha" else None,
                **kwargs,
            ).entity_id

        source = register("binary_sensor", "smoke", original_device_class="smoke")
        target = register(domain, key) if domain else None
        setting = (
            register(
                "binary_sensor" if gate == "remote_control_permission" else "switch",
                gate,
            )
            if gate
            else None
        )
        battery = register("sensor", "battery", original_device_class="battery")
        fault = register("binary_sensor", "fault", original_device_class="problem")
        test = register(
            "binary_sensor", "test" if provider == "mqtt" else "self_test_state"
        )
        if target:
            outputs[target] = idle
        fixtures[name] = {
            "source": source,
            "target": target,
            "setting": setting,
            "battery": battery,
            "fault": fault,
            "test": test,
            "features": features,
            "tones": tones,
            "key": key,
        }

    def enabled(flag):
        return hass.states.is_state(f"input_boolean.catalog_{flag}", "on")

    @callback
    def update(_event=None):
        for name, item in fixtures.items():
            attrs = {
                "device_class": "smoke",
                "friendly_name": (
                    f"SIMULATED {name.upper()} - {DEVICES[ord(name) - 97][2]}"
                )
                + (
                    " - long detector name for the upstairs landing and storage area"
                    if name == "o"
                    else ""
                ),
            }
            hass.states.async_set(
                item["source"],
                "unavailable"
                if enabled(f"{name}_unreachable")
                else "on"
                if enabled(f"{name}_smoke")
                else "off",
                attrs,
            )
            hass.states.async_set(
                item["battery"],
                "72",
                {"device_class": "battery", "unit_of_measurement": "%"},
            )
            hass.states.async_set(
                item["fault"],
                "on" if enabled("fault") else "off",
                {"device_class": "problem"},
            )
            hass.states.async_set(item["test"], "on" if enabled("test") else "off")
            if item["setting"]:
                hass.states.async_set(
                    item["setting"], "on" if enabled(f"{name}_permission") else "off"
                )
            if item["target"]:
                attrs = {
                    "supported_features": item["features"],
                    "available_tones": item["tones"],
                }
                if item["key"] in {"buzzer", "siren_for_automation_only", "alarm"}:
                    attrs["options"] = (
                        ["alarm", "mute"]
                        if item["key"] == "buzzer"
                        else ["stop", "pre_alarm", "fire", "burglar"]
                        if item["key"] == "alarm"
                        else ["stop", "smoke_siren", "co_siren"]
                    )
                hass.states.async_set(
                    item["target"],
                    "unavailable"
                    if enabled(f"{name}_control_unreachable")
                    else outputs[item["target"]],
                    attrs,
                )
        hass.states.async_set(
            "sensor.catalog_requests",
            str(len(calls)),
            {
                "requests": calls[-30:],
                "friendly_name": "SIMULATED action requests, no sound",
            },
        )

    async def command(call):
        target = call.data.get("entity_id")
        name = next(
            (name for name, item in fixtures.items() if item["target"] == target), None
        )
        if name is None:
            raise HomeAssistantError("Only explicit simulation controls accepted")
        calls.append(
            {
                "target": target,
                "service": call.service,
                "data": dict(call.data),
                "failed": enabled(f"{name}_failure"),
            }
        )
        if enabled(f"{name}_failure"):
            update()
            raise HomeAssistantError("Simulated failure, no transport")
        outputs[target] = call.data.get("option", "on")
        update()

    for domain, service in (
        ("select", "select_option"),
        ("switch", "turn_on"),
        ("siren", "turn_on"),
    ):
        hass.services.async_register(domain, service, command)
    helpers = [
        f"input_boolean.catalog_{name}_{flag}"
        for name, *_ in DEVICES
        for flag in (
            "smoke",
            "unreachable",
            "permission",
            "control_unreachable",
            "failure",
        )
    ]
    helpers += ["input_boolean.catalog_fault", "input_boolean.catalog_test"]
    entry.async_on_unload(async_track_state_change_event(hass, helpers, update))
    hass.data["alarmmesh_simulation"] = {"fixtures": fixtures, "calls": calls}
    update()
    return True
