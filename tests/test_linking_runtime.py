"""Real HA registries/storage/auth with only mocked HA action handlers."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.capabilities import Capabilities
from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS
from custom_components.alarmmesh.groups import GroupError, GroupStore


@pytest.fixture
def devices(hass):
    """Virtual metadata, deliberately unrelated visible entity IDs; no drivers."""
    entities = er.async_get(hass)
    calls, failures = [], set()

    async def command(call):
        data = dict(call.data)
        calls.append((call.domain, call.service, data))
        if data["entity_id"] in failures:
            raise HomeAssistantError("simulated target failure")
        hass.states.async_set(
            data["entity_id"],
            data.get("option", "on"),
            dict(hass.states.get(data["entity_id"]).attributes),
            context=call.context,
        )

    hass.services.async_register("select", "select_option", command)
    hass.services.async_register("siren", "turn_on", command)

    def add(
        name,
        model="HS1SA-E-PLUS",
        origin="mqtt",
        vendor="Heiman",
        options=None,
        features=19,
    ):
        entry = MockConfigEntry(domain=origin, data={})
        entry.add_to_hass(hass)
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={
                (
                    origin,
                    f"zigbee2mqtt_sim_{name}"
                    if origin == "mqtt"
                    else f"simulation_{name}",
                )
            },
            model_id=model,
            model="Simulated smoke model",
            manufacturer=vendor,
        )
        uid = f"sim_{name}"

        def entity(domain, property_name, state, attrs):
            unique = (
                f"{uid}_{property_name}_zigbee2mqtt"
                if origin == "mqtt"
                else f"{uid}-{property_name}"
            )
            registered = entities.async_get_or_create(
                domain,
                origin,
                unique,
                config_entry=entry,
                device_id=device.id,
                suggested_object_id=f"sim_{name}_{property_name}",
                original_device_class="smoke" if property_name == "smoke" else None,
            )
            hass.states.async_set(registered.entity_id, state, attrs)
            return registered.entity_id

        source = entity("binary_sensor", "smoke", "off", {"device_class": "smoke"})
        if model == "SMSZB-120":
            target = entity(
                "siren",
                "sounder",
                "off",
                {
                    "supported_features": 31
                    if origin == "mqtt" and features == 19
                    else features,
                    "available_tones": ["burglar"] if origin == "mqtt" else [],
                },
            )
        else:
            prop = (
                "buzzer"
                if model in {"JY-GZ-01AQ", "lumi.sensor_smoke.acn03"}
                else "siren_for_automation_only"
            )
            target = entity(
                "select",
                prop,
                "mute" if prop == "buzzer" else "stop",
                {
                    "options": options
                    if options is not None
                    else ["alarm", "mute"]
                    if prop == "buzzer"
                    else ["smoke_siren", "stop", "co_siren"]
                },
            )
        setting = entity("switch", "linkage_alarm", "on", {})
        test = entity("binary_sensor", "test", "off", {})
        return {
            "source": source,
            "target": target,
            "feedback": entity("binary_sensor", "buzzer_manual_alarm", "off", {})
            if model == "JY-GZ-01AQ" and origin == "mqtt"
            else None,
            "device": device.id,
            "setting": setting,
            "test": test,
        }

    return add, calls, failures


async def setup(hass, members):
    entry = MockConfigEntry(
        domain="alarmmesh", data={}, options={CONF_SOURCE_ENTITY_IDS: members}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await flush(hass, entry)
    return entry


async def flush(hass, entry):
    for _ in range(8):
        await hass.async_block_till_done()
        engine = entry.runtime_data.panel.linking
        if engine._task is None:
            return
        await engine._task
    pytest.fail("Linking did not settle")


def binding(hass, device):
    control = Capabilities(hass).describe(device["source"])["controls"][0]
    return {key: control[key] for key in ("source", "target", "profile", "identity")}


async def configure(hass, entry, members, targets, *, group_id=None, enabled=True):
    panel = entry.runtime_data.panel
    await panel.groups.async_mutate(
        {
            "operation": "update" if group_id else "create",
            **({"group_id": group_id} if group_id else {}),
            "revision": panel.groups.revision,
            "name": "Simulation only",
            "members": members,
            "linking": {
                "enabled": enabled,
                "bindings": [binding(hass, d) for d in targets],
            },
            "confirmed": True,
        },
        tuple(entry.options[CONF_SOURCE_ENTITY_IDS]),
    )
    panel.linking.changed()
    await flush(hass, entry)
    return panel.groups.groups[-1]["id"]


@pytest.mark.parametrize("hall_state", ["off", "on", "unavailable"])
async def test_group_stop_during_origin_smoke(
    hass, devices, hass_ws_client, hall_state
):
    add, calls, _ = devices
    landing, hall, test = (add(name) for name in ("landing", "hall", "test"))
    attic = add("attic", "JY-GZ-01AQ", vendor="Aqara")
    members = [d["source"] for d in (landing, hall, test, attic)]
    entry = await setup(hass, members)
    group = await configure(hass, entry, members, [hall, test, attic])
    client = await hass_ws_client(hass)
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    await client.send_json({"id": 1, "type": "alarmmesh/current"})
    snapshot = (await client.receive_json())["result"]
    choices = snapshot["groups"][0]["group_stop_choices"]
    assert {row["source"] for row in choices} == {hall["source"], test["source"]}
    assert [call[2]["option"] for call in calls].count("smoke_siren") == 2
    assert [call[2]["option"] for call in calls].count("alarm") == 1
    # The linked detector can report smoke or go offline while the screen is open.
    hass.states.async_set(hall["source"], hall_state, {"device_class": "smoke"})
    payload = {
        "type": "alarmmesh/group_stop",
        "group_id": group,
        "revision": snapshot["revision"],
        "start_ids": [row["start_id"] for row in choices],
    }
    await client.send_json({"id": 2, **payload})
    result = (await client.receive_json())["result"]
    expected = (
        {test["target"], hall["target"]} if hall_state == "off" else {test["target"]}
    )
    assert result == {"accepted": len(expected), "requested": 2}
    await flush(hass, entry)
    assert {(data["entity_id"], data["option"]) for _, _, data in calls[3:]} == {
        (target, "stop") for target in expected
    }
    assert hass.states.is_state(landing["source"], "on")
    assert hass.states.is_state(hall["source"], hall_state)
    if hall_state != "off":
        assert hass.states.is_state(hall["target"], "smoke_siren")
    assert hass.states.is_state(attic["target"], "alarm")
    panel = entry.runtime_data.panel
    assert panel.snapshot()["result"]["smoke"] == "SMOKE_REPORTED"
    events = panel.activity.snapshot()["events"]
    assert {
        e["target"] for e in events if e["result"] == "group_stop_requested"
    } == expected
    # Replay of a lost reply cannot issue another stop or restart a stopped target.
    await client.send_json({"id": 3, **payload})
    assert (await client.receive_json())["result"]["accepted"] == 0
    await flush(hass, entry)
    assert len(calls) == 3 + len(expected)
    for source in (landing["source"], hall["source"]):
        hass.states.async_set(source, "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    before = len(calls)
    await client.send_json({"id": 4, **payload})
    assert (await client.receive_json())["result"]["accepted"] == 0
    assert len(calls) == before and hass.states.is_state(test["target"], "smoke_siren")


@pytest.mark.parametrize(
    "case",
    [
        "landing_smoke",
        "landing_clear",
        "clear_before_report",
        "hall_smoke",
        "foreign",
        "intervening",
    ],
)
async def test_group_button_after_late_start_feedback(
    hass, devices, hass_ws_client, case
):
    add, calls, _ = devices
    landing, hall = add("landing"), add("hall")
    attic = add("attic", "JY-GZ-01AQ", vendor="Aqara")
    members = [d["source"] for d in (landing, hall, attic)]
    entry = await setup(hass, members)
    panel = entry.runtime_data.panel
    group = await configure(hass, entry, members, [hall, attic])
    contexts = {}

    async def device_action(call):
        target, option = call.data["entity_id"], call.data["option"]
        calls.append((target, option))
        if option == "smoke_siren":
            contexts[target] = call.context
        else:
            hass.states.async_set(
                target, option, hass.states.get(target).attributes, context=call.context
            )

    hass.services.async_register("select", "select_option", device_action)
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    target = hall["target"]
    if case == "landing_smoke":
        await asyncio.sleep(2.35)
    else:
        panel.linking._expire_pending(target)
    assert panel.linking.records[target]["stop_reason"] == "feedback_window_expired"
    if case == "clear_before_report":
        hass.states.async_set(landing["source"], "off", {"device_class": "smoke"})
        await flush(hass, entry)
    if case == "intervening":
        hass.states.async_set(target, "co_siren", hass.states.get(target).attributes)
        await flush(hass, entry)
    hass.states.async_set(
        target,
        "smoke_siren",
        hass.states.get(target).attributes,
        context=None if case == "foreign" else contexts[target],
    )
    await flush(hass, entry)
    if case == "landing_clear":
        hass.states.async_set(landing["source"], "off", {"device_class": "smoke"})
        await flush(hass, entry)
    choices = panel.snapshot()["groups"][0]["group_stop_choices"]
    assert sorted(calls) == sorted(
        [(attic["target"], "alarm"), (target, "smoke_siren")]
    )
    if case in {"foreign", "intervening"}:
        assert not choices
        return
    assert [row["source"] for row in choices] == [hall["source"]]
    assert target not in panel.linking.owned
    if case == "hall_smoke":
        hass.states.async_set(hall["source"], "on", {"device_class": "smoke"})
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "alarmmesh/group_stop",
            "group_id": group,
            "revision": panel.groups.revision,
            "start_ids": [choices[0]["start_id"]],
        }
    )
    assert (await client.receive_json())["result"]["accepted"] == int(
        case != "hall_smoke"
    )
    await flush(hass, entry)
    if case == "hall_smoke":
        assert hass.states.is_state(hall["source"], "on")
        assert hass.states.is_state(target, "smoke_siren")
        assert len(calls) == 2
    else:
        assert calls[2:] == [(target, "stop")]
        assert panel.linking.records[target]["stop_feedback"] == "group_stop_idle"
    assert hass.states.is_state(attic["target"], "alarm")


@pytest.mark.parametrize(
    ("reply", "stops", "result"),
    [
        ("idle", 1, "group_stop_idle"),
        ("none", 1, "group_stop_unconfirmed"),
        ("foreign", 1, "group_stop_unconfirmed"),
        ("foreign_then_idle", 1, "group_stop_idle"),
        ("own_smoke", 1, "group_stop_unconfirmed"),
        ("retry_idle", 2, "group_stop_idle"),
        ("still_active", 2, "group_stop_still_active"),
    ],
)
async def test_group_stop_checks_fresh_feedback_and_limits_retries(
    hass, devices, monkeypatch, reply, stops, result
):
    if reply != "retry_idle":
        monkeypatch.setattr(
            "custom_components.alarmmesh.linking_runtime.GROUP_STOP_CHECK_SECONDS", 0.08
        )
    add, calls, _ = devices
    landing, hall = add("landing"), add("hall")
    members = [d["source"] for d in (landing, hall)]
    entry = await setup(hass, members)
    panel = entry.runtime_data.panel
    group = await configure(hass, entry, members, [hall])
    target = hall["target"]
    stop_times = []

    async def device_action(call):
        option = call.data["option"]
        calls.append(option)
        if option == "stop":
            stop_times.append(hass.loop.time())
        state = hass.states.get(target)
        if (
            option == "smoke_siren"
            or reply == "idle"
            or (reply == "retry_idle" and calls.count("stop") == 2)
        ):
            hass.states.async_set(
                target, option, state.attributes, context=call.context
            )
        elif reply != "none":
            # An unchanged HA state can get fresh reports with different contexts.
            hass.states.async_set(
                target,
                "smoke_siren",
                state.attributes,
                context=None if reply.startswith("foreign") else call.context,
            )
            if reply == "foreign_then_idle":
                await asyncio.sleep(0)
                hass.states.async_set(
                    target, "stop", state.attributes, context=call.context
                )
            if reply == "own_smoke":
                hass.states.async_set(hall["source"], "on", {"device_class": "smoke"})

    hass.services.async_register("select", "select_option", device_action)
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    start = panel.snapshot()["groups"][0]["group_stop_choices"][0]["start_id"]
    assert (await panel.linking.stop_group(group, panel.groups.revision, {start}))[
        "accepted"
    ] == 1
    await flush(hass, entry)
    assert calls == ["smoke_siren", *(["stop"] * stops)]
    if reply == "retry_idle":
        assert stop_times[1] - stop_times[0] >= 5
    events = [e for e in panel.activity.snapshot()["events"] if e["target"] == target]
    assert (
        sum(
            e["result"] == "group_stop_retry" and e["kind"] == "sounder_command"
            for e in events
        )
        == stops - 1
    )
    assert any(
        e["result"] == result and e["kind"] == "sounder_feedback" for e in events
    )
    assert panel.linking.records[target]["stop_feedback"] == result
    assert not panel.linking._group_checks
    assert (await panel.linking.stop_group(group, panel.groups.revision, {start}))[
        "accepted"
    ] == 0
    if reply == "own_smoke":
        assert hass.states.is_state(hall["source"], "on") and hass.states.is_state(
            target, "smoke_siren"
        )


async def test_group_stop_keeps_target_needed_by_other_group(hass, devices):
    add, calls, _ = devices
    landing, hall, other = (add(n) for n in ("landing", "hall", "other_floor"))
    entry = await setup(hass, [d["source"] for d in (landing, hall, other)])
    group = await configure(hass, entry, [landing["source"], hall["source"]], [hall])
    await configure(hass, entry, [other["source"], hall["source"]], [hall])
    panel = entry.runtime_data.panel
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    start = panel.snapshot()["groups"][0]["group_stop_choices"][0]["start_id"]
    hass.states.async_set(other["source"], "on", {"device_class": "smoke"})
    result = await panel.linking.stop_group(group, panel.groups.revision, {start})
    assert result["accepted"] == 0
    await flush(hass, entry)
    assert all(not g["group_stop_choices"] for g in panel.snapshot()["groups"])
    assert len(calls) == 1


async def test_group_stop_rechecks_ownership_and_handles_concurrent_requests(
    hass, devices
):
    add, calls, failures = devices
    landing, hall, test = (add(name) for name in ("landing", "hall", "test"))
    members = [d["source"] for d in (landing, hall, test)]
    entry = await setup(hass, members)
    group = await configure(hass, entry, members, [hall, test])
    panel = entry.runtime_data.panel
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    choices = panel.snapshot()["groups"][0]["group_stop_choices"]
    starts = {row["start_id"] for row in choices}
    revision = panel.groups.revision
    stale = await panel.linking.stop_group(group, revision - 1, starts)
    assert stale["accepted"] == 0
    # A new, unrelated context can report the same tone.
    attrs = dict(hass.states.get(hall["target"]).attributes)
    hass.states.async_set(hall["target"], "smoke_siren", {**attrs, "sequence": 2})
    failures.add(test["target"])
    results = await asyncio.gather(
        panel.linking.stop_group(group, revision, starts),
        panel.linking.stop_group(group, revision, starts),
    )
    await flush(hass, entry)
    assert all(result["accepted"] == 0 for result in results)
    assert [data for _, _, data in calls[2:]] == [
        {"entity_id": test["target"], "option": "stop"}
    ]
    assert panel.linking.records[test["target"]]["status"] == "stop_failed"
    assert all(hass.states.is_state(d["target"], "smoke_siren") for d in (hall, test))


@pytest.mark.parametrize(
    "model,origin,vendor,profile",
    [
        ("HS1SA-E-PLUS", "mqtt", "Heiman", "heiman_mqtt"),
        ("JY-GZ-01AQ", "mqtt", "Aqara", "aqara_mqtt"),
        ("SMSZB-120", "mqtt", "Develco", "smszb_mqtt"),
        ("SMSZB-120", "zha", "frient A/S", "smszb_zha"),
    ],
)
async def test_verified_profiles_require_actual_controls(
    hass, devices, model, origin, vendor, profile
):
    add, calls, _ = devices
    d = add("profile", model, origin, vendor)
    info = Capabilities(hass).describe(d["source"])
    assert info["status"] == "linkable" and info["controls"][0]["profile"] == profile
    assert not info["physical_tested"] and not calls
    hass.states.async_remove(d["target"])
    assert Capabilities(hass).describe(d["source"])["status"] == "not_confirmed"


@pytest.mark.parametrize(
    "model,origin,vendor",
    [
        ("Unknown", "mqtt", "Heiman"),
        ("HS1SA-E-PLUS", "zha", "Heiman"),
        ("lumi.sensor_smoke.acn03", "zha", "LUMI"),
        ("94430", "zha", "frient A/S"),
        ("HS1SA-E-PLUS", "mqtt", "Other"),
    ],
)
async def test_no_invented_model_or_zha_equivalence(
    hass, devices, model, origin, vendor
):
    add, calls, _ = devices
    info = Capabilities(hass).describe(
        add("unsupported", model, origin, vendor)["source"]
    )
    assert (
        info["status"] in {"detection_only", "not_confirmed"}
        and not info["controls"]
        and not calls
    )


async def test_settings_options_services_disabled_entities_and_ambiguity(hass, devices):
    add, _, _ = devices
    d = add("aqara", "JY-GZ-01AQ", vendor="Aqara")
    cap = Capabilities(hass)
    hass.states.async_set(d["setting"], "off")
    assert cap.describe(d["source"])["status"] == "setting_needed"
    hass.states.async_set(d["setting"], "unknown")
    assert cap.resolve(binding(hass, d)) is None
    hass.states.async_set(d["setting"], "on")
    hass.states.async_set(d["target"], "mute", {"options": ["mute"]})
    assert cap.describe(d["source"])["reason"] == "invalid_control_options"
    hass.states.async_set(d["target"], "mute", {"options": ["mute", "alarm"]})
    hass.services.async_remove("select", "select_option")
    assert cap.describe(d["source"])["reason"] == "service_missing"


async def test_aqara_discovery_switch_is_device_bound_and_reports_blocker(
    hass, devices
):
    add, calls, _ = devices
    attic = add("attic", "JY-GZ-01AQ", vendor="Aqara")
    other = add("other", "JY-GZ-01AQ", vendor="Aqara")
    cap = Capabilities(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get(attic["setting"])
    owner = hass.config_entries.async_get_entry(legacy.config_entry_id)
    uid = "sim_attic_switch_linkage_alarm_zigbee2mqtt"
    current = registry.async_get_or_create(
        "switch",
        "mqtt",
        uid,
        config_entry=owner,
        device_id=attic["device"],
        suggested_object_id="renamed_attic_setting",
    )
    source = attic["source"]
    hass.states.async_set(current.entity_id, "on")
    assert cap.describe(source)["reason"] == "aqara_linkage_ambiguous"
    assert cap.resolve(binding(hass, attic)) is None
    registry.async_remove(legacy.entity_id)
    assert cap.describe(source)["status"] == "linkable"
    saved = binding(hass, attic)
    for value, reason in (
        ("off", "aqara_linkage_required"),
        ("unavailable", "aqara_linkage_unavailable"),
        ("unknown", "aqara_linkage_unavailable"),
    ):
        hass.states.async_set(current.entity_id, value)
        assert cap.describe(source)["reason"] == reason
        assert cap.resolve(saved) is None
    hass.states.async_set(current.entity_id, "on")
    assert cap.resolve(saved) is not None
    registry.async_remove(current.entity_id)
    assert hass.states.is_state(other["setting"], "on")
    assert cap.describe(source)["reason"] == "aqara_linkage_missing"
    assert cap.resolve(saved) is None
    assert not calls


async def test_write_only_aqara_uses_independent_device_feedback(hass, devices):
    add, calls, _ = devices
    origin = add("origin")
    attic = add("attic", "JY-GZ-01AQ", vendor="Aqara")
    other = add("other", "JY-GZ-01AQ", vendor="Aqara")
    cap = Capabilities(hass)
    er.async_get(hass).async_update_entity(
        attic["setting"], new_unique_id="sim_attic_switch_linkage_alarm_zigbee2mqtt"
    )
    target = attic["target"]
    hass.states.async_set(target, "unknown", dict(hass.states.get(target).attributes))
    members = [origin["source"], attic["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [attic])
    saved = binding(hass, attic)
    hass.states.async_set(attic["feedback"], "on")
    assert not cap.is_idle(cap.resolve(saved))
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert not calls
    hass.states.async_set(attic["feedback"], "off")
    await flush(hass, entry)
    assert not calls  # A manually stopped target stays quiet in this incident.
    hass.states.async_set(origin["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(origin["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == [
        ("select", "select_option", {"entity_id": target, "option": "alarm"})
    ]
    for value in ("unknown", "unavailable"):
        hass.states.async_set(attic["feedback"], value)
        assert cap.resolve(saved) is None
        assert cap.describe(attic["source"])["reason"] == "aqara_feedback_needed"
    hass.states.async_remove(attic["feedback"])
    assert hass.states.is_state(other["feedback"], "off") and cap.resolve(saved) is None


async def test_foreign_device_and_replaced_registry_identity_never_bind(hass, devices):
    add, _, _ = devices
    a, b = add("a"), add("b")
    cap = Capabilities(hass)
    old = binding(hass, a)
    old["target"] = b["target"]
    assert cap.resolve(old) is None
    old = binding(hass, a)
    er.async_get(hass).async_update_entity(
        a["target"], new_unique_id="different_under_same_entity_id"
    )
    assert cap.resolve(old) is None


async def test_legacy_groups_default_off_without_rewriting(hass):
    store = GroupStore(hass, "legacy")
    legacy = {
        "revision": 4,
        "groups": [
            {"id": "a" * 32, "name": "Original", "members": ["binary_sensor.old"]}
        ],
    }
    with (
        patch.object(store.store, "async_load", return_value=legacy),
        patch.object(store.store, "async_save", new_callable=AsyncMock) as save,
    ):
        await store.async_load()
        assert store.revision == 4 and store.groups[0]["id"] == "a" * 32
        assert store.groups[0]["linking"] == {"enabled": False, "bindings": []}
        save.assert_not_called()


async def test_default_off_confirmation_and_atomic_failure(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    entry = await setup(hass, [a["source"], b["source"]])
    panel = entry.runtime_data.panel
    await panel.groups.async_mutate(
        {
            "operation": "create",
            "revision": 0,
            "name": "Default",
            "members": list(entry.runtime_data.source_entity_ids),
        },
        entry.runtime_data.source_entity_ids,
    )
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert not calls and not panel.groups.groups[0]["linking"]["enabled"]
    payload = {
        "operation": "update",
        "group_id": panel.groups.groups[0]["id"],
        "revision": 1,
        "name": "Enabled",
        "members": list(entry.runtime_data.source_entity_ids),
        "linking": {"enabled": True, "bindings": [binding(hass, b)]},
    }
    with pytest.raises(GroupError, match="confirmation"):
        await panel.groups.async_mutate(payload, entry.runtime_data.source_entity_ids)
    before = deepcopy(panel.groups.groups)
    with patch.object(
        panel.groups.store, "async_save", side_effect=OSError("simulated disk failure")
    ):
        with pytest.raises(OSError):
            await panel.groups.async_mutate(
                {**payload, "confirmed": True}, entry.runtime_data.source_entity_ids
            )
    await flush(hass, entry)
    assert panel.groups.groups == before and panel.groups.revision == 1 and not calls


async def test_mixed_targets_fail_independently_deduplicate_and_never_mute(
    hass, devices
):
    add, calls, failures = devices
    a, b = add("a"), add("b")
    c = add("c", "SMSZB-120", "zha", "frient A/S")
    d = add("d", "JY-GZ-01AQ", vendor="Aqara")
    members = [x["source"] for x in (a, b, c, d)]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b, c, d])
    await configure(hass, entry, members, [b, c])
    failures.add(b["target"])
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert {call[2]["entity_id"] for call in calls} == {
        b["target"],
        c["target"],
        d["target"],
    }
    assert len(calls) == 3
    assert next(call[2] for call in calls if call[0] == "siren") == {
        "entity_id": c["target"],
        "duration": 60,
    }
    assert {r["status"] for r in entry.runtime_data.panel.linking.records.values()} == {
        "failed",
        "sent_no_auto_stop",
    }
    for _ in range(4):
        hass.states.async_set(
            a["source"], "on", {"device_class": "smoke", "iteration": _}
        )
        await flush(hass, entry)
    assert len(calls) == 3
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 3 and all(call[2].get("option") != "mute" for call in calls)


@pytest.mark.parametrize(
    "model",
    [
        "S1-M",
        "S1-TL",
        "S1-TL-AI",
        "S2-E",
        "HS1SA-E Lover",
        "HM-636THV-AC-M",
        "HS1SA-E-PLUS",
    ],
)
async def test_multiple_origins_unknown_and_local_smoke_never_stop(
    hass, devices, model
):
    add, calls, _ = devices
    a, b, c = add("a"), add("b", model), add("c")
    members = [d["source"] for d in (a, b, c)]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    for source in (a["source"], c["source"]):
        hass.states.async_set(source, "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    hass.states.async_set(c["source"], "unavailable", {"device_class": "smoke"})
    await flush(hass, entry)
    assert entry.runtime_data.panel.linking.active == {c["source"]} and len(calls) == 1
    hass.states.async_set(b["source"], "on", {"device_class": "smoke"})
    hass.states.async_set(c["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1  # B now has local smoke; never hush it.
    hass.states.async_set(a["source"], "unavailable", {"device_class": "smoke"})
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1  # Even an earlier cleared origin is now unreadable.
    hass.states.async_set(
        a["source"], "off", {"device_class": "smoke", "assumed_state": True}
    )
    await flush(hass, entry)
    assert len(calls) == 1
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert [call[2]["option"] for call in calls] == ["smoke_siren", "stop"]


@pytest.mark.parametrize("feedback", ["unattributed", "assumed", "became_assumed"])
async def test_s1m_requires_attributable_observed_tone(hass, devices, feedback):
    add, calls, _ = devices
    source, target = add("source"), add("target", "S1-M")
    members = [source["source"], target["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [target])
    sounder = target["target"]
    attrs = dict(hass.states.get(sounder).attributes)

    async def report(call):
        calls.append(call.data["option"])
        hass.states.async_set(
            sounder,
            call.data["option"],
            {**attrs, "assumed_state": feedback == "assumed"},
            context=None if feedback == "unattributed" else call.context,
        )

    hass.services.async_register("select", "select_option", report)
    hass.states.async_set(source["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    if feedback == "became_assumed":
        assert sounder in entry.runtime_data.panel.linking.owned
        hass.states.async_set(sounder, "smoke_siren", {**attrs, "assumed_state": True})
        hass.states.async_set(sounder, "smoke_siren", attrs)
        await flush(hass, entry)
    hass.states.async_set(source["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert sounder not in entry.runtime_data.panel.linking.owned
    assert calls == ["smoke_siren"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_selftest_and_manual_sounding_are_not_sources(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    hass.states.async_set(a["test"], "on")
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    hass.states.async_set(
        a["target"], "smoke_siren", {"options": ["stop", "smoke_siren"]}
    )
    await flush(hass, entry)
    assert not calls and not entry.runtime_data.panel.linking.active
    hass.states.async_set(a["test"], "off")
    await flush(hass, entry)
    assert not calls


async def test_disabled_remapped_and_old_runtime_never_dispatch(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    group_id = await configure(hass, entry, members, [b])
    await configure(hass, entry, members, [b], group_id=group_id, enabled=False)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert not calls
    old = entry.runtime_data.panel.linking
    assert await hass.config_entries.async_reload(entry.entry_id)
    await flush(hass, entry)
    old.changed()
    assert old._closed and not calls
    await configure(hass, entry, members, [b], group_id=group_id)
    assert len(calls) == 1  # Existing ON is recognized, not only a future event.
    previous = entry.runtime_data.panel.linking
    assert await hass.config_entries.async_unload(entry.entry_id)
    previous.changed()
    assert previous._closed and len(calls) == 1


async def test_reload_does_not_adopt_or_stop_previous_or_manual_activation(
    hass, devices
):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    assert await hass.config_entries.async_reload(entry.entry_id)
    await flush(hass, entry)
    assert len(calls) == 1 and not entry.runtime_data.panel.linking.owned
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1


async def test_quiet_target_during_persistent_smoke_before_and_after_reload(
    hass, devices
):
    add, calls, _ = devices
    origin, other = add("origin"), add("other")
    members = [origin["source"], other["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [other])
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    attrs = dict(hass.states.get(other["target"]).attributes)
    hass.states.async_set(other["target"], "stop", attrs)
    hass.states.async_set(
        origin["source"], "on", {"device_class": "smoke", "sequence": 2}
    )
    await flush(hass, entry)
    assert [c[2]["option"] for c in calls] == ["smoke_siren"]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await flush(hass, entry)
    assert [c[2]["option"] for c in calls] == ["smoke_siren", "smoke_siren"]
    history = entry.runtime_data.panel.activity.snapshot()
    rows = list(reversed(history["events"]))
    commands = [r for r in rows if r["kind"] == "sounder_command"]
    assert [r["result"] for r in commands] == ["start_requested", "start_requested"]
    assert len({r["correlation"] for r in commands}) == 2
    assert all(r["origins"] == [origin["source"]] for r in commands)
    assert all(
        r["source"] == other["source"] and r["target"] == other["target"]
        for r in commands
    )
    observed = [
        r
        for r in rows
        if r["result"] == "SMOKE_REPORTED"
        and r["source"] == origin["source"]
        and r["kind"] in {"source", "startup_smoke"}
    ]
    assert [r["kind"] for r in observed] == ["source", "startup_smoke"]
    assert observed[0]["observed_at"] <= commands[0]["observed_at"]
    assert (
        commands[0]["observed_at"]
        <= observed[1]["observed_at"]
        <= commands[1]["observed_at"]
    )
    assert not history["incomplete"]


async def test_rapid_external_stop_and_restart_cannot_be_stopped_as_ours(hass, devices):
    add, calls, _ = devices
    origin, other = add("origin"), add("other")
    members = [origin["source"], other["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [other])
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    attrs = dict(hass.states.get(other["target"]).attributes)
    hass.states.async_set(other["target"], "stop", attrs)
    hass.states.async_set(other["target"], "smoke_siren", attrs)
    hass.states.async_set(origin["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert [c[2]["option"] for c in calls] == ["smoke_siren"]
    assert not entry.runtime_data.panel.linking.owned


async def test_pause_cancels_inflight_and_does_not_send_pending_targets(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    started = asyncio.Event()

    async def slow(call):
        started.set()
        await asyncio.Event().wait()

    hass.services.async_register("select", "select_option", slow)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await started.wait()
    engine = entry.runtime_data.panel.linking
    await engine.pause()
    assert engine.records[b["target"]]["status"] == "outcome_unknown"
    engine.changed()
    assert not calls and engine._task is None
    await engine.close()


async def test_backend_rejects_forged_mapping_without_dispatch(
    hass, devices, hass_ws_client
):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    client = await hass_ws_client(hass)
    fake = binding(hass, b)
    fake["identity"] = "0" * 64
    await client.send_json(
        {
            "id": 1,
            "type": "alarmmesh/group",
            "operation": "create",
            "revision": 0,
            "name": "Forgery",
            "members": members,
            "linking": {"enabled": True, "bindings": [fake]},
            "confirmed": True,
        }
    )
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "control_changed"
    assert not calls and entry.runtime_data.panel.groups.groups == []


@pytest.mark.parametrize(
    "features,tones", [(19, ["burglar"]), (31, ["emergency"]), (1, ["burglar"])]
)
async def test_mqtt_siren_never_uses_unsupported_implicit_emergency_tone(
    hass, devices, features, tones
):
    add, calls, _ = devices
    d = add("smszb", "SMSZB-120", vendor="Develco")
    hass.states.async_set(
        d["target"], "off", {"supported_features": features, "available_tones": tones}
    )
    assert Capabilities(hass).describe(d["source"])["status"] == "not_confirmed"
    assert not calls


async def test_mqtt_smszb_uses_explicit_burglar_and_bounded_duration(hass, devices):
    add, calls, _ = devices
    a = add("a")
    b = add("b", "SMSZB-120", vendor="Develco")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == [
        (
            "siren",
            "turn_on",
            {"entity_id": b["target"], "duration": 60, "tone": "burglar"},
        )
    ]


async def test_disabled_duplicate_controls_and_known_bad_firmware(hass, devices):
    add, _, _ = devices
    d = add("aq", "JY-GZ-01AQ", vendor="Aqara")
    cap = Capabilities(hass)
    dr.async_get(hass).async_update_device(d["device"], sw_version="0.0.0_0021")
    assert cap.describe(d["source"])["reason"] == "aqara_firmware_21"
    dr.async_get(hass).async_update_device(
        d["device"], sw_version="verified_other_version"
    )
    er.async_get(hass).async_update_entity(
        d["target"], disabled_by=er.RegistryEntryDisabler.USER
    )
    assert cap.describe(d["source"])["reason"] == "control_missing"
    z = add("z", "SMSZB-120", "zha", "frient A/S")
    er.async_get(hass).async_get_or_create(
        "siren", "zha", "another-control", device_id=z["device"]
    )
    assert cap.describe(z["source"])["reason"] == "ambiguous_control"


@pytest.mark.parametrize("control_state", ["unavailable", "unknown"])
async def test_target_readiness_recovery_does_not_lose_existing_smoke(
    hass, devices, control_state
):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    attrs = dict(hass.states.get(b["target"]).attributes)
    hass.states.async_set(b["target"], control_state, attrs)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert (
        not calls
        and entry.runtime_data.panel.linking.records[b["target"]]["status"] == "blocked"
    )
    hass.states.async_set(b["target"], "stop", attrs)
    await flush(hass, entry)
    assert len(calls) == 1 and calls[0][2]["option"] == "smoke_siren"


async def test_disable_does_not_stop_or_later_reclaim_an_old_activation(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    group_id = await configure(hass, entry, members, [b])
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    await configure(hass, entry, members, [b], group_id=group_id, enabled=False)
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1 and not entry.runtime_data.panel.linking.owned


async def test_selected_source_removal_requires_group_review(hass, devices):
    add, calls, _ = devices
    a, b, c = add("a"), add("b"), add("c")
    entry = await setup(hass, [d["source"] for d in (a, b, c)])
    await configure(hass, entry, list(entry.runtime_data.source_entity_ids), [c])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [b["source"], c["source"]]}
    )
    await flush(hass, entry)
    hass.states.async_set(b["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert (
        not calls
        and entry.runtime_data.panel.snapshot()["groups"][0]["linking_status"]
        == "review_needed"
    )


async def test_enabled_storage_with_initial_smoke_dispatches_after_setup(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await entry.runtime_data.panel.linking.pause()
    await configure(hass, entry, members, [b])
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await flush(hass, entry)
    assert len(calls) == 1 and entry.runtime_data.panel.linking.active == {a["source"]}


async def test_failed_stop_is_bounded_and_does_not_mute(hass, devices):
    add, calls, failures = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    failures.add(b["target"])
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert (
        len(calls) == 2
        and entry.runtime_data.panel.linking.records[b["target"]]["status"]
        == "stop_failed"
    )
    for i in range(3):
        hass.states.async_set(
            a["source"], "off", {"device_class": "smoke", "counter": i}
        )
        await flush(hass, entry)
    assert len(calls) == 2 and calls[-1][2]["option"] == "stop"


async def test_failed_unload_keeps_actions_paused_without_weakening_ha(hass, devices):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    engine = entry.runtime_data.panel.linking
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert engine.snapshot()["executor_state"] == "paused" and not calls


async def test_non_admin_cannot_enable_a_valid_mapping(hass, devices, hass_ws_client):
    add, calls, _ = devices
    a, b = add("a"), add("b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    user = await hass.auth.async_create_user(
        "Simulation reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    await client.send_json(
        {
            "id": 1,
            "type": "alarmmesh/group",
            "operation": "create",
            "revision": 0,
            "name": "Denied",
            "members": members,
            "linking": {"enabled": True, "bindings": [binding(hass, b)]},
            "confirmed": True,
        }
    )
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "unauthorized"
    assert not entry.runtime_data.panel.groups.groups and not calls


async def test_existing_manual_co_sounder_is_never_adopted_or_stopped(hass, devices):
    """A manual CO tone must not be replaced then owned as a smoke activation."""
    add, calls, _ = devices
    a, b = add("manual_co"), add("origin_co")
    members = [a["source"], b["source"]]
    attrs = dict(hass.states.get(a["target"]).attributes)
    hass.states.async_set(a["target"], "co_siren", attrs)
    entry = await setup(hass, members)
    await configure(hass, entry, members, [a])
    hass.states.async_set(b["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == []
    assert not entry.runtime_data.panel.linking.owned
    assert (
        entry.runtime_data.panel.linking.records[a["target"]]["status"]
        == "already_active"
    )
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == []


@pytest.mark.parametrize("attributable", [True, False])
async def test_delayed_heiman_start_confirmation_and_physical_hush(
    hass, devices, attributable
):
    add, calls, _ = devices
    origin, other = add("origin"), add("other")
    members = [origin["source"], other["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [other])
    attrs = dict(hass.states.get(other["target"]).attributes)
    contexts = []

    async def delayed(call):
        option = call.data["option"]
        calls.append(option)
        if option == "smoke_siren":
            contexts.append(call.context)
        else:
            hass.states.async_set(other["target"], option, attrs)

    hass.services.async_register("select", "select_option", delayed)
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    # Another HA observation arrives before the detector acknowledges the start.
    hass.states.async_set(origin["test"], "off", {"sequence": 1})
    await flush(hass, entry)
    hass.states.async_set(
        other["target"],
        "smoke_siren",
        attrs,
        context=contexts[0] if attributable else None,
    )
    await flush(hass, entry)
    # A physical button can silence a device while its smoke entity stays on.
    hass.states.async_set(
        origin["source"], "on", {"device_class": "smoke", "muted": True}
    )
    await flush(hass, entry)
    assert calls == ["smoke_siren"]
    hass.states.async_set(origin["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == (["smoke_siren", "stop"] if attributable else ["smoke_siren"])
    trace = [
        r
        for r in reversed(entry.runtime_data.panel.activity.snapshot()["events"])
        if r["kind"] in {"sounder_feedback", "sounder_command"}
        and r["target"] == other["target"]
    ]
    assert [r["result"] for r in trace] == (
        ["start_requested", "feedback_linked", "stop_requested"]
        if attributable
        else ["start_requested", "feedback_context_missing"]
    )
    assert len({r["correlation"] for r in trace}) == 1


async def test_manual_tone_replaces_our_ownership_before_clear(hass, devices):
    """A later manual CO selection cannot be stopped under earlier ownership."""
    add, calls, _ = devices
    a, b = add("owned_then_manual"), add("origin_manual")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [a])
    hass.states.async_set(b["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1 and calls[0][2]["option"] == "smoke_siren"
    hass.states.async_set(
        a["target"], "co_siren", dict(hass.states.get(a["target"]).attributes)
    )
    await flush(hass, entry)
    assert not entry.runtime_data.panel.linking.owned
    # Returning to the same tone does not restore old ownership.
    hass.states.async_set(
        a["target"], "smoke_siren", dict(hass.states.get(a["target"]).attributes)
    )
    await flush(hass, entry)
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    assert not entry.runtime_data.panel.linking.owned
    assert (
        entry.runtime_data.panel.linking.records[a["target"]]["status"] == "not_stopped"
    )


@pytest.mark.parametrize("late_context_matches", [True, False])
async def test_heiman_feedback_timeline_two_targets(
    hass, devices, late_context_matches
):
    """Two independent starts, a late report and a timely uncorrelated report."""
    add, calls, _ = devices
    landing, hall, other = add("landing"), add("hall"), add("test")
    members = [device["source"] for device in (landing, hall, other)]
    entry = await setup(hass, members)
    panel = entry.runtime_data.panel
    contexts = {}

    async def accept(call):
        target = call.data["entity_id"]
        calls.append((target, call.data["option"]))
        contexts[target] = call.context

    hass.services.async_register("select", "select_option", accept)
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls == []  # No default permission.
    hass.states.async_set(landing["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    await configure(hass, entry, members, [hall, other])
    hass.states.async_set(landing["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)

    def report(device, value, context=None):
        target = device["target"]
        hass.states.async_set(
            target, value, dict(hass.states.get(target).attributes), context=context
        )
        return hass.states.get(target).last_updated.isoformat()

    other_observed = report(other, "smoke_siren")
    await flush(hass, entry)
    # Drive the actual deadline callback before the next HA report.
    panel.linking._expire_pending(hall["target"])
    context = contexts[hall["target"]] if late_context_matches else None
    hall_observed = report(hall, "smoke_siren", context)
    await flush(hass, entry)
    for device in (other, hall):
        report(device, "stop")
        await flush(hass, entry)
    hass.states.async_set(landing["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert not panel.linking.owned
    assert sorted(calls) == sorted(
        (device["target"], "smoke_siren") for device in (hall, other)
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await flush(hass, entry)
    history = entry.runtime_data.panel.activity.snapshot()
    assert not history["incomplete"]
    traces = {}
    for device, expected, observed in (
        (
            hall,
            [
                "feedback_window_expired",
                "feedback_late_matched"
                if late_context_matches
                else "feedback_late_unmatched",
                "feedback_idle_observed",
            ],
            hall_observed,
        ),
        (other, ["feedback_context_missing", "feedback_idle_observed"], other_observed),
    ):
        events = [
            r
            for r in reversed(history["events"])
            if r["target"] == device["target"]
            and r["kind"] in {"sounder_feedback", "sounder_command"}
        ]
        assert [r["result"] for r in events] == ["start_requested", *expected]
        assert all(
            r["source"] == device["source"] and r["origins"] == [landing["source"]]
            for r in events
        )
        assert len({r["correlation"] for r in events}) == 1
        assert events[-2]["observed_at"] == observed
        traces[device["target"]] = events[0]["correlation"]
    assert len(set(traces.values())) == 2


async def test_review_new_group_incident_while_other_group_remains_active(
    hass, devices
):
    """The review reproduction: A/B must rearm independently of active C/D."""
    add, calls, _ = devices
    a, b, c, d = (
        add(name) for name in ("review_a", "review_b", "review_c", "review_d")
    )
    members = [device["source"] for device in (a, b, c, d)]
    entry = await setup(hass, members)
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [c["source"], d["source"]], [d])
    for origin in (a, c):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2
    assert {call[2]["entity_id"] for call in calls} == {b["target"], d["target"]}
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert hass.states.get(b["target"]).state == "stop"
    assert calls[-1][2] == {"entity_id": b["target"], "option": "stop"}
    assert entry.runtime_data.panel.linking.active == {c["source"]}
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    starts = [
        call
        for call in calls
        if call[2]["entity_id"] == b["target"]
        and call[2].get("option") == "smoke_siren"
    ]
    assert len(starts) == 2, "New A/B incident must reactivate B while C/D stays active"
    assert len([call for call in calls if call[2]["entity_id"] == d["target"]]) == 1


async def test_new_incidents_in_same_group_rearm_without_repeated_event_storm(
    hass, devices
):
    add, calls, _ = devices
    a, b = add("repeat_a"), add("repeat_b")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [b])
    for incident in range(3):
        hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
        await flush(hass, entry)
        for _ in range(3):
            hass.states.async_set(
                a["source"], "on", {"device_class": "smoke"}, force_update=True
            )
            await flush(hass, entry)
        assert [call[2]["option"] for call in calls] == [
            "smoke_siren",
            "stop",
        ] * incident + ["smoke_siren"]
        hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
        await flush(hass, entry)
        assert [call[2]["option"] for call in calls] == ["smoke_siren", "stop"] * (
            incident + 1
        )


async def test_overlapping_target_rearms_only_after_all_relevant_origins_clear(
    hass, devices
):
    add, calls, _ = devices
    a, b, c, d, e = (
        add(name)
        for name in ("overlap_a", "overlap_b", "overlap_c", "other_d", "other_e")
    )
    entry = await setup(hass, [device["source"] for device in (a, b, c, d, e)])
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [c["source"], b["source"]], [b])
    await configure(hass, entry, [d["source"], e["source"]], [e])
    for origin in (a, d):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2
    hass.states.async_set(c["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(c["source"], "unavailable", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2  # Overlap and missing information do not end the episode.
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(c["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert calls[-1][2] == {"entity_id": b["target"], "option": "stop"}
    hass.states.async_set(c["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert [
        call[2]["option"] for call in calls if call[2]["entity_id"] == b["target"]
    ] == ["smoke_siren", "stop", "smoke_siren"]
    assert len([call for call in calls if call[2]["entity_id"] == e["target"]]) == 1


async def test_failed_attempt_stays_suppressed_through_join_disable_and_reenable(
    hass, devices
):
    add, calls, failures = devices
    a, b, c, d, e = (
        add(name)
        for name in ("failure_a", "failure_b", "failure_c", "active_d", "active_e")
    )
    entry = await setup(hass, [device["source"] for device in (a, b, c, d, e)])
    members = [a["source"], b["source"], c["source"]]
    group_id = await configure(hass, entry, members, [b])
    await configure(hass, entry, [d["source"], e["source"]], [e])
    failures.add(b["target"])
    for origin in (a, d):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2
    hass.states.async_set(c["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    failures.remove(b["target"])
    await configure(hass, entry, members, [b], group_id=group_id, enabled=False)
    await configure(hass, entry, members, [b], group_id=group_id)
    for _ in range(3):
        hass.states.async_set(
            c["source"], "on", {"device_class": "smoke"}, force_update=True
        )
        await flush(hass, entry)
    assert (
        len(calls) == 2
    )  # Neither another origin nor a settings edit retries failure.
    hass.states.async_set(c["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 3 and calls[-1][2] == {
        "entity_id": b["target"],
        "option": "smoke_siren",
    }


async def test_activation_only_target_expiry_does_not_retry_until_its_next_incident(
    hass, devices
):
    add, calls, _ = devices
    a, c, d = add("duration_a"), add("duration_c"), add("duration_d")
    b = add("duration_b", "SMSZB-120", "zha", "frient A/S")
    entry = await setup(hass, [device["source"] for device in (a, b, c, d)])
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [c["source"], d["source"]], [d])
    for origin in (a, c):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2
    # Simulate expiry reported by the mock device; never add a timer or renewal.
    hass.states.async_set(
        b["target"], "off", dict(hass.states.get(b["target"]).attributes)
    )
    await flush(hass, entry)
    assert len(calls) == 2
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert [call[2] for call in calls if call[2]["entity_id"] == b["target"]] == [
        {"entity_id": b["target"], "duration": 60},
        {"entity_id": b["target"], "duration": 60},
    ]
    assert len([call for call in calls if call[2]["entity_id"] == d["target"]]) == 1


async def test_manual_target_remains_unclaimed_until_a_separate_relevant_incident(
    hass, devices
):
    add, calls, _ = devices
    a, b, c, d = (add(name) for name in ("manual_a", "manual_b", "other_c", "other_d"))
    hass.states.async_set(
        b["target"], "smoke_siren", dict(hass.states.get(b["target"]).attributes)
    )
    entry = await setup(hass, [device["source"] for device in (a, b, c, d)])
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [c["source"], d["source"]], [d])
    for origin in (a, c):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1 and b["target"] not in entry.runtime_data.panel.linking.owned
    hass.states.async_set(
        b["target"], "stop", dict(hass.states.get(b["target"]).attributes)
    )
    await flush(hass, entry)
    assert (
        len(calls) == 1
    )  # A manual stop during the same incident grants no ownership.
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2 and calls[-1][2] == {
        "entity_id": b["target"],
        "option": "smoke_siren",
    }
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 3 and calls[-1][2] == {
        "entity_id": b["target"],
        "option": "stop",
    }


async def test_local_target_smoke_does_not_end_a_continuing_target_incident(
    hass, devices
):
    add, calls, _ = devices
    a, b, c, d, e = (
        add(name) for name in ("local_a", "local_b", "local_c", "other_d", "other_e")
    )
    entry = await setup(hass, [device["source"] for device in (a, b, c, d, e)])
    await configure(hass, entry, [a["source"], b["source"], c["source"]], [b])
    await configure(hass, entry, [d["source"], e["source"]], [e])
    for origin in (a, d):
        hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(b["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(c["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2  # No extra activation or stop around local smoke.
    hass.states.async_set(c["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 3 and calls[-1][2] == {
        "entity_id": b["target"],
        "option": "stop",
    }
    assert len([call for call in calls if call[2]["entity_id"] == e["target"]]) == 1


@pytest.mark.parametrize(
    ("model", "vendor", "expected_calls"),
    [("S1-M", "Heiman", 2), ("JY-GZ-01AQ", "Aqara", 1)],
)
async def test_linked_targets_own_smoke_visible_until_explicit_clear(
    hass, devices, model, vendor, expected_calls
):
    add, calls, _ = devices
    source = add("hall")["source"]
    detector = add("attic", model, vendor=vendor)
    target = detector["source"]
    entry = await setup(hass, [source, target])
    await configure(hass, entry, [source, target], [detector])
    hass.states.async_set(source, "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    hass.states.async_set(target, "on", {"device_class": "smoke"})
    hass.states.async_set(source, "off", {"device_class": "smoke"})
    await flush(hass, entry)
    current = entry.runtime_data.panel.snapshot()
    assert current["result"]["smoke"] == "SMOKE_REPORTED"
    assert [
        s["entity_id"] for s in current["sources"] if s["status"] == "SMOKE_REPORTED"
    ] == [target]
    assert len(calls) == 1
    hass.states.async_set(target, "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == expected_calls
    history = entry.runtime_data.panel.activity.snapshot()
    commands = [
        r["result"]
        for r in reversed(history["events"])
        if r["kind"] == "sounder_command"
    ]
    assert commands == (
        ["start_requested", "stop_requested"]
        if expected_calls == 2
        else ["start_requested"]
    )
    for detector_id in (source, target):
        assert [
            r["result"]
            for r in reversed(history["events"])
            if r["kind"] == "source" and r["source"] == detector_id
        ] == ["SMOKE_REPORTED", "NO_SMOKE_REPORTED"]
    assert not history["incomplete"]
    if expected_calls == 2:
        assert calls[-1][2] == {"entity_id": detector["target"], "option": "stop"}
