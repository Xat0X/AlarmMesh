"""Read-only analysis and explicit diagnostic allowlists with real HA metadata."""

import json
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import outputs as outputs
from test_incident_features import script
from test_linking_runtime import configure, setup
from test_maintenance_delivery import settle

from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.diagnostics import support_report
from custom_components.alarmmesh.linking import Activation
from custom_components.alarmmesh.preview import group_preview


async def prepared(hass, catalog_devices):
    add, calls = catalog_devices
    a, b = add("HS1SA-E-PLUS", "Heiman"), add("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [a["source"], b["source"]])
    group = await configure(hass, entry, [a["source"], b["source"]], [b])
    return entry, a, b, group, calls


async def test_preview_has_no_output_or_incident_storage_or_test_side_effects(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    before = deepcopy(
        (
            p.linking.active,
            p.linking.previous,
            p.linking.attempted,
            p.linking.records,
            p.effects.episodes,
            p.selftests.record,
            p.selftests.separate_smoke,
            p.groups.groups,
            p.groups.revision,
        )
    )
    with (
        patch.object(type(hass.services), "async_call", AsyncMock()) as invoke,
        patch.object(p.groups.store, "async_save", AsyncMock()) as save,
    ):
        result = group_preview(p, group, a["source"])
        invoke.assert_not_called()
        save.assert_not_called()
    assert (
        result["readonly"]
        and result["targets"][0]["eligible"]
        and not result["physical_confirmed"]
    )
    assert (
        p.linking.active,
        p.linking.previous,
        p.linking.attempted,
        p.linking.records,
        p.effects.episodes,
        p.selftests.record,
        p.selftests.separate_smoke,
        p.groups.groups,
        p.groups.revision,
    ) == before
    assert not calls and not outputs[0]
    binding = p.groups.groups[0]["linking"]["bindings"][0]
    activation = Activation(binding, frozenset({a["source"]}))
    assert p.linking.assess(activation, {a["source"]})[0] is not None
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(calls) == 1 and calls[0][2]["entity_id"] == b["target"]


async def test_preview_blocks_changed_identity_manual_target_and_disabled_group(
    hass, catalog_devices
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    hass.states.async_set(
        b["target"], "smoke_siren", {"options": ["stop", "smoke_siren", "co_siren"]}
    )
    await settle(hass, entry)
    assert (
        group_preview(p, group, a["source"])["targets"][0]["reason"] == "already_active"
    )
    hass.states.async_set(
        b["target"], "stop", {"options": ["stop", "smoke_siren", "co_siren"]}
    )
    er.async_get(hass).async_update_entity(b["target"], new_unique_id="changed-control")
    await settle(hass, entry)
    result = group_preview(p, group, a["source"])
    assert (
        not result["targets"][0]["eligible"]
        and result["targets"][0]["reason"] == "control_missing"
    )
    await p.groups.async_mutate(
        {
            "operation": "update",
            "group_id": group,
            "revision": p.groups.revision,
            "name": "SIMULATED off",
            "members": [a["source"], b["source"]],
            "linking": {
                "enabled": False,
                "bindings": p.groups.groups[0]["linking"]["bindings"],
            },
        },
        p.runtime.source_entity_ids,
    )
    assert group_preview(p, group, a["source"])["targets"][0]["reason"] == "disabled"
    assert not calls


async def test_preview_includes_scripts_order_global_phones_and_recovery_conditions(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    await p.groups.async_mutate(
        {
            "operation": "update",
            "group_id": group,
            "revision": p.groups.revision,
            "name": "SIMULATED scripts",
            "members": [a["source"], b["source"]],
            "origins": [a["source"]],
            "actions": {
                "enabled": True,
                "start": [script(hass, "second"), script(hass, "first")],
                "recovery": [script(hass, "recovery")],
            },
            "confirmed": True,
        },
        p.runtime.source_entity_ids,
    )
    await p.effects.settings.save(
        {
            "enabled": True,
            "recovery": True,
            "recipients": [{"service": "mobile_app_simulation_a", "enabled": True}],
        },
        p.effects.settings.revision,
        True,
    )
    result = group_preview(p, group, a["source"])
    assert [row["target"] for row in result["scripts"]] == [
        "script.simulation_second",
        "script.simulation_first",
        "script.simulation_recovery",
    ]
    assert result["phones"][0]["eligible"] and result["notification_recovery"]
    assert result["recovery_sources"] == [a["source"]]
    assert not group_preview(p, group, b["source"])["scripts"][0]["eligible"]
    assert not calls and not outputs[0]


async def test_existing_incident_receipts_are_shared_with_preview_dedup(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    await p.groups.async_mutate(
        {
            "operation": "update",
            "group_id": group,
            "revision": p.groups.revision,
            "name": "SIMULATED dedup",
            "members": [a["source"], b["source"]],
            "origins": [a["source"]],
            "actions": {
                "enabled": True,
                "start": [script(hass, "first")],
                "recovery": [script(hass, "recovery")],
            },
            "confirmed": True,
        },
        p.runtime.source_entity_ids,
    )
    await p.effects.settings.save(
        {
            "enabled": True,
            "recovery": True,
            "recipients": [{"service": "mobile_app_simulation_a", "enabled": True}],
        },
        p.effects.settings.revision,
        True,
    )
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    before = (len(calls), len(outputs[0]), deepcopy(p.effects.episodes))
    example = group_preview(p, group, a["source"])
    assert example["phones"][0]["reason"] == "preview_already_attempted"
    assert example["scripts"][0]["reason"] == "preview_already_attempted"
    assert group_preview(p, group, b["source"])["phones"][0]["eligible"]
    assert (len(calls), len(outputs[0]), p.effects.episodes) == before


async def test_preview_cannot_claim_phone_or_script_eligibility_when_executor_paused(
    hass, catalog_devices, outputs
):
    entry, a, b, group, calls = await prepared(hass, catalog_devices)
    p = entry.runtime_data.panel
    await p.groups.async_mutate(
        {
            "operation": "update",
            "group_id": group,
            "revision": p.groups.revision,
            "name": "SIMULATED paused",
            "members": [a["source"], b["source"]],
            "actions": {
                "enabled": True,
                "start": [script(hass, "first")],
                "recovery": [],
            },
            "confirmed": True,
        },
        p.runtime.source_entity_ids,
    )
    await p.effects.settings.save(
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": "mobile_app_simulation_a", "enabled": True}],
        },
        p.effects.settings.revision,
        True,
    )
    await p.async_pause()
    example = group_preview(p, group, a["source"])
    assert (
        not example["phones"][0]["eligible"]
        and example["phones"][0]["reason"] == "execution_paused"
    )
    assert (
        not example["scripts"][0]["eligible"]
        and example["scripts"][0]["reason"] == "execution_paused"
    )
    assert not calls and not outputs[0]


@pytest.mark.parametrize("kind", ["group", "source"])
async def test_invalid_preview_cannot_create_anything(hass, catalog_devices, kind):
    entry, a, _, group, calls = await prepared(hass, catalog_devices)
    with pytest.raises(AutomationError, match="invalid_preview"):
        group_preview(
            entry.runtime_data.panel,
            "missing" if kind == "group" else group,
            "binary_sensor.unselected" if kind == "source" else a["source"],
        )
    assert not calls


async def test_diagnostics_exports_only_allowlisted_fields_and_consistent_aliases(
    hass, catalog_devices, outputs
):
    entry, a, b, group, _ = await prepared(hass, catalog_devices)
    snapshot = entry.runtime_data.panel.snapshot()
    secret = "PRIVATE_ADDRESS_TOKEN_192.0.2.97"
    snapshot["title"] = secret
    for source in snapshot["sources"]:
        source.update(
            name=secret,
            device_name=secret,
            area_name=secret,
            model=secret,
            manufacturer=secret,
        )
        source["capability"]["details"]["payload"] = {"token": secret}
    snapshot["groups"][0]["name"] = secret
    snapshot["automation"]["preview"] = {"title": secret, "message": secret}
    snapshot["automation"]["settings"]["recipients"] = [
        {"service": "mobile_app_" + secret, "enabled": True}
    ]
    report = support_report(snapshot, "0.1.0-beta.5", "2026.11.1")
    serialized = json.dumps(report)
    assert secret not in serialized
    for id in (a["source"], b["source"], b["target"], group):
        assert id not in serialized
    assert set(report) == {
        "schema",
        "versions",
        "result",
        "counts",
        "sources",
        "assignments",
        "recipients",
        "problems",
        "recorded_errors",
        "physical_confirmed",
    }
    assert report["sources"][1]["alias"] == report["assignments"][0]["source"]
    assert report["recipients"][0]["alias"] == "Recipient 1"
    assert not report["physical_confirmed"]
    snapshot["sources"][0]["capability"].update(catalog_id=[], status={}, reason=[])
    report = support_report(snapshot, secret, secret)
    assert report["versions"] == {"alarmmesh": "unknown", "home_assistant": "unknown"}
    assert report["sources"][0]["model"] == "unknown"


@pytest.mark.parametrize(
    "command",
    ["alarmmesh/maintenance_settings", "alarmmesh/preview", "alarmmesh/diagnostics"],
)
async def test_new_commands_require_admin(
    hass, catalog_devices, hass_ws_client, command
):
    entry, a, _, group, calls = await prepared(hass, catalog_devices)
    user = await hass.auth.async_create_user(
        "SIMULATED reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    payload = {"id": 1, "type": command}
    if command.endswith("maintenance_settings"):
        from custom_components.alarmmesh.maintenance import DEFAULT

        payload.update(revision=0, settings=deepcopy(DEFAULT), confirmed=True)
    elif command.endswith("preview"):
        payload.update(group_id=group, source=a["source"])
    await client.send_json(payload)
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "unauthorized"
    assert entry.runtime_data.panel.maintenance.revision == 0 and not calls
