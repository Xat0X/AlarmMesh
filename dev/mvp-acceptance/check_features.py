"""Additional scenarios in the existing image checker; no physical endpoints."""

from copy import deepcopy
from uuid import uuid4

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.alarmmesh.automation import script_target
from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS


async def check_features(hass, entry, registry, fixtures, ws_request, require, passed):
    a, b = (fixtures[n]["source"] for n in "ab")
    for name in "ab":
        hass.states.async_set(f"input_boolean.catalog_{name}_smoke", "off")
    hass.states.async_set("input_boolean.catalog_test", "off")
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: [a, b]}
    )
    require(await hass.config_entries.async_setup(entry.entry_id), "Feature setup")

    async def settle():
        for _ in range(12):
            await hass.async_block_till_done()
            panel = entry.runtime_data.panel
            tasks = [
                t
                for t in (
                    panel.linking._task,
                    panel.effects._task,
                    panel.maintenance.task,
                    panel.reminders.task,
                    panel.activity.task,
                    *panel.selftests.tasks,
                )
                if t is not None
            ]
            if not tasks:
                return
            for task in tasks:
                await task
        raise AssertionError("Feature tasks did not settle")

    calls, actions = [], []

    async def notify(call):
        calls.append((call.service, dict(call.data)))
        if call.service.endswith("_b"):
            raise HomeAssistantError("Simulated recipient failure")

    for name in "ab":
        hass.services.async_register("notify", "mobile_app_simulated_" + name, notify)

    def observe(event):
        actions.append(event.data["phase"])

    unsubscribe = hass.bus.async_listen("alarmmesh_simulated_script", observe)
    try:
        require(
            await async_setup_component(
                hass,
                "script",
                {
                    "script": {
                        "alarmmesh_simulated_start": {
                            "alias": "SIMULATED start",
                            "sequence": [
                                {
                                    "event": "alarmmesh_simulated_script",
                                    "event_data": {"phase": "start"},
                                }
                            ],
                        },
                        "alarmmesh_simulated_recovery": {
                            "alias": "SIMULATED recovery",
                            "sequence": [
                                {
                                    "event": "alarmmesh_simulated_script",
                                    "event_data": {"phase": "recovery"},
                                }
                            ],
                        },
                    }
                },
            ),
            "Actual script integration setup",
        )
        await settle()
        panel = entry.runtime_data.panel
        snapshot = panel.snapshot()
        require(
            [s["id"] for s in snapshot["review"]["steps"]]
            == [
                "sources",
                "rooms",
                "groups",
                "sounders",
                "notifications",
                "scripts",
                "check",
            ],
            "Seven-step current configuration guide missing",
        )
        require(
            all(
                s["status"] == "disabled"
                for s in snapshot["review"]["steps"]
                if s["id"] in {"notifications", "scripts"}
            ),
            "Disabled optional functions misreported",
        )
        result = snapshot["result"]
        hass.states.async_set("input_boolean.catalog_battery_low", "on")
        await settle()
        snapshot = panel.snapshot()
        require(
            next(s for s in snapshot["sources"] if s["entity_id"] == b)["capability"][
                "details"
            ]["maintenance"]["battery_percent"]
            == 14.0
            and snapshot["result"] == result,
            "Maintenance display changed smoke semantics or lost bound battery",
        )
        hass.states.async_set("input_boolean.catalog_battery_low", "off")
        await settle()
        battery = hass.states.get(fixtures["b"]["battery"])
        hass.states.async_set(battery.entity_id, "95", {"unit_of_measurement": "V"})
        await settle()
        require(
            next(s for s in panel.snapshot()["sources"] if s["entity_id"] == b)[
                "capability"
            ]["details"]["maintenance"]["battery_percent"]
            is None,
            "Contradictory battery unit presented as percentage",
        )
        hass.states.async_set(
            battery.entity_id, battery.state, dict(battery.attributes)
        )
        old_class = registry.async_get(a).device_class
        registry.async_update_entity(a, device_class="opening")
        await settle()
        require(
            next(
                s for s in panel.snapshot()["review"]["steps"] if s["id"] == "sources"
            )["status"]
            == "needs_attention"
            and panel.snapshot()["result"] == result,
            "Changed source identity: incorrect guide or altered smoke result",
        )
        registry.async_update_entity(a, device_class=old_class)
        await settle()
        passed("derived_setup_and_passive_maintenance")

        def script(name):
            target = script_target(hass, "script.alarmmesh_simulated_" + name)
            require(target is not None, "Actual script registry target missing")
            return {k: target[k] for k in ("entity_id", "identity")}

        require(
            not calls and not actions and not panel.effects.settings.value["enabled"],
            "Default-on automation",
        )
        await ws_request(
            {
                "id": 100,
                "type": "alarmmesh/settings",
                "revision": 0,
                "confirmed": True,
                "notifications": {
                    "enabled": True,
                    "recovery": True,
                    "recipients": [
                        {"service": "mobile_app_simulated_" + n, "enabled": True}
                        for n in "ab"
                    ],
                },
            }
        )
        await ws_request(
            {
                "id": 101,
                "type": "alarmmesh/group",
                "operation": "create",
                "revision": panel.groups.revision,
                "name": "SIMULATED incident actions",
                "members": [a, b],
                "origins": [a],
                "confirmed": True,
                "actions": {
                    "enabled": True,
                    "start": [script("start")],
                    "recovery": [script("recovery")],
                },
            }
        )
        await settle()
        require(not calls and not actions, "Configuration sent an unsolicited action")
        passed("incident_settings_and_real_script_api")

        hass.states.async_set("input_boolean.catalog_a_smoke", "on")
        await settle()
        require(len(calls) == 2 and actions == ["start"], "Initial incident delivery")
        panel.linking.changed()
        await settle()
        require(len(calls) == 2 and actions == ["start"], "Duplicate event replayed")
        hass.states.async_set("input_boolean.catalog_b_unreachable", "on")
        hass.states.async_set("input_boolean.catalog_a_smoke", "off")
        await settle()
        require(
            len(calls) == 2 and actions == ["start", "recovery"],
            "Group recovery or false global recovery",
        )
        hass.states.async_set("input_boolean.catalog_b_unreachable", "off")
        await settle()
        require(len(calls) == 4, "Confirmed notification recovery")
        require(
            "/alarmmesh?incident=" in calls[0][1]["data"]["url"],
            "Incident deep link missing",
        )
        passed("incident_delivery_failure_and_explicit_recovery")

        hass.states.async_set("input_boolean.catalog_a_smoke", "on")
        hass.states.async_set("input_boolean.catalog_b_smoke", "on")
        await settle()
        before = (len(calls), list(actions))
        retired = panel
        require(
            await hass.config_entries.async_reload(entry.entry_id), "Feature reload"
        )
        await settle()
        require((len(calls), actions) == before, "Receipts replayed on reload")
        retired.effects.changed()
        require(
            retired.effects.closed and retired.linking._closed, "Retired feature worker"
        )
        hass.states.async_set("input_boolean.catalog_b_smoke", "off")
        hass.states.async_set("input_boolean.catalog_a_smoke", "off")
        await settle()
        passed("incident_receipts_reload_and_retired_workers")

        panel = entry.runtime_data.panel
        source = registry.async_get(a)
        group_id = panel.groups.groups[-1]["id"]
        before = (
            len(calls),
            list(actions),
            deepcopy(panel.linking.active),
            deepcopy(panel.linking.attempted),
            deepcopy(panel.effects.episodes),
        )
        example = await ws_request(
            {"id": 110, "type": "alarmmesh/preview", "group_id": group_id, "source": a}
        )
        diagnosis = await ws_request({"id": 111, "type": "alarmmesh/diagnostics"})
        require(
            example["readonly"] and not example["physical_confirmed"],
            "Example could execute",
        )
        require(
            before
            == (
                len(calls),
                actions,
                panel.linking.active,
                panel.linking.attempted,
                panel.effects.episodes,
            ),
            "Read-only example altered execution",
        )
        import json

        serialized = json.dumps(diagnosis)
        require(
            a not in serialized
            and b not in serialized
            and "mobile_app_simulated_" not in serialized
            and diagnosis["versions"]["home_assistant"],
            "Support report leaked live identifiers",
        )
        passed("readonly_action_example_and_anonymized_diagnosis")

        maintenance = panel.maintenance
        require(not maintenance.value["enabled"], "Maintenance default enabled")
        settings = {
            **deepcopy(maintenance.value),
            "enabled": True,
            "recovery": True,
            "recipients": [
                {"service": "mobile_app_simulated_" + n, "enabled": True} for n in "ab"
            ],
        }
        await ws_request(
            {
                "id": 112,
                "type": "alarmmesh/maintenance_settings",
                "revision": maintenance.revision,
                "settings": settings,
                "confirmed": True,
            }
        )
        await settle()
        before_calls = len(calls)
        hass.states.async_set("input_boolean.catalog_battery_low", "on")
        await settle()
        require(
            len(calls) == before_calls + 2, "Maintenance delivery or isolation missing"
        )
        maintenance.changed()
        await settle()
        require(len(calls) == before_calls + 2, "Maintenance duplicate event replay")
        require(
            await hass.config_entries.async_reload(entry.entry_id), "Maintenance reload"
        )
        await settle()
        panel = entry.runtime_data.panel
        maintenance = panel.maintenance
        require(len(calls) == before_calls + 2, "Maintenance replay after load")
        hass.states.async_set("input_boolean.catalog_battery_low", "off")
        await settle()
        require(
            len(calls) == before_calls + 3,
            "Only accepted recipient may receive maintenance recovery",
        )
        await ws_request(
            {
                "id": 113,
                "type": "alarmmesh/maintenance_settings",
                "revision": maintenance.revision,
                "settings": {**settings, "enabled": False},
                "confirmed": False,
            }
        )
        await settle()
        require(
            maintenance.cancel_timer is None and maintenance.task is None,
            "Disabled maintenance retained work",
        )
        passed("maintenance_default_off_dedup_recovery_reload_failure_isolation")

        button = registry.async_get_or_create(
            "button",
            "mqtt",
            "sim_a_trigger_selftest_zigbee2mqtt",
            config_entry=next(
                e for e in hass.config_entries.async_entries("alarmmesh_simulation")
            ),
            device_id=source.device_id,
            suggested_object_id="simulated_builtin_test",
        )
        hass.states.async_set(button.entity_id, "unknown")
        test_calls = []

        async def press(call):
            require(
                call.data == {"entity_id": button.entity_id},
                "Unexpected self-test payload",
            )
            test_calls.append(call.data["entity_id"])
            hass.states.async_set("input_boolean.catalog_test", "on")

        hass.services.async_register("button", "press", press)
        await settle()
        control = panel.selftests.resolve(a)
        require(control is not None, "Reviewed self-test missing")
        before = (len(calls), list(actions))
        await ws_request(
            {
                "id": 114,
                "type": "alarmmesh/test",
                "kind": "selftest",
                "target": a,
                "identity": control["identity"],
                "confirmed": True,
                "request_id": uuid4().hex,
            }
        )
        await settle()
        require(
            len(test_calls) == 1 and (len(calls), actions) == before,
            "Self-test became incident",
        )
        require(
            panel.selftests.record["status"] == "test_active", "Test active feedback"
        )
        hass.states.async_set("input_boolean.catalog_a_smoke", "on")
        await settle()
        require(
            hass.states.is_state(a, "on") and a in panel.linking.active,
            "Real smoke hidden by test",
        )
        require(
            len(calls) == before[0] + 2 and len(actions) == len(before[1]) + 1,
            "Smoke delivery suppressed by test",
        )
        panel.selftests._expired(None)
        await settle()
        require(
            panel.selftests.record["status"] == "outcome_unknown",
            "Timeout reported success",
        )
        hass.states.async_set("input_boolean.catalog_a_smoke", "off")
        hass.states.async_set("input_boolean.catalog_test", "off")
        await settle()
        history = panel.activity.snapshot()["events"]
        require(
            any(
                r["kind"] == "selftest" and r["result"] == "outcome_unknown"
                for r in history
            ),
            "Observed self-test outcome missing",
        )
        require(
            any(
                r["kind"] == "source" and r["result"] == "SMOKE_REPORTED"
                for r in history
            ),
            "Observed smoke transition missing",
        )
        original = deepcopy(panel.groups.groups)
        group = original[0]
        copy_members = [
            s for s in group["members"] if s in panel.runtime.source_entity_ids
        ]
        copy_origins = [
            s for s in group.get("origins", group["members"]) if s in copy_members
        ]
        await ws_request(
            {
                "id": 115,
                "type": "alarmmesh/group_copy",
                "group_id": group["id"],
                "revision": panel.groups.revision,
                "name": "SIMULATION organizational copy",
                "members": copy_members,
                "origins": copy_origins,
                "confirmed": True,
            }
        )
        await settle()
        copied = panel.groups.groups[-1]
        require(
            panel.groups.groups[:-1] == original
            and copied["members"] == copy_members
            and copied["origins"] == copy_origins
            and copied["linking"] == {"enabled": False, "bindings": []}
            and not copied.get("actions", {}).get("enabled"),
            "Copy inherited authority or changed original",
        )
        passed("observed_activity_and_organizational_copy_without_authority")
        from datetime import timedelta
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        from homeassistant.util import dt as dt_util

        r = panel.reminders
        require(not r.items, "Reminders enabled by upgrade")
        day = (
            dt_util.utcnow()
            .astimezone(ZoneInfo(hass.config.time_zone))
            .date()
            .isoformat()
        )
        value = {
            "identity": r.identity(a),
            "enabled": True,
            "date": day,
            "interval": 0,
            "recipient": "mobile_app_simulated_a",
        }
        before = len(calls)
        with patch(
            "custom_components.alarmmesh.reminders.due_at",
            return_value=dt_util.utcnow() - timedelta(seconds=1),
        ):
            await ws_request(
                {
                    "id": 116,
                    "type": "alarmmesh/reminder",
                    "operation": "save",
                    "source": a,
                    "revision": r.revision,
                    "value": value,
                    "confirmed": True,
                }
            )
            await settle()
            require(
                len(calls) == before + 1 and r.items[a]["status"] == "accepted",
                "Mock reminder request missing",
            )
            await ws_request(
                {
                    "id": 117,
                    "type": "alarmmesh/reminder",
                    "operation": "save",
                    "source": a,
                    "revision": r.revision,
                    "value": value,
                    "confirmed": True,
                }
            )
            await settle()
            require(len(calls) == before + 1, "Same reminder replayed")
        test_before = deepcopy(panel.selftests.record)
        await ws_request(
            {
                "id": 118,
                "type": "alarmmesh/reminder",
                "operation": "handle",
                "source": a,
                "revision": r.revision,
                "value": {},
                "confirmed": True,
            }
        )
        await settle()
        require(
            panel.selftests.record == test_before and r.items[a]["status"] == "handled",
            "Handling reminder changed test truth",
        )
        await ws_request(
            {
                "id": 119,
                "type": "alarmmesh/reminder",
                "operation": "delete",
                "source": a,
                "revision": r.revision,
                "value": {},
                "confirmed": True,
            }
        )
        await settle()
        passed("calendar_reminder_mock_delivery_dedup_handle_no_selftest")
        old = panel
        require(
            await hass.config_entries.async_unload(entry.entry_id), "Feature unload"
        )
        require(
            old.effects.closed and old.selftests.closed and not old.script_unsubscribe,
            "Feature subscription leak",
        )
        require(
            old.activity.closed
            and old.activity.task is None
            and old.activity.cancel_timer is None
            and old.reminders.closed
            and old.reminders.task is None
            and old.reminders.cancel_timer is None,
            "Activity/reminder lifecycle leak",
        )
        passed("selftest_request_real_smoke_and_interruption")
    finally:
        unsubscribe()
