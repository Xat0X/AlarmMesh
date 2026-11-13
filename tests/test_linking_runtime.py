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


async def test_multiple_origins_unknown_and_local_smoke_never_stop(hass, devices):
    add, calls, _ = devices
    a, b, c = add("a"), add("b"), add("c")
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
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert [call[2]["option"] for call in calls] == ["smoke_siren", "stop"]


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
