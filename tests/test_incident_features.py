"""Real HA fixtures/registries/storage; every output is an in-memory test handler."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_catalog import catalog_devices as catalog_devices
from test_linking_runtime import binding, configure, setup
from test_linking_runtime import devices as devices

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.automation import (
    AutomationError,
    NotificationStore,
    recipients,
    script_target,
    validate_actions,
)
from custom_components.alarmmesh.effects import IncidentEffects
from custom_components.alarmmesh.groups import GroupError, GroupStore
from custom_components.alarmmesh.self_test import SelfTests

A, B, C = (f"binary_sensor.simulation_{n}" for n in "abc")


async def settle(hass, entry):
    for _ in range(12):
        await hass.async_block_till_done()
        panel = entry.runtime_data.panel
        tasks = [
            task
            for task in (
                panel.linking._task,
                panel.effects._task,
                *panel.selftests.tasks,
            )
            if task is not None
        ]
        if not tasks:
            return
        await asyncio.gather(*tasks)
    pytest.fail("Simulation did not settle")


@pytest.fixture
def outputs(hass):
    calls, failed = [], set()

    async def action(call):
        target = call.data.get("entity_id", call.service)
        calls.append((call.domain, target, dict(call.data)))
        if target in failed:
            raise HomeAssistantError("deliberate synthetic failure")

    for service in (
        "mobile_app_simulation_a",
        "mobile_app_simulation_b",
        "other_provider",
    ):
        hass.services.async_register("notify", service, action)
    hass.services.async_register("script", "turn_on", action)
    for name in ("first", "second", "recovery"):
        entity = er.async_get(hass).async_get_or_create(
            "script",
            "script",
            f"simulation_{name}",
            suggested_object_id=f"simulation_{name}",
        )
        hass.states.async_set(
            entity.entity_id, "off", {"friendly_name": f"SIMULATED {name}"}
        )
    return calls, failed


async def new_entry(hass, sources=(A, B, C)):
    for source in sources:
        hass.states.async_set(
            source,
            "off",
            {"device_class": "smoke", "friendly_name": f"SIMULATED {source[-1]}"},
        )
    return await setup(hass, list(sources))


def script(hass, name):
    value = script_target(hass, f"script.simulation_{name}")
    return {key: value[key] for key in ("entity_id", "identity")}


async def notifications(entry, *, recovery=True):
    settings = entry.runtime_data.panel.effects.settings
    await settings.save(
        {
            "enabled": True,
            "recovery": recovery,
            "recipients": [
                {"service": "mobile_app_simulation_a", "enabled": True},
                {"service": "mobile_app_simulation_b", "enabled": True},
            ],
        },
        settings.revision,
        True,
    )
    entry.runtime_data.panel.effects.changed()


async def group_actions(
    hass,
    entry,
    origins,
    *,
    members=None,
    group=None,
    start=("first",),
    recovery=("recovery",),
    enabled=True,
):
    panel = entry.runtime_data.panel
    await panel.groups.async_mutate(
        {
            "operation": "update" if group else "create",
            **({"group_id": group} if group else {}),
            "revision": panel.groups.revision,
            "name": "SIMULATED actions",
            "members": members or origins,
            "origins": origins,
            "actions": {
                "enabled": enabled,
                "start": [script(hass, s) for s in start],
                "recovery": [script(hass, s) for s in recovery],
            },
            "confirmed": True,
        },
        entry.runtime_data.source_entity_ids,
    )
    panel.linking.changed()
    await settle(hass, entry)
    return panel.groups.groups[-1]["id"] if not group else group


async def source(hass, entry, entity, value):
    hass.states.async_set(
        entity,
        value,
        {"device_class": "smoke", "friendly_name": f"SIMULATED {entity[-1]}"},
    )
    await settle(hass, entry)


async def test_default_off_never_sends_and_discovers_only_companion_services(
    hass, outputs
):
    entry = await new_entry(hass)
    await source(hass, entry, A, "on")
    assert not outputs[0]
    assert not entry.runtime_data.panel.effects.episodes
    assert {r["service"] for r in recipients(hass)} == {
        "mobile_app_simulation_a",
        "mobile_app_simulation_b",
    }
    assert (
        entry.runtime_data.panel.snapshot()["automation"]["settings"]["enabled"]
        is False
    )


async def test_notification_dedup_updates_recovery_and_independent_failures(
    hass, outputs
):
    calls, failed = outputs
    failed.add("mobile_app_simulation_b")
    entry = await new_entry(hass)
    await notifications(entry)
    await source(hass, entry, A, "on")
    assert len(calls) == 2
    assert all(c[0] == "notify" for c in calls)
    assert "SIMULATED a" in calls[0][2]["message"]
    assert calls[0][2]["title"] == "Smoke alert · SIMULATED a"
    assert calls[0][2]["data"]["url"].startswith("/alarmmesh?incident=")
    assert "push" not in calls[0][2]["data"]  # No unsupported critical payload.
    await source(hass, entry, A, "on")
    entry.runtime_data.panel.linking.changed()
    await settle(hass, entry)
    assert len(calls) == 2
    await source(hass, entry, C, "on")
    assert len(calls) == 4  # One meaningful new-source update per recipient.
    assert calls[-1][2]["title"] == "Smoke alert · SIMULATED c (+1)"
    assert calls[-1][2]["message"].startswith("SIMULATED c; SIMULATED a")
    assert calls[-1][2]["data"]["url"] == calls[0][2]["data"]["url"]
    await source(hass, entry, A, "off")
    await source(hass, entry, C, "unavailable")
    assert len(calls) == 4
    await source(hass, entry, C, "off")
    assert len(calls) == 6
    assert {
        r["status"]
        for e in entry.runtime_data.panel.effects.episodes.values()
        for r in e["receipts"].values()
    } == {"accepted", "failed"}


async def test_independent_group_lifetimes_origins_and_notification_updates(
    hass, outputs
):
    calls, _ = outputs
    entry = await new_entry(hass)
    await notifications(entry, recovery=False)
    await group_actions(hass, entry, [A], members=[A, B])
    await group_actions(hass, entry, [C], start=("second",))
    await source(hass, entry, B, "on")
    assert not any(c[0] == "script" for c in calls)  # B not an allowed origin.
    await source(hass, entry, B, "off")
    calls.clear()
    await source(hass, entry, A, "on")
    await source(hass, entry, C, "on")
    assert [c[1] for c in calls if c[0] == "script"] == [
        "script.simulation_first",
        "script.simulation_second",
    ]
    await source(hass, entry, A, "off")
    await source(hass, entry, A, "on")
    assert [c[1] for c in calls if c[0] == "script"].count(
        "script.simulation_first"
    ) == 2
    assert [c[1] for c in calls if c[0] == "script"].count(
        "script.simulation_second"
    ) == 1
    assert len([c for c in calls if c[0] == "notify"]) == 6


async def test_script_order_errors_do_not_block_other_outputs_or_recover_early(
    hass, outputs, devices
):
    add, sounder_calls, _ = devices
    a, b = add("trigger"), add("target")
    entry = await setup(hass, [a["source"], b["source"]])
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await notifications(entry)
    await group_actions(
        hass, entry, [a["source"], b["source"]], start=("first", "second")
    )
    outputs[1].add("script.simulation_first")
    await source(hass, entry, a["source"], "on")
    assert [c[1] for c in outputs[0] if c[0] == "script"] == [
        "script.simulation_first",
        "script.simulation_second",
    ]
    assert len(sounder_calls) == 1
    assert len([c for c in outputs[0] if c[0] == "notify"]) == 2
    await source(hass, entry, b["source"], "unavailable")
    await source(hass, entry, a["source"], "off")
    assert not any(c[1] == "script.simulation_recovery" for c in outputs[0])
    await source(hass, entry, b["source"], "off")
    assert [c[1] for c in outputs[0] if c[0] == "script"][
        -1
    ] == "script.simulation_recovery"


async def test_reload_preserves_receipts_but_rebuilds_current_source_truth(
    hass, outputs
):
    entry = await new_entry(hass)
    await notifications(entry)
    await group_actions(hass, entry, [A])
    await source(hass, entry, A, "on")
    expected = len(outputs[0])
    old = entry.runtime_data.panel
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert len(outputs[0]) == expected
    old.effects.changed()
    old.linking.changed()
    assert old.effects.closed and old.linking._closed
    await source(hass, entry, A, "unknown")
    assert len(outputs[0]) == expected
    await source(hass, entry, A, "on")
    assert len(outputs[0]) == expected  # Unknown is not a new lifetime.
    await source(hass, entry, A, "off")
    assert len(outputs[0]) == expected + 3
    await source(hass, entry, A, "on")
    assert len(outputs[0]) == expected + 6


async def test_missing_or_replaced_script_is_blocked_and_not_retried(hass, outputs):
    entry = await new_entry(hass)
    await group_actions(hass, entry, [A])
    registry = er.async_get(hass)
    old = registry.async_get("script.simulation_first")
    registry.async_remove(old.entity_id)
    registry.async_get_or_create(
        "script", "script", "replacement", suggested_object_id="simulation_first"
    )
    await source(hass, entry, A, "on")
    assert not outputs[0]
    receipts = list(entry.runtime_data.panel.effects.episodes.values())[0]["receipts"]
    assert next(iter(receipts.values()))["status"] == "blocked"
    entry.runtime_data.panel.effects.changed()
    await settle(hass, entry)
    assert not outputs[0]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"enabled": True},
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": "telegram", "enabled": True}],
        },
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": "mobile_app_unregistered", "enabled": True}],
        },
    ],
)
async def test_invalid_notification_settings_do_not_replace_saved_data(
    hass, outputs, value
):
    entry = await new_entry(hass)
    await notifications(entry)
    store = entry.runtime_data.panel.effects.settings
    before = deepcopy(store.value)
    with pytest.raises(AutomationError):
        await store.save(value, store.revision, True)
    assert store.value == before
    assert not outputs[0]


async def test_settings_atomic_failure_and_missing_recipient_visibility(hass, outputs):
    entry = await new_entry(hass)
    await notifications(entry)
    panel = entry.runtime_data.panel
    old, revision = (
        deepcopy(panel.effects.settings.value),
        panel.effects.settings.revision,
    )
    with patch.object(
        panel.effects.settings.store, "async_save", new=AsyncMock(side_effect=OSError)
    ):
        with pytest.raises(OSError):
            await panel.effects.settings.save(
                {**old, "enabled": False}, revision, False
            )
    assert (
        panel.effects.settings.value == old
        and panel.effects.settings.revision == revision
    )
    hass.services.async_remove("notify", "mobile_app_simulation_a")
    assert (
        "mobile_app_simulation_a"
        in panel.snapshot()["automation"]["missing_recipients"]
    )


@pytest.mark.parametrize("section", ["notifications", "receipts", "selftest"])
async def test_corrupt_storage_never_dispatches_or_overwrites(hass, outputs, section):
    entry = await new_entry(hass)
    panel = entry.runtime_data.panel
    instance = (
        NotificationStore(hass, "broken")
        if section == "notifications"
        else IncidentEffects(hass, entry, panel.linking, panel.groups, lambda: None)
        if section == "receipts"
        else SelfTests(hass, entry, panel.linking, lambda: None)
    )
    with (
        patch.object(
            instance.store,
            "async_load",
            new=AsyncMock(return_value={"unexpected": "corruption"}),
        ),
        patch.object(instance.store, "async_save", new=AsyncMock()) as save,
    ):
        with pytest.raises(AutomationError):
            await instance.load()
        save.assert_not_called()
    assert not outputs[0]


async def test_legacy_groups_keep_explicit_bindings_and_new_actions_off(hass, devices):
    add, _, _ = devices
    a, b = add("a"), add("b")
    store = GroupStore(hass, "legacy")
    existing = {
        "id": "a" * 32,
        "name": "Keep name",
        "members": [a["source"], b["source"]],
        "linking": {"enabled": True, "bindings": [binding(hass, b)]},
    }
    with (
        patch.object(
            store.store,
            "async_load",
            new=AsyncMock(
                return_value={"schema": 2, "revision": 4, "groups": [existing]}
            ),
        ),
        patch.object(store.store, "async_save", new=AsyncMock()) as save,
    ):
        await store.async_load()
        assert store.groups == [existing]
        assert "actions" not in store.groups[0]
        assert "origins" not in store.groups[0]
        save.assert_not_called()


async def test_store_rejects_unauthorized_scripts_origins_and_unconfirmed_actions(
    hass, outputs
):
    entry = await new_entry(hass)
    panel = entry.runtime_data.panel
    value = {
        "operation": "create",
        "revision": 0,
        "name": "No write",
        "members": [A],
        "origins": [B],
    }
    with pytest.raises(GroupError, match="invalid_origins"):
        await panel.groups.async_mutate(value, (A, B))
    value.update(
        origins=[A],
        actions={"enabled": True, "start": [script(hass, "first")], "recovery": []},
    )
    with pytest.raises(GroupError, match="automation_confirmation_required"):
        await panel.groups.async_mutate(value, (A, B))
    with pytest.raises(AutomationError):
        validate_actions(
            {
                "enabled": True,
                "start": [{"entity_id": "light.fake", "identity": "a" * 64}],
                "recovery": [],
            }
        )
    assert not panel.groups.groups and not outputs[0]
    with pytest.raises(AutomationError, match="invalid_actions"):
        validate_actions({"enabled": True, "start": [], "recovery": []})
    group = await group_actions(hass, entry, [A], members=[A, B])
    with pytest.raises(GroupError, match="automation_confirmation_required"):
        await panel.groups.async_mutate(
            {
                "operation": "update",
                "revision": panel.groups.revision,
                "group_id": group,
                "name": "No silent origin change",
                "members": [A, B],
                "origins": [B],
            },
            (A, B),
        )
    assert panel.groups.groups[0]["origins"] == [A] and not outputs[0]


@pytest.mark.parametrize(
    "kind,target", [("notification", "other_provider"), ("script", "script.missing")]
)
async def test_manual_requests_validate_targets_and_confirmation(
    hass, outputs, kind, target
):
    entry = await new_entry(hass)
    effects = entry.runtime_data.panel.effects
    with pytest.raises(AutomationError, match="test_confirmation_required"):
        await effects.manual(kind, target, "", False, uuid4().hex)
    with pytest.raises(AutomationError):
        await effects.manual(kind, target, "a" * 64, True, uuid4().hex)
    assert not outputs[0]


async def test_manual_notification_is_explicit_single_request_with_no_auto_retry(
    hass, outputs
):
    entry = await new_entry(hass)
    effects = entry.runtime_data.panel.effects
    request = uuid4().hex
    result = await effects.manual(
        "notification", "mobile_app_simulation_a", "", True, request
    )
    assert result["status"] == "accepted"
    assert (
        len(outputs[0]) == 1
        and "test notification" in outputs[0][0][2]["message"].lower()
    )
    with pytest.raises(AutomationError, match="test_busy"):
        await effects.manual(
            "notification", "mobile_app_simulation_a", "", True, request
        )
    assert len(outputs[0]) == 1


async def test_revoked_admin_and_cancelled_unload_cannot_dispatch_waiting_work(
    hass, outputs
):
    entry = await new_entry(hass)
    panel = entry.runtime_data.panel
    for _ in range(8):
        await panel.linking._semaphore.acquire()
    task = asyncio.create_task(
        panel.effects.manual(
            "notification",
            "mobile_app_simulation_a",
            "",
            True,
            uuid4().hex,
            lambda: False,
        )
    )
    await hass.async_block_till_done()
    panel.linking._semaphore.release()
    assert (await task)["status"] == "failed"
    assert not outputs[0]
    await panel.linking._semaphore.acquire()
    task = asyncio.create_task(
        panel.effects.manual(
            "notification", "mobile_app_simulation_a", "", True, uuid4().hex
        )
    )
    await hass.async_block_till_done()
    await panel.async_pause()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not outputs[0]
    for _ in range(8):
        panel.linking._semaphore.release()


def add_test_device(add, model="HS1SA-E-PLUS", vendor="Heiman", origin="mqtt"):
    d = add(model, vendor, origin=origin)
    key = (
        "self_test"
        if origin == "zha"
        else "selftest"
        if model.startswith("JY")
        else "test_cycle"
        if model.startswith("HALO")
        else "trigger_selftest"
    )
    domain = "select" if model.startswith("HALO") else "button"
    target = d["register"](
        domain,
        key,
        "unknown",
        {"options": ["start", "cancel"]} if domain == "select" else {},
    )
    flag = d["register"](
        "binary_sensor",
        "self_test_state"
        if origin == "zha"
        else "test_in_progress"
        if model.startswith("HALO")
        else "test",
        "off",
        {},
    )
    result = (
        d["register"]("sensor", "halo_test_result", "success", {})
        if model.startswith("HALO")
        else None
    )
    return {**d, "test_target": target, "flag": flag, "result": result}


@pytest.mark.parametrize(
    "model,vendor,origin",
    [
        ("HS1SA-E-PLUS", "Heiman", "mqtt"),
        ("JY-GZ-01AQ", "Aqara", "mqtt"),
        ("JY-GZ-03AQ", "Aqara", "mqtt"),
        ("lumi.sensor_smoke.acn03", "LUMI", "zha"),
        ("HALO", "Halo Smart Labs", "mqtt"),
        ("HALO+", "Halo Smart Labs", "mqtt"),
    ],
)
async def test_reviewed_selftest_routes_send_exact_ha_request_not_sounder(
    hass, catalog_devices, model, vendor, origin
):
    add, calls = catalog_devices
    d = add_test_device(add, model, vendor, origin)
    entry = await setup(hass, [d["source"]])
    tests = entry.runtime_data.panel.selftests

    async def command(call):
        calls.append((call.domain, call.service, dict(call.data)))

    hass.services.async_register("button", "press", command)
    if model.startswith("HALO"):
        hass.services.async_register("select", "select_option", command)
    control = tests.resolve(d["source"])
    assert control is not None
    result = await tests.start(
        d["source"], control["identity"], True, request_id=uuid4().hex
    )
    assert calls == [
        (
            "select" if model.startswith("HALO") else "button",
            "select_option" if model.startswith("HALO") else "press",
            {
                "entity_id": d["test_target"],
                **({"option": "start"} if model.startswith("HALO") else {}),
            },
        )
    ]
    assert result["status"] == "request_sent"
    assert result["status"] != "device_success"  # Even a stale success is not accepted.
    await tests.close()


async def test_selftest_explicit_result_timeout_restart_and_real_smoke_are_separate(
    hass, catalog_devices, outputs
):
    add, _ = catalog_devices
    d = add_test_device(add, "HALO", "Halo Smart Labs")
    entry = await setup(hass, [d["source"]])
    await notifications(entry)
    await group_actions(hass, entry, [d["source"]])
    tests = entry.runtime_data.panel.selftests
    control = tests.resolve(d["source"])
    await tests.start(d["source"], control["identity"], True, request_id=uuid4().hex)
    hass.states.async_set(d["result"], "running")
    await settle(hass, entry)
    assert tests.record["status"] == "test_active"
    assert not outputs[0]
    hass.states.async_set(d["result"], "success")
    await settle(hass, entry)
    assert tests.record["status"] == "device_success"
    await tests.start(d["source"], control["identity"], True, request_id=uuid4().hex)
    hass.states.async_set(d["flag"], "on")
    await settle(hass, entry)
    await source(hass, entry, d["source"], "on")
    assert entry.runtime_data.panel.snapshot()["result"]["smoke"] == "SMOKE_REPORTED"
    assert {c[0] for c in outputs[0]} == {"notify", "script"}
    assert len(outputs[0]) == 3  # Genuine separate smoke is not suppressed by test.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await settle(hass, entry)
    assert tests.record["status"] == "outcome_unknown"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert entry.runtime_data.panel.selftests.record["status"] == "outcome_unknown"
    assert len(outputs[0]) == 3


async def test_selftest_rejects_conflicts_second_device_and_unconfirmed_payload(
    hass, catalog_devices
):
    add, calls = catalog_devices
    a, b = add_test_device(add), add_test_device(add)

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [a["source"], b["source"]])
    tests = entry.runtime_data.panel.selftests
    identity = tests.resolve(a["source"])["identity"]
    with pytest.raises(AutomationError, match="test_confirmation_required"):
        await tests.start(a["source"], identity, False, request_id=uuid4().hex)
    await source(hass, entry, b["source"], "unavailable")
    with pytest.raises(AutomationError, match="test_conflict"):
        await tests.start(a["source"], identity, True, request_id=uuid4().hex)
    await source(hass, entry, b["source"], "off")
    request = uuid4().hex
    await tests.start(a["source"], identity, True, request_id=request)
    with pytest.raises(AutomationError, match="test_busy"):
        await tests.start(
            b["source"],
            tests.resolve(b["source"])["identity"],
            True,
            request_id=uuid4().hex,
        )
    assert len(calls) == 1
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    tests = entry.runtime_data.panel.selftests
    assert tests.record["status"] == "outcome_unknown"
    with pytest.raises(AutomationError, match="test_busy"):
        await tests.start(
            a["source"],
            tests.resolve(a["source"])["identity"],
            True,
            request_id=request,
        )


@pytest.mark.parametrize(
    "model,vendor,origin",
    [
        ("SMSZB-120", "Develco", "zha"),
        ("HS1SA-E-PLUS", "HEIMAN", "zha"),
        ("TS0601", "_TZE200_unknown", "mqtt"),
    ],
)
async def test_sounder_or_generic_smoke_never_invents_selftest(
    hass, catalog_devices, model, vendor, origin
):
    add, calls = catalog_devices
    d = add(model, vendor, origin=origin)
    entry = await setup(hass, [d["source"]])
    assert entry.runtime_data.panel.selftests.resolve(d["source"]) is None
    assert not calls


@pytest.mark.parametrize("kind", ["notification", "script", "selftest"])
async def test_all_test_routes_require_admin_and_reject_browser_payloads(
    hass, outputs, hass_ws_client, kind
):
    entry = await new_entry(hass)
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
            "type": "alarmmesh/test",
            "kind": kind,
            "target": "mobile_app_simulation_a",
            "confirmed": True,
            "request_id": uuid4().hex,
        }
    )
    response = await client.receive_json()
    assert response["error"]["code"] == "unauthorized"
    await client.send_json(
        {
            "id": 2,
            "type": "alarmmesh/settings",
            "revision": 0,
            "notifications": {"enabled": False, "recovery": False, "recipients": []},
        }
    )
    assert (await client.receive_json())["error"]["code"] == "unauthorized"
    admin = await hass_ws_client(hass)
    await admin.send_json(
        {
            "id": 3,
            "type": "alarmmesh/test",
            "kind": kind,
            "target": "light.arbitrary",
            "confirmed": True,
            "request_id": uuid4().hex,
            "payload": {"service": "turn_off"},
        }
    )
    assert (await admin.receive_json())["error"]["code"] == "invalid_format"
    assert not outputs[0]
    assert entry.runtime_data.panel.effects.settings.revision == 0


async def test_request_rechecks_script_and_notifies_other_recipients_after_timeout(
    hass, outputs
):
    entry = await new_entry(hass)
    await notifications(entry)

    async def timeout(_call):
        raise TimeoutError

    hass.services.async_register("notify", "mobile_app_simulation_b", timeout)
    await source(hass, entry, A, "on")
    assert len(outputs[0]) == 1
    receipts = entry.runtime_data.panel.effects.episodes["notifications"]["receipts"]
    assert receipts["mobile_app_simulation_b"]["status"] == "failed"
    await source(hass, entry, A, "on")
    assert len(outputs[0]) == 1


async def test_retention_expiry_discards_recovered_receipts_not_active_incidents(
    hass, outputs, freezer
):
    entry = await new_entry(hass)
    await notifications(entry)
    await source(hass, entry, A, "on")
    effects = entry.runtime_data.panel.effects
    freezer.move_to(dt_util.utcnow() + timedelta(hours=25))
    effects.changed()
    await settle(hass, entry)
    assert "notifications" in effects.episodes
    await source(hass, entry, A, "off")
    freezer.move_to(dt_util.utcnow() + timedelta(hours=25))
    effects.changed()
    await settle(hass, entry)
    assert not effects.episodes
    assert (await effects.store.async_load())["episodes"] == {}


async def test_real_script_entity_api_supports_recovery_only_configuration(hass):
    from homeassistant.setup import async_setup_component

    events = []
    hass.bus.async_listen(
        "alarmmesh_simulated_script", lambda event: events.append(event.data["name"])
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "simulation_recovery": {
                    "alias": "SIMULATED recovery",
                    "sequence": [
                        {
                            "event": "alarmmesh_simulated_script",
                            "event_data": {"name": "recovery"},
                        }
                    ],
                }
            }
        },
    )
    entry = await new_entry(hass)
    await group_actions(hass, entry, [A], start=())
    await source(hass, entry, A, "on")
    assert not events
    await source(hass, entry, A, "off")
    assert events == ["recovery"]


async def test_selftest_identity_change_is_unknown_and_never_adopted(
    hass, catalog_devices
):
    add, _ = catalog_devices
    d = add_test_device(add)

    async def press(_call):
        pass

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [d["source"]])
    tests = entry.runtime_data.panel.selftests
    await tests.start(
        d["source"],
        tests.resolve(d["source"])["identity"],
        True,
        request_id=uuid4().hex,
    )
    er.async_get(hass).async_remove(d["test_target"])
    await settle(hass, entry)
    assert tests.record["status"] == "outcome_unknown"
    assert not tests.describe(d["source"])["available"]


async def test_zha_builtin_button_needs_no_invented_result_entity(
    hass, catalog_devices
):
    add, calls = catalog_devices
    d = add_test_device(add, "lumi.sensor_smoke.acn03", "LUMI", "zha")
    er.async_get(hass).async_remove(d["flag"])
    hass.states.async_remove(d["flag"])

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [d["source"]])
    tests = entry.runtime_data.panel.selftests
    control = tests.resolve(d["source"])
    assert control is not None and not control["flags"] and not control["results"]
    assert not control["has_explicit_result"]
    await tests.start(d["source"], control["identity"], True, request_id=uuid4().hex)
    assert calls == [{"entity_id": d["test_target"]}]
    assert tests.record["status"] == "request_sent"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await settle(hass, entry)
    assert tests.record["status"] == "outcome_unknown"


@pytest.mark.parametrize("loss", ["unavailable", "removed"])
async def test_real_smoke_during_selftest_survives_loss_of_test_control(
    hass, catalog_devices, outputs, loss
):
    add, _ = catalog_devices
    d = add_test_device(add)

    async def press(_call):
        pass

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [d["source"]])
    await notifications(entry)
    tests = entry.runtime_data.panel.selftests
    await tests.start(
        d["source"],
        tests.resolve(d["source"])["identity"],
        True,
        request_id=uuid4().hex,
    )
    hass.states.async_set(d["flag"], "on")
    await settle(hass, entry)
    if loss == "removed":
        er.async_get(hass).async_remove(d["test_target"])
    else:
        hass.states.async_set(d["test_target"], "unavailable")
    await source(hass, entry, d["source"], "on")
    assert d["source"] in entry.runtime_data.panel.linking.active
    assert entry.runtime_data.panel.snapshot()["result"]["smoke"] == "SMOKE_REPORTED"
    assert len(outputs[0]) == 2


@pytest.mark.parametrize("change", ["expired", "other_test", "manual_sounder"])
async def test_queued_selftest_rechecks_deadline_and_conflicts(
    hass, catalog_devices, change
):
    add, calls = catalog_devices
    d = add_test_device(add)

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [d["source"]])
    panel = entry.runtime_data.panel
    for _ in range(8):
        await panel.linking._semaphore.acquire()
    task = asyncio.create_task(
        panel.selftests.start(
            d["source"],
            panel.selftests.resolve(d["source"])["identity"],
            True,
            request_id=uuid4().hex,
        )
    )
    await hass.async_block_till_done()
    assert panel.selftests.record["status"] == "sending"
    if change == "expired":
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    elif change == "other_test":
        hass.states.async_set(d["flag"], "on")
    else:
        control = panel.linking.capabilities.describe(d["source"])["controls"][0]
        hass.states.async_set(control["target"], "smoke_siren")
    await hass.async_block_till_done()
    panel.linking._semaphore.release()
    try:
        result = await task
        assert not calls
        assert result["status"] == "outcome_unknown"
    finally:
        for _ in range(7):
            panel.linking._semaphore.release()
