"""No transport/phones/sound: explicit mock self-check and notification endpoints."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .catalog_fixture import async_setup_catalog


async def async_setup_incidents(hass, entry):
    await async_setup_catalog(hass, entry)
    fixtures = hass.data["alarmmesh_simulation"]["fixtures"]
    # Metadata-only registrations. No Companion provider or outbound transport.
    for letter, platform in (("a", "iOS"), ("b", "Android")):
        uid = f"alarmmesh_simulated_phone_{letter}"
        owner = next(
            (
                e
                for e in hass.config_entries.async_entries("mobile_app")
                if e.unique_id == uid
            ),
            None,
        )
        data = {
            "device_name": f"simulated_phone_{letter}",
            "device_id": uid,
            "os_name": platform,
        }
        if owner is None:
            owner = ConfigEntry(
                domain="mobile_app",
                title=f"SIMULATED phone {letter}",
                data=data,
                options={},
                version=1,
                minor_version=1,
                source=SOURCE_IGNORE,
                unique_id=uid,
                discovery_keys={},
                subentries_data=[],
            )
            manager_type = type(hass.config_entries)
            original = manager_type.async_setup

            async def inert_setup(
                manager, entry_id, *args, fixture=owner, delegate=original, **kwargs
            ):
                if entry_id == fixture.entry_id:
                    return False
                return await delegate(manager, entry_id, *args, **kwargs)

            with patch.object(manager_type, "async_setup", inert_setup):
                await hass.config_entries.async_add(owner)
        assert owner.source == SOURCE_IGNORE and owner.data == data
    calls = []
    notification_mode = "normal"
    registry = er.async_get(hass)
    tests = {}
    from .matter_fixture import async_setup_matter_fixture

    matter_tests = await async_setup_matter_fixture(hass, entry)
    from .zwave_fixture import async_setup_zwave_fixture

    await async_setup_zwave_fixture(hass, entry)

    async def audit_started(_event):
        """Local mock-only evidence, without account data or raw HA snapshots."""
        alarmmesh = hass.config_entries.async_entries("alarmmesh")
        panel = alarmmesh[0].runtime_data.panel if alarmmesh else None
        state = panel.snapshot() if panel else None
        helpers = hass.states.async_all("input_boolean")
        owner = next(
            e
            for e in hass.config_entries.async_entries("matter")
            if e.unique_id == "alarmmesh_simulation_registry_only"
        )
        evidence = {
            "scope": "mock simulator only, no physical validation",
            "helpers": len(helpers),
            "helpers_all_off": bool(helpers) and all(s.state == "off" for s in helpers),
            "test_result_idle": hass.states.is_state(
                "input_select.incident_test_result", "idle"
            ),
            "matter_owner_ignored": owner.source == "ignore" and owner.data == {},
            "matter_controller_loaded": "matter" in hass.config.components,
            "selected_sources": len(state["sources"]) if state else 0,
            "selected_smoke_off": bool(state)
            and all(s["ha_state"] == "off" for s in state["sources"]),
            "linking_off": not state
            or not any(g["linking"]["enabled"] for g in state["groups"]),
            "scripts_off": not state
            or not any(g.get("actions", {}).get("enabled") for g in state["groups"]),
            "notifications_off": not state
            or not state["automation"]["settings"]["enabled"],
            "maintenance_off": not state
            or not state["maintenance"]["settings"]["enabled"],
            "reminders_off": not state
            or not any(r["enabled"] for r in state["reminders"]["items"]),
            "no_active_selftest": panel is None or panel.selftests._request is None,
        }
        await hass.async_add_executor_job(
            Path(hass.config.path("alarmmesh-simulation-audit.json")).write_text,
            json.dumps(evidence, indent=2),
            "utf-8",
        )

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, audit_started)
    )
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
        data = call.data.get("data", {})
        calls.append(
            {
                "kind": "notification",
                "target": call.service,
                "alarm_fields": {
                    k: data[k]
                    for k in ("push", "channel", "priority", "ttl")
                    if k in data
                },
            }
        )
        update()
        if call.service.endswith("phone_b") and notification_mode == "timeout":
            await asyncio.sleep(15)
        if call.service.endswith("phone_b") and hass.states.is_state(
            "input_boolean.incident_notify_failure", "on"
        ):
            raise HomeAssistantError("Deliberate simulated notification failure")

    async def press(call):
        if call.data.get("entity_id") in matter_tests:
            calls.append({"kind": "selftest", "target": call.data["entity_id"]})
            await hass.services.async_call(
                "input_boolean",
                "turn_on",
                {"entity_id": matter_tests[call.data["entity_id"]]},
                blocking=True,
            )
            update()
            return
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

    async def set_notification_mode(call):
        """Test-only fault injection; never connects to a phone or external provider."""
        nonlocal notification_mode
        notification_mode = call.data["mode"]
        target = "mobile_app_simulated_phone_b"
        if notification_mode == "missing":
            hass.services.async_remove("notify", target)
        else:
            hass.services.async_register("notify", target, notify)

    hass.services.async_register(
        "alarmmesh_simulation",
        "notification_mode",
        set_notification_mode,
        schema=vol.Schema(
            {vol.Required("mode"): vol.In(["normal", "timeout", "missing"])}
        ),
    )
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
