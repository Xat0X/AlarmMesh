"""Route and guided recovery regressions; real HA, mock outputs only."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import outputs as outputs
from test_linking_runtime import configure, setup
from test_maintenance_delivery import settle
from test_matter import matter_devices as matter_devices
from test_zwave import zwave_device as zwave_device

from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.preview import source_preview
from custom_components.alarmmesh.recovery import recover_groups, recovery_plan


async def test_source_route_overlap_and_no_execution(hass, catalog_devices, outputs):
    add, calls = catalog_devices
    a, b = add("HS1SA-E-PLUS", "Heiman"), add("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [a["source"], b["source"]])
    p = entry.runtime_data.panel
    await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [a["source"], b["source"]], [b])
    before = deepcopy((p.linking.active, p.linking.attempted, p.effects.episodes))
    r = source_preview(p, a["source"])
    assert (
        len(r["targets"]) == 1
        and len(r["targets"][0]["via"]) == 2
        and r["targets"][0]["eligible"]
    )
    assert (
        (p.linking.active, p.linking.attempted, p.effects.episodes) == before
        and not calls
        and not outputs[0]
    )
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(calls) == 1


async def fixture(hass, catalog_devices):
    add, _ = catalog_devices
    a, b = add("HS1SA-E-PLUS", "Heiman"), add("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [a["source"], b["source"]])
    p = entry.runtime_data.panel
    await p.groups.async_mutate(
        {
            "operation": "create",
            "revision": 0,
            "name": "SIMULATED",
            "members": [a["source"]],
        },
        p.runtime.source_entity_ids,
    )
    return entry, p, a, b


async def test_recovery_atomic_conflict_no_authority_or_history_transfer(
    hass, catalog_devices
):
    entry, p, a, b = await fixture(hass, catalog_devices)
    old = deepcopy(dict(entry.options))
    plan = recovery_plan(p, a["source"])
    history = deepcopy(p.activity.rows)
    await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    assert (
        p.groups.groups[0]["members"] == [b["source"]]
        and p.groups.groups[0]["origins"] == []
    )
    assert (
        not p.groups.groups[0]["linking"]["enabled"]
        and not p.groups.groups[0]["linking"]["bindings"]
    )
    assert entry.options == old and p.activity.rows == history
    with pytest.raises(AutomationError, match="conflict"):
        await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.panel.groups.groups[0]["members"] == [b["source"]]


async def test_recovery_smoke_missing_candidate_and_storage_failure_keep_groups(
    hass, catalog_devices
):
    entry, p, a, b = await fixture(hass, catalog_devices)
    plan = recovery_plan(p, a["source"])
    old = deepcopy(p.groups.groups)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    with pytest.raises(AutomationError, match="recovery_busy"):
        await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    assert (
        entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
        and p.groups.groups == old
    )
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    hass.states.async_remove(b["source"])
    with pytest.raises(AutomationError, match="recovery_candidate"):
        await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    hass.states.async_set(b["source"], "off", {"device_class": "smoke"})
    with patch.object(
        p.groups.store, "async_save", AsyncMock(side_effect=OSError("SIMULATED"))
    ):
        with pytest.raises(OSError):
            await recover_groups(
                p, a["source"], b["source"], plan["groups"], plan["token"]
            )
    assert p.groups.groups == old and p.groups.revision == plan["revision"]


async def test_recovery_and_route_require_admin(hass, catalog_devices, hass_ws_client):
    entry, p, a, b = await fixture(hass, catalog_devices)
    user = await hass.auth.async_create_user(
        "SIMULATED reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    for i, kind in enumerate(("route", "recovery"), 1):
        await client.send_json(
            {"id": i, "type": "alarmmesh/" + kind, "source": a["source"]}
        )
        r = await client.receive_json()
        assert not r["success"] and r["error"]["code"] == "unauthorized"
    await client.send_json(
        {
            "id": 3,
            "type": "alarmmesh/recovery",
            "source": a["source"],
            "target": a["source"],
            "groups": [],
            "token": "forged",
            "confirmed": True,
        }
    )
    r = await client.receive_json()
    assert not r["success"] and r["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("provider", ["matter", "zwave_js"])
async def test_route_mixed_provider_and_temporary_outage(
    hass, catalog_devices, matter_devices, zwave_device, provider
):
    a = (
        matter_devices[0]()["source"]
        if provider == "matter"
        else zwave_device[0]("binary_sensor", "smoke")
    )
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [a, b["source"]])
    p = entry.runtime_data.panel
    await configure(hass, entry, [a, b["source"]], [b])
    r = source_preview(p, a)
    assert (
        r["source"] == a
        and r["targets"][0]["source"] == b["source"]
        and r["targets"][0]["eligible"]
    )
    hass.states.async_set(a, "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    hass.states.async_set(a, "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert source_preview(p, a)["targets"][0]["eligible"] and not catalog_devices[1]
    if provider == "matter":
        e = er.async_get(hass).async_get(a)
        er.async_get(hass).async_update_entity(
            a, new_unique_id=e.unique_id.replace("SIMULATED", "REPLACEMENT")
        )
        await settle(hass, entry)
        assert not source_preview(p, a)["targets"][0]["eligible"]


async def test_recovery_candidate_identity_and_enabled_outputs_block(
    hass, catalog_devices
):
    entry, p, a, b = await fixture(hass, catalog_devices)
    plan = recovery_plan(p, a["source"])
    er.async_get(hass).async_update_entity(b["source"], new_unique_id="replacement")
    with pytest.raises(AutomationError, match="conflict"):
        await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    p.effects.settings.value["enabled"] = True
    plan = recovery_plan(p, a["source"])
    with pytest.raises(AutomationError, match="recovery_disable"):
        await recover_groups(p, a["source"], b["source"], plan["groups"], plan["token"])
    assert p.groups.groups[0]["members"] == [a["source"]]
