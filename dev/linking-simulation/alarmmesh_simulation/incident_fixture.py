"""No transport/phones/sound: explicit mock self-check and notification endpoints."""

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .catalog_fixture import async_setup_catalog


async def async_setup_incidents(hass, entry):
    await async_setup_catalog(hass, entry)
    fixtures = hass.data["alarmmesh_simulation"]["fixtures"]
    calls = []
    registry = er.async_get(hass)
    tests = {}
    for name, prop, provider in (
        ("a", "trigger_selftest", "mqtt"),
        ("b", "selftest", "mqtt"),
        ("g", "self_test", "zha"),
    ):
        source = registry.async_get(fixtures[name]["source"])
        button = registry.async_get_or_create(
            "button",
            provider,
            f"sim_{name}_{prop}_zigbee2mqtt"
            if provider == "mqtt"
            else f"sim_{name}-{prop}",
            config_entry=entry,
            device_id=source.device_id,
            translation_key=prop if provider == "zha" else None,
            suggested_object_id=f"incident_{name}_{prop}",
        )
        hass.states.async_set(button.entity_id, "unknown")
        tests[button.entity_id] = name
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("mqtt", "zigbee2mqtt_sim_q")},
        model="HALO",
        model_id="HALO",
        manufacturer="Halo Smart Labs",
        name="SIMULATED Q - built-in self-test result",
    )

    def register(domain, key):
        return registry.async_get_or_create(
            domain,
            "mqtt",
            f"sim_q_{key}_zigbee2mqtt",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=f"incident_q_{key}",
            original_device_class="smoke" if key == "smoke" else None,
        ).entity_id

    source = register("binary_sensor", "smoke")
    cycle = register("select", "test_cycle")
    flag = register("binary_sensor", "test_in_progress")
    result = register("sensor", "halo_test_result")
    hass.states.async_set(
        source,
        "off",
        {
            "device_class": "smoke",
            "friendly_name": "SIMULATED Q - HALO device-result contract",
        },
    )
    hass.states.async_set(cycle, "unknown", {"options": ["start", "cancel"]})

    @callback
    def update(*_):
        state = hass.states.get("input_select.incident_test_result")
        value = state.state if state else "idle"
        hass.states.async_set(flag, "on" if value == "running" else "off")
        hass.states.async_set(result, value)
        hass.states.async_set(
            "sensor.incident_simulated_requests",
            str(len(calls)),
            {
                "friendly_name": "SIMULATED requests; no external delivery",
                "requests": calls[-50:],
            },
        )

    async def notify(call):
        calls.append({"kind": "notification", "target": call.service})
        update()
        if call.service.endswith("phone_b") and hass.states.is_state(
            "input_boolean.incident_notify_failure", "on"
        ):
            raise HomeAssistantError("Deliberate simulated notification failure")

    async def press(call):
        if call.data.get("entity_id") not in tests:
            raise HomeAssistantError("Only explicit simulated test buttons")
        calls.append({"kind": "selftest", "target": call.data["entity_id"]})
        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.catalog_test"},
            blocking=True,
        )
        update()

    # Existing select handler remains in use for sounder mocks.
    previous_select = hass.data["alarmmesh_simulation"]["command"]

    async def select(call):
        if call.data.get("entity_id") == cycle:
            if call.data.get("option") != "start":
                raise HomeAssistantError("No simulated cancel/mute route")
            calls.append({"kind": "selftest", "target": cycle})
            await hass.services.async_call(
                "input_select",
                "select_option",
                {"entity_id": "input_select.incident_test_result", "option": "running"},
                blocking=True,
            )
            update()
        else:
            await previous_select(call)

    @callback
    def script_event(event):
        calls.append(
            {"kind": "script", "target": str(event.data.get("name", "simulation"))}
        )
        update()

    for phone in ("phone_a", "phone_b"):
        hass.services.async_register("notify", "mobile_app_simulated_" + phone, notify)
    hass.services.async_register("button", "press", press)
    hass.services.async_register("select", "select_option", select)
    entry.async_on_unload(
        hass.bus.async_listen("alarmmesh_simulated_script", script_event)
    )
    entry.async_on_unload(
        async_track_state_change_event(
            hass, ["input_select.incident_test_result"], update
        )
    )
    update()
    return True
