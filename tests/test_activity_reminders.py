"""Real HA storage, clock and registry; only explicit mock phone outputs."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import outputs as outputs
from test_maintenance_delivery import prepare
from test_preview_diagnostics import prepared

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.activity import LIMIT, PENDING_LIMIT, Activity
from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.diagnostics import support_report
from custom_components.alarmmesh.groups import GroupError
from custom_components.alarmmesh.reminders import Reminders, due_at


async def settle(hass, entry):
    for _ in range(30):
        await hass.async_block_till_done()
        p = entry.runtime_data.panel
        tasks = [
            p.activity.task,
            p.reminders.task,
            p.maintenance.task,
            p.effects._task,
            p.linking._task,
        ]
        if not any(tasks):
            return
        for task in tasks:
            if task is not None:
                await task
    pytest.fail("Owned workers did not settle")


async def schedule(hass, entry, source, day, **changes):
    r = entry.runtime_data.panel.reminders
    value = {
        "identity": r.identity(source),
        "enabled": True,
        "date": day,
        "interval": 0,
        "recipient": "mobile_app_simulation_a",
        **changes,
    }
    await r.save("save", source, r.revision, value, True)
    await settle(hass, entry)
    return r


async def test_activity_baseline_no_old_receipt_import_and_dedup(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    await settle(hass, entry)
    assert not p.activity.rows
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    smoke = [r for r in p.activity.rows if r["result"] == "SMOKE_REPORTED"]
    assert len(smoke) == 1 and smoke[0]["correlation"]
    for _ in range(5):
        p.hub.publish()
    await settle(hass, entry)
    assert len([r for r in p.activity.rows if r["result"] == "SMOKE_REPORTED"]) == 1
    hass.states.async_set(d["source"], "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert not any(r["result"] == "NO_SMOKE_REPORTED" for r in p.activity.rows)
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    release = next(r for r in p.activity.rows if r["result"] == "NO_SMOKE_REPORTED")
    assert release["correlation"] == smoke[0]["correlation"]
    before = deepcopy(p.activity.rows)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert entry.runtime_data.panel.activity.rows == before
    assert not outputs[0]


async def test_request_transitions_are_correlated_and_not_physical_proof(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    requests = [r for r in p.activity.rows if r["kind"] == "sounder"]
    assert requests and requests[0]["result"] == "sending"
    assert (
        requests[-1]["result"] == "sent"
        and requests[0]["correlation"] == requests[-1]["correlation"]
    )
    assert all(group in r["groups"] and r["target"] == b["target"] for r in requests)
    assert len(calls) == 1
    p.selftests.record = {
        "request_id": "a" * 32,
        "status": "test_active",
        "source": b["source"],
    }
    p.hub.publish()
    p.selftests.record = {**p.selftests.record, "status": "device_success"}
    p.hub.publish()
    await settle(hass, entry)
    rows = [r for r in p.activity.rows if r["kind"] == "selftest"]
    assert [r["result"] for r in rows] == ["test_active", "device_success"]
    assert {r["correlation"] for r in rows} == {"a" * 32}
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    # This record is a journal-only fixture, never a device self-test invocation.
    p.selftests.record = None


async def test_passive_maintenance_history_without_phone_enabled(
    hass, catalog_devices, outputs
):
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert any(
        r["kind"] == "battery" and r["result"] == "problem" for r in p.activity.rows
    )
    hass.states.async_set(d["battery"], "unknown", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert not any(
        r["kind"] == "battery" and r["result"] == "recovered" for r in p.activity.rows
    )
    hass.states.async_set(d["battery"], "70", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    assert any(
        r["kind"] == "battery" and r["result"] == "recovered" for r in p.activity.rows
    )
    assert not outputs[0] and not p.maintenance.value["enabled"]


async def test_activity_queue_retention_and_storage_failure_do_not_block_smoke(
    hass, catalog_devices, freezer
):
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    a = p.activity
    with patch.object(
        a.store, "async_save", AsyncMock(side_effect=OSError("private storage detail"))
    ):
        for _ in range(PENDING_LIMIT + 5):
            a.record("configuration", "configuration", "changed")
        assert len(a.pending) == PENDING_LIMIT and a.incomplete
        await settle(hass, entry)
    assert a.damaged and len(a.rows) == PENDING_LIMIT
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    for _ in range(9):
        for _ in range(125):
            a.record("configuration", "configuration", "changed")
        await settle(hass, entry)
    assert len(a.rows) == LIMIT
    freezer.tick(timedelta(days=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle(hass, entry)
    assert not a.snapshot()["events"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert a.closed and a.task is None and a.cancel_timer is None


async def test_corrupt_journal_is_not_overwritten(hass, catalog_devices):
    entry, _ = await prepare(hass, catalog_devices)
    fresh = Activity(hass, entry, lambda: None)
    with (
        patch.object(
            fresh.store, "async_load", AsyncMock(return_value={"secret": "invalid"})
        ),
        patch.object(fresh.store, "async_save", AsyncMock()) as save,
    ):
        await fresh.load()
        fresh.record("configuration", "configuration", "changed")
        if fresh.task:
            await fresh.task
        assert fresh.incomplete and fresh.rows and not save.called
    await fresh.close()


async def test_expired_loaded_history_is_removed_from_storage_without_new_events(
    hass, catalog_devices
):
    entry, _ = await prepare(hass, catalog_devices)
    a = entry.runtime_data.panel.activity
    a.record("configuration", "configuration", "changed")
    await settle(hass, entry)
    expired = deepcopy(a.rows[0])
    expired["observed_at"] = (dt_util.utcnow() - timedelta(days=31)).isoformat()
    fresh = Activity(hass, entry, lambda: None)
    with (
        patch.object(
            fresh.store,
            "async_load",
            AsyncMock(
                return_value={"schema": 1, "incomplete": False, "events": [expired]}
            ),
        ),
        patch.object(fresh.store, "async_save", AsyncMock()) as save,
    ):
        await fresh.load()
        assert fresh.rows == [] and not fresh.incomplete
        save.assert_awaited_once_with({"schema": 1, "incomplete": False, "events": []})
    await fresh.close()


@pytest.mark.parametrize("day,utc_hour", [("2026-03-29", 7), ("2026-10-25", 8)])
def test_calendar_date_uses_ha_timezone_across_dst(day, utc_hour):
    due = due_at(day, "Europe/Brussels")
    assert due.hour == utc_hour and due.date().isoformat() == day


async def test_reminder_defaults_and_exact_confirmation(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T08:00:00Z")
    entry, d = await prepare(hass, catalog_devices)
    r = entry.runtime_data.panel.reminders
    assert r.items == {} and not outputs[0]
    with pytest.raises(AutomationError, match="confirmation"):
        await r.save("save", d["source"], 0, {}, False)
    with pytest.raises(AutomationError, match="conflict"):
        await r.save("save", d["source"], False, {}, True)
    with pytest.raises(AutomationError, match="invalid_reminder"):
        await schedule(hass, entry, d["source"], "2026-11-16", interval=1)
    assert not r.items and not outputs[0]


async def test_due_once_snooze_handle_repeat_never_test_success(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T06:59:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    before = deepcopy(p.selftests.record)
    r = await schedule(hass, entry, d["source"], "2026-11-15", interval=30)
    assert r.cancel_timer is not None and not outputs[0]
    freezer.move_to("2026-11-15T08:00:00Z")
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle(hass, entry)
    assert len(outputs[0]) == 1 and r.items[d["source"]]["status"] == "accepted"
    for _ in range(4):
        r.changed()
    await settle(hass, entry)
    assert len(outputs[0]) == 1
    await r.save("snooze", d["source"], r.revision, {"date": "2026-11-16"}, True)
    await settle(hass, entry)
    assert r.items[d["source"]]["status"] == "pending"
    await r.save("handle", d["source"], r.revision, {}, True)
    await settle(hass, entry)
    assert r.items[d["source"]]["date"] == "2026-12-15"
    assert p.selftests.record == before and len(outputs[0]) == 1
    old = r
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert old.closed and not old.cancel_timer and old.task is None
    assert len(outputs[0]) == 1


async def test_reminder_restart_suppresses_overdue_and_uncertain_delivery(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T08:00:00Z")
    entry, d = await prepare(hass, catalog_devices)
    r = await schedule(hass, entry, d["source"], "2026-11-16")
    await r.pause()
    freezer.move_to("2026-11-17T10:00:00Z")
    fresh = Reminders(
        hass,
        entry,
        entry.runtime_data.panel.linking,
        lambda: None,
        entry.runtime_data.panel.activity,
    )
    await fresh.load()
    fresh.start()
    if fresh.task:
        await fresh.task
    assert fresh.items[d["source"]]["status"] == "startup_suppressed" and not outputs[0]
    await fresh.close()


async def test_saving_same_due_reminder_does_not_retry(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T12:00:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    r = await schedule(hass, entry, d["source"], "2026-11-15")
    assert len(outputs[0]) == 1
    first = r.items[d["source"]]["cycle"]
    await schedule(hass, entry, d["source"], "2026-11-15", interval=90)
    assert len(outputs[0]) == 1 and r.items[d["source"]]["cycle"] == first


async def test_smoke_priority_missing_identity_and_failed_recipient_no_retry(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T10:00:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    r = await schedule(hass, entry, d["source"], "2026-11-15")
    assert not outputs[0] and r.items[d["source"]]["status"] == "pending"
    hass.states.async_set(d["source"], "unknown", {"device_class": "smoke"})
    await settle(hass, entry)
    assert not outputs[0]
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(outputs[0]) == 1
    outputs[1].add("mobile_app_simulation_b")
    await schedule(
        hass, entry, d["source"], "2026-11-15", recipient="mobile_app_simulation_b"
    )
    assert r.items[d["source"]]["status"] == "failed"
    r.changed()
    await settle(hass, entry)
    assert len(outputs[0]) == 2
    hass.services.async_remove("notify", "mobile_app_simulation_b")
    await settle(hass, entry)
    assert r.snapshot()["items"][0]["attention"] == "recipient_unavailable"
    entity = er.async_get(hass).async_get(d["source"])
    er.async_get(hass).async_update_entity(
        d["source"], new_unique_id=entity.unique_id + "_replacement"
    )
    await settle(hass, entry)
    assert r.snapshot()["items"][0]["attention"] == "reminder_identity_changed"
    assert len(outputs[0]) == 2


async def test_copy_never_inherits_authority_or_changes_original(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    before = deepcopy(p.groups.groups)
    await p.groups.async_mutate(
        {
            "operation": "copy",
            "revision": p.groups.revision,
            "group_id": group,
            "name": "SIMULATION copy",
            "members": [a["source"], b["source"]],
            "origins": [a["source"]],
            "linking": {"enabled": True, "bindings": before[0]["linking"]["bindings"]},
        },
        p.runtime.source_entity_ids,
    )
    assert p.groups.groups[0] == before[0]
    copy = p.groups.groups[1]
    assert copy["id"] != group and copy["origins"] == [a["source"]]
    assert copy["linking"] == {"enabled": False, "bindings": []}
    assert copy.get("actions", {"enabled": False, "start": [], "recovery": []}) == {
        "enabled": False,
        "start": [],
        "recovery": [],
    }
    with pytest.raises(GroupError, match="conflict"):
        await p.groups.async_mutate(
            {"operation": "copy", "revision": 0, "group_id": group},
            p.runtime.source_entity_ids,
        )
    assert not calls and not outputs[0]


async def test_report_does_not_export_activity_or_reminder_private_payloads(
    hass, catalog_devices
):
    entry, _ = await prepare(hass, catalog_devices)
    snapshot = entry.runtime_data.panel.snapshot()
    secret = "PRIVATE_SIMULATED_PERSON_LOCATION_MESSAGE"
    snapshot["activity"] = {"incomplete": True, "events": [{"private": secret}]}
    snapshot["reminders"] = {
        "error": None,
        "items": [
            {
                "source": secret,
                "recipient": secret,
                "attention": "recipient_unavailable",
            }
        ],
    }
    import json

    report = support_report(snapshot, "0.1.0-beta.6", "2026.11.1")
    assert secret not in json.dumps(report)
    assert report["counts"]["activity_events"] == report["counts"]["reminders"] == 1


@pytest.mark.parametrize("command", ["alarmmesh/reminder", "alarmmesh/group_copy"])
async def test_new_mutations_are_admin_only(
    hass, catalog_devices, hass_ws_client, command
):
    entry, d = await prepare(hass, catalog_devices)
    user = await hass.auth.async_create_user(
        "SIMULATED reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    payload = {"id": 1, "type": command, "revision": 0, "confirmed": True}
    if command.endswith("reminder"):
        payload.update(operation="delete", source=d["source"], value={})
    else:
        payload.update(
            group_id="not-real", name="SIMULATION copy", members=[], origins=[]
        )
    await client.send_json(payload)
    response = await client.receive_json()
    assert response["error"]["code"] == "unauthorized"
    assert (
        entry.runtime_data.panel.reminders.revision
        == entry.runtime_data.panel.groups.revision
        == 0
    )


async def test_reminder_corruption_and_intent_failure_are_fail_closed(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T12:00:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    r = await schedule(hass, entry, d["source"], "2026-11-16")
    with patch.object(
        r.store, "async_save", AsyncMock(side_effect=OSError("private fixture"))
    ):
        freezer.move_to("2026-11-16T12:00:00Z")
        async_fire_time_changed(hass, dt_util.utcnow())
        await settle(hass, entry)
    assert r.fault == "reminder_storage_error" and not outputs[0]
    fresh = Reminders(hass, entry, p.linking, lambda: None, p.activity)
    with (
        patch.object(fresh.store, "async_load", AsyncMock(return_value={"schema": 2})),
        patch.object(fresh.store, "async_save", AsyncMock()) as save,
    ):
        await fresh.load()
        fresh.start()
        if fresh.task:
            await fresh.task
        assert fresh.fault == "reminder_storage_error" and not save.called
    await fresh.close()


async def test_cancel_inflight_reminder_is_unknown_and_never_retried(
    hass, catalog_devices, outputs, freezer
):
    import asyncio

    freezer.move_to("2026-11-15T12:00:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    started = asyncio.Event()

    async def blocked(*_args):
        started.set()
        await asyncio.Event().wait()

    r = p.reminders
    with patch(
        "custom_components.alarmmesh.reminders.send_notification", side_effect=blocked
    ):
        value = {
            "identity": r.identity(d["source"]),
            "enabled": True,
            "date": "2026-11-15",
            "interval": 0,
            "recipient": "mobile_app_simulation_a",
        }
        await r.save("save", d["source"], r.revision, value, True)
        await started.wait()
        await r.pause()
    assert r.items[d["source"]]["status"] == "outcome_unknown" and r.task is None
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert (
        entry.runtime_data.panel.reminders.items[d["source"]]["status"]
        == "outcome_unknown"
        and not outputs[0]
    )


async def test_partial_unload_pause_cancels_journal_work_and_marks_observation_gap(
    hass, catalog_devices
):
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert p.activity.cancel_timer is not None
    await p.async_pause()
    assert p.activity.cancel_timer is None and p.activity.task is None
    before = deepcopy(p.activity.rows)
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert p.activity.incomplete and p.activity.rows == before
    assert p.activity.cancel_timer is None and p.activity.task is None


async def test_reminder_timezone_change_reschedules_local_calendar(
    hass, catalog_devices, outputs, freezer
):
    freezer.move_to("2026-11-15T07:30:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    entry, d = await prepare(hass, catalog_devices)
    r = await schedule(hass, entry, d["source"], "2026-11-15")
    assert not outputs[0] and r.cancel_timer is not None
    await hass.config.async_update(time_zone="UTC")
    await settle(hass, entry)
    freezer.move_to("2026-11-15T08:01:00Z")
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle(hass, entry)
    assert not outputs[0]
    freezer.move_to("2026-11-15T09:00:00Z")
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle(hass, entry)
    assert len(outputs[0]) == 1
    await r.pause()
    assert r.config_unsubscribe is None and r.cancel_timer is None


async def test_new_battery_problem_does_not_keep_cleared_previous_cause(
    hass, catalog_devices
):
    entry, d = await prepare(hass, catalog_devices)
    low = d["register"]("binary_sensor", "battery_low", "off", {})
    p = entry.runtime_data.panel
    hass.states.async_set(d["battery"], "8", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    hass.states.async_set(d["battery"], "80", {"unit_of_measurement": "%"})
    await settle(hass, entry)
    hass.states.async_set(d["battery"], "unknown", {"unit_of_measurement": "%"})
    hass.states.async_set(low, "on")
    await settle(hass, entry)
    hass.states.async_set(low, "off")
    await settle(hass, entry)
    assert [r["result"] for r in p.activity.rows if r["kind"] == "battery"] == [
        "problem",
        "recovered",
        "problem",
        "recovered",
    ]
