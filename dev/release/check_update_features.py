"""Published-catalog upgrade and current-setting restart checks; mock outputs only."""

import json
from copy import deepcopy

from homeassistant.config_entries import ConfigEntryState


async def settle(hass, entry):
    for _ in range(12):
        await hass.async_block_till_done()
        panel = entry.runtime_data.panel
        tasks = [t for t in (panel.linking._task, panel.effects._task) if t is not None]
        if not tasks:
            return
        for task in tasks:
            await task
    raise AssertionError("Mock outputs did not settle")


async def check_features(hass, entry, phase, root, helper, require, checks):
    from custom_components.alarmmesh.capabilities import Capabilities

    panel = entry.runtime_data.panel
    fixtures = hass.data["alarmmesh_simulation"]["fixtures"]
    a, b = (fixtures[n]["source"] for n in "ab")
    saved_path = root / "published-groups.json"
    if phase == "seed":
        controls = Capabilities(hass).describe(a)["controls"]
        require(len(controls) == 1, "Mock PLUS control missing")
        binding = {
            k: controls[0][k] for k in ("source", "target", "profile", "identity")
        }
        await panel.groups.async_mutate(
            {
                "operation": "create",
                "revision": panel.groups.revision,
                "name": "SIMULATION saved explicit linking",
                "members": [a, b],
                "linking": {"enabled": True, "bindings": [binding]},
                "confirmed": True,
            },
            entry.runtime_data.source_entity_ids,
        )
        # A is already locally alarming, so this stored target is never commanded.
        saved_path.write_text(
            json.dumps(panel.groups.groups, indent=2), encoding="utf-8"
        )
        checks.append("published_groups_names_and_explicit_mapping_seeded_via_api")
        return
    if phase == "restore":
        require(
            panel.groups.groups == json.loads(saved_path.read_text()),
            "Published group restore changed",
        )
        checks.append("stopped_catalog_snapshot_restores_explicit_group_configuration")
        return

    from custom_components.alarmmesh.automation import script_target

    if phase in {"fresh", "update"}:
        require(
            not panel.effects.settings.value["enabled"],
            "Notifications enabled without choice",
        )
        require(panel.selftests.record is None, "Unexpected restored device test")
        require(
            all(
                not g.get("actions", {}).get("enabled", False)
                for g in panel.groups.groups
            ),
            "Scripts auto-enabled",
        )
        checks.append("new_notifications_actions_and_tests_default_off")
        if phase == "fresh":
            require(not panel.groups.groups, "Fresh package reused groups")
            return
        require(
            panel.groups.groups == json.loads(saved_path.read_text()),
            "Upgrade changed explicit catalog choices",
        )
        checks.append("catalog_to_current_preserves_group_id_name_members_and_linking")
        group = panel.groups.groups[0]

        def binding(phase):
            script = script_target(hass, "script.incident_simulated_" + phase)
            require(script is not None, "Actual event-only script missing")
            return {k: script[k] for k in ("entity_id", "identity")}

        await panel.groups.async_mutate(
            {
                "operation": "update",
                "group_id": group["id"],
                "revision": panel.groups.revision,
                "name": group["name"],
                "members": group["members"],
                "origins": [b],
                "linking": group["linking"],
                "confirmed": True,
                "actions": {
                    "enabled": True,
                    "start": [binding("start"), binding("recovery")],
                    "recovery": [binding("recovery")],
                },
            },
            entry.runtime_data.source_entity_ids,
        )
        await panel.effects.settings.save(
            {
                "enabled": True,
                "recovery": True,
                "recipients": [
                    {"service": "mobile_app_simulated_phone_" + n, "enabled": True}
                    for n in "ab"
                ],
            },
            panel.effects.settings.revision,
            True,
        )
        checkpoint = json.loads((root / "checkpoint.json").read_text())
        checkpoint.update(
            smoke="off",
            availability="complete",
            groups=deepcopy(panel.groups.groups),
            notifications=deepcopy(panel.effects.settings.value),
        )
        (root / "features-checkpoint.json").write_text(
            json.dumps(checkpoint, indent=2), encoding="utf-8"
        )
        checks.append(
            "current_receivers_and_scripts_explicitly_configured_via_supported_stores"
        )
        return

    checkpoint = json.loads((root / "features-checkpoint.json").read_text())
    require(
        panel.groups.groups == checkpoint["groups"],
        "Current groups/scripts changed after new process",
    )
    require(
        panel.effects.settings.value == checkpoint["notifications"],
        "Receivers changed after new process",
    )
    require(not panel.effects.episodes, "Idle restart invented an incident")
    checks.append(
        "real_process_restart_preserves_origins_linking_receivers_and_script_order"
    )
    await helper("mvp_b_smoke", True)
    await settle(hass, entry)
    episode = panel.effects.episodes["notifications"]
    require(
        len(episode["receipts"]) == 2
        and all(r["status"] == "accepted" for r in episode["receipts"].values()),
        "Mock phone delivery requests",
    )
    group_episode = panel.effects.episodes[panel.groups.groups[0]["id"]]
    require(
        len(group_episode["receipts"]) == 2
        and all(
            r["kind"] == "script" and r["status"] == "accepted"
            for r in group_episode["receipts"].values()
        ),
        "Event-only start script not requested",
    )
    requests = hass.states.get("sensor.incident_simulated_requests").attributes[
        "requests"
    ]
    require(
        [r["target"] for r in requests if r["kind"] == "script"]
        == ["start", "recovery"],
        "Event-only script start order changed",
    )
    before = hass.states.get("sensor.incident_simulated_requests").state
    retired = panel
    require(
        await hass.config_entries.async_reload(entry.entry_id),
        "Current feature reload failed",
    )
    await settle(hass, entry)
    require(
        hass.states.get("sensor.incident_simulated_requests").state == before,
        "Reload replayed mock notifications/scripts",
    )
    require(
        retired.effects.closed and retired.selftests.closed,
        "Retired output handlers live",
    )
    await helper("mvp_b_smoke", False)
    await settle(hass, entry)
    require(
        entry.runtime_data.panel.effects.episodes["notifications"]["phase"]
        == "recovery",
        "Explicit source recovery missing",
    )
    checks.append("mock_incident_reload_without_replay_and_explicit_recovery")


async def check_corrupt_storage(hass, entry, require, checks):
    panel = entry.runtime_data.panel
    require(
        not panel.groups.groups and not panel.effects.settings.value["enabled"],
        "Re-add did not reset entry-owned choices",
    )
    store = panel.groups.store
    await store.async_save({"schema": 999, "revision": 0, "groups": []})
    before = hass.states.get("sensor.incident_simulated_requests").state
    await hass.config_entries.async_reload(entry.entry_id)
    require(
        entry.state is ConfigEntryState.SETUP_ERROR,
        "Corrupt storage was treated as usable",
    )
    require(
        hass.states.get("sensor.incident_simulated_requests").state == before,
        "Corruption dispatched mock output",
    )
    await store.async_remove()  # Only this disposable entry, through HA's Store API.
    require(
        await hass.config_entries.async_reload(entry.entry_id),
        "Recovery after corrupt test store failed",
    )
    require(
        not entry.runtime_data.panel.effects.settings.value["enabled"],
        "Storage recovery enabled notifications",
    )
    checks.append(
        "missing_and_corrupt_entry_store_fail_closed_then_supported_api_recovery"
    )
