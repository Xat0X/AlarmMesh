"""Real HA panel, registry, transport, storage and lifecycle behavior."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components import frontend
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN
from custom_components.alarmmesh.groups import GroupError, GroupStore
from custom_components.alarmmesh.panel import DATA_HUB

A = "binary_sensor.hall"
B = "binary_sensor.kitchen"


@pytest.fixture
async def panel_entry(hass):
    hass.states.async_set(A, "off", {"device_class": "smoke", "friendly_name": "Hall"})
    hass.states.async_set(B, "unavailable", {"device_class": "smoke"})
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_SOURCE_ENTITY_IDS: [A, B]}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_groups_persist_without_touching_options(hass, panel_entry):
    panel = panel_entry.runtime_data.panel
    original = deepcopy(dict(panel_entry.options))
    await panel.groups.async_mutate(
        {"operation": "create", "revision": 0, "name": "  Home  ", "members": [A, B]},
        (A, B),
    )
    saved = deepcopy(panel.groups.groups)
    assert saved[0]["name"] == "Home"
    assert len(saved[0]["id"]) == 32
    assert await hass.config_entries.async_reload(panel_entry.entry_id)
    assert panel_entry.runtime_data.panel.groups.groups == saved
    assert panel_entry.runtime_data.panel.groups.revision == 1
    assert panel_entry.options == original
    assert panel_entry.data == {}


@pytest.mark.parametrize(
    "name,members,code",
    [
        ("  ", [A], "invalid_name"),
        ("x" * 65, [A], "invalid_name"),
        (9, [A], "invalid_name"),
        ("Home", [A, A], "invalid_members"),
        ("Home", ["sensor.bad"], "invalid_members"),
        ("Home", ["binary_sensor."], "invalid_members"),
        ("Home", ["binary_sensor.NEW"], "invalid_members"),
        ("Home", [[A]], "invalid_members"),
        ("Home", A, "invalid_members"),
        ("Home", [A] * 257, "invalid_members"),
    ],
)
async def test_invalid_groups_never_write(hass, name, members, code):
    store = GroupStore(hass, "test")
    with patch.object(store.store, "async_save", new_callable=AsyncMock) as save:
        with pytest.raises(GroupError, match=code):
            await store.async_mutate(
                {
                    "operation": "create",
                    "revision": 0,
                    "name": name,
                    "members": members,
                },
                (A,),
            )
        save.assert_not_called()
    assert store.revision == 0 and store.groups == []


async def test_group_conflict_and_concurrent_writes(hass):
    store = GroupStore(hass, "test")
    command = {"operation": "create", "revision": 0, "name": "Home", "members": [A]}
    results = await asyncio.gather(
        store.async_mutate(command, (A,)),
        store.async_mutate(command, (A,)),
        return_exceptions=True,
    )
    assert (
        sum(
            isinstance(result, GroupError) and str(result) == "conflict"
            for result in results
        )
        == 1
    )
    assert len(store.groups) == 1 and store.revision == 1
    with pytest.raises(GroupError, match="conflict"):
        await store.async_mutate({**command, "revision": True}, (A,))
    with patch.object(
        store.store, "async_save", new_callable=AsyncMock, side_effect=OSError
    ):
        with pytest.raises(OSError):
            await store.async_mutate({**command, "revision": 1}, (A,))
    assert len(store.groups) == 1 and store.revision == 1


async def test_group_membership_stale_references_and_delete(hass):
    store = GroupStore(hass, "test")
    await store.async_mutate(
        {"operation": "create", "revision": 0, "name": "Home", "members": [A]}, (A,)
    )
    group_id = store.groups[0]["id"]
    await store.async_mutate(
        {
            "operation": "update",
            "revision": 1,
            "group_id": group_id,
            "name": "Renamed",
            "members": [A, B],
        },
        (B,),
    )
    assert store.groups[0]["members"] == [A, B]
    with pytest.raises(GroupError, match="invalid_members"):
        await store.async_mutate(
            {"operation": "create", "revision": 2, "name": "Other", "members": [A]},
            (B,),
        )
    await store.async_mutate(
        {"operation": "delete", "revision": 2, "group_id": group_id}, (B,)
    )
    assert store.groups == [] and store.revision == 3
    await store.async_close()
    with pytest.raises(GroupError, match="not_loaded"):
        await store.async_mutate(
            {"operation": "create", "revision": 3, "name": "Home", "members": []}, ()
        )


async def test_real_metadata_area_precedence_and_shared_status(hass, panel_entry):
    area1 = ar.async_get(hass).async_create("Downstairs")
    area2 = ar.async_get(hass).async_create("Upstairs")
    source_entry = MockConfigEntry(domain="template", data={})
    source_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={("template", "simulation")},
        model="Simulated model",
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area1.id)
    hass.states.async_remove(A)
    entity = er.async_get(hass).async_get_or_create(
        "binary_sensor",
        "template",
        "sim-source",
        suggested_object_id="hall",
        device_id=device.id,
    )
    assert entity.entity_id == A
    er.async_get(hass).async_update_entity(A, area_id=area2.id, name="Custom detector")
    panel = panel_entry.runtime_data.panel
    await panel.groups.async_mutate(
        {"operation": "create", "revision": 0, "name": "Home", "members": [A, B]},
        (A, B),
    )
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await hass.async_block_till_done()
    data = panel.snapshot()
    assert data["result"] == {"smoke": "SMOKE_REPORTED", "availability": "INCOMPLETE"}
    assert data["groups"][0]["result"] == data["result"]
    assert data["usable"] == 1
    source = data["sources"][0]
    assert source["area_id"] == area2.id and source["name"] == "Custom detector"
    assert source["model"] == "Simulated model"
    assert "battery" not in source and "last_seen" not in source
    er.async_get(hass).async_update_entity(A, area_id=None)
    assert panel.snapshot()["sources"][0]["area_id"] == area1.id
    hass.states.async_remove(A)
    await hass.async_block_till_done()
    assert panel.snapshot()["sources"][0]["status"] == "MISSING"
    assert panel.snapshot()["result"]["smoke"] == "INDETERMINATE"


@pytest.mark.parametrize(
    "a,b,home,room,group",
    [
        (
            "off",
            "off",
            ("NO_SMOKE_REPORTED", "COMPLETE"),
            ("NO_SMOKE_REPORTED", "COMPLETE"),
            ("NO_SMOKE_REPORTED", "COMPLETE"),
        ),
        (
            "off",
            "unknown",
            ("INDETERMINATE", "INCOMPLETE"),
            ("NO_SMOKE_REPORTED", "COMPLETE"),
            ("INDETERMINATE", "INCOMPLETE"),
        ),
        (
            "on",
            "unavailable",
            ("SMOKE_REPORTED", "INCOMPLETE"),
            ("SMOKE_REPORTED", "COMPLETE"),
            ("INDETERMINATE", "INCOMPLETE"),
        ),
    ],
)
async def test_room_and_group_are_distinct_runtime_subsets(
    hass, panel_entry, a, b, home, room, group
):
    area = ar.async_get(hass).async_create("Assigned simulation room")
    hass.states.async_remove(A)
    entity = er.async_get(hass).async_get_or_create(
        "binary_sensor", "template", "hall", suggested_object_id="hall"
    )
    assert entity.entity_id == A
    er.async_get(hass).async_update_entity(A, area_id=area.id)
    panel = panel_entry.runtime_data.panel
    await panel.groups.async_mutate(
        {"operation": "create", "revision": 0, "name": "Only B", "members": [B]}, (A, B)
    )
    hass.states.async_set(A, a, {"device_class": "smoke"})
    hass.states.async_set(B, b, {"device_class": "smoke"})
    await hass.async_block_till_done()
    snapshot = panel.snapshot()
    assert tuple(snapshot["result"].values()) == home
    assert (
        tuple(
            next(r for r in snapshot["rooms"] if r["id"] == area.id)["result"].values()
        )
        == room
    )
    assert tuple(snapshot["groups"][0]["result"].values()) == group
    assert next(r for r in snapshot["rooms"] if r["id"] is None)["members"] == [B]


async def test_raw_change_push_and_lifecycle(hass, panel_entry):
    hub = hass.data[DATA_HUB]
    panel = panel_entry.runtime_data.panel
    updates = []
    hub.listeners.add(lambda: updates.append(hub.snapshot()))
    hass.states.async_set(B, "unknown", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert updates[-1]["sources"][1]["status"] == "UNKNOWN"
    assert updates[-1]["result"] == panel.snapshot()["result"]
    assert "alarmmesh" in hass.data[frontend.DATA_PANELS]
    assert await hass.config_entries.async_reload(panel_entry.entry_id)
    assert any(not update["available"] for update in updates)
    assert not panel.unsubscribers and not panel.runtime._observers
    assert hub.controller is not panel
    assert await hass.config_entries.async_unload(panel_entry.entry_id)
    assert updates[-1] == {"available": False}
    assert "alarmmesh" not in hass.data[frontend.DATA_PANELS]
    count = len(updates)
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert len(updates) == count


async def test_stale_groups_after_selection_change(hass, panel_entry):
    panel = panel_entry.runtime_data.panel
    await panel.groups.async_mutate(
        {"operation": "create", "revision": 0, "name": "Home", "members": [A]}, (A, B)
    )
    hass.config_entries.async_update_entry(
        panel_entry, options={CONF_SOURCE_ENTITY_IDS: [B]}
    )
    assert await hass.config_entries.async_reload(panel_entry.entry_id)
    data = panel_entry.runtime_data.panel.snapshot()
    assert data["groups"][0]["unselected"] == [A]
    assert data["groups"][0]["result"] == {
        "smoke": "INDETERMINATE",
        "availability": "INCOMPLETE",
    }
    assert data["groups"][0]["members"] == [A]


async def test_websocket_subscription_mutation_and_unsubscribe(
    hass, panel_entry, hass_ws_client
):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "alarmmesh/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["available"]
    await client.send_json(
        {
            "id": 2,
            "type": "alarmmesh/group",
            "operation": "create",
            "revision": 0,
            "name": "Home",
            "members": [A],
        }
    )
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["groups"][0]["name"] == "Home"
    await client.send_json(
        {
            "id": 3,
            "type": "alarmmesh/group",
            "operation": "create",
            "revision": 0,
            "name": "Old browser",
            "members": [A],
        }
    )
    assert (await client.receive_json())["error"]["code"] == "conflict"
    await client.send_json({"id": 4, "type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"]
    assert not hass.data[DATA_HUB].listeners


async def test_non_admin_websocket_is_denied(hass, panel_entry, hass_ws_client):
    user = await hass.auth.async_create_user(
        "Simulation reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    for message in (
        {"id": 1, "type": "alarmmesh/subscribe"},
        {
            "id": 2,
            "type": "alarmmesh/group",
            "operation": "create",
            "revision": 0,
            "name": "Denied",
            "members": [A],
        },
    ):
        await client.send_json(message)
        result = await client.receive_json()
        assert result["success"] is False and result["error"]["code"] == "unauthorized"
    assert panel_entry.runtime_data.panel.groups.groups == []
    assert not hass.data[DATA_HUB].listeners


async def test_bad_storage_fails_closed(hass):
    store = GroupStore(hass, "test")
    with patch.object(
        store.store,
        "async_load",
        return_value={"revision": 2, "groups": [{"id": "bad"}]},
    ):
        with pytest.raises(GroupError, match="invalid_storage"):
            await store.async_load()
    assert store.groups == []


async def test_static_panel_assets_are_packaged_and_served(
    hass, panel_entry, hass_client
):
    client = await hass_client()
    for path, marker in (
        ("panel.js", "alarmmesh-panel"),
        ("panel.css", "@media"),
        ("translations.js", "Geen rook gemeld"),
    ):
        response = await client.get(f"/alarmmesh-assets/{path}")
        assert response.status == 200
        assert marker in await response.text()


async def test_admin_revocation_stops_private_push(hass, panel_entry, hass_ws_client):
    user = await hass.auth.async_create_user(
        "Simulation manager", group_ids=["system-admin"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    await client.send_json({"id": 1, "type": "alarmmesh/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["available"]
    await hass.auth.async_update_user(user, group_ids=["system-users"])
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert (await client.receive_json())["event"] == {"available": False}


async def test_entry_removal_removes_only_its_groups(hass, panel_entry, hass_storage):
    store = panel_entry.runtime_data.panel.groups
    await store.async_mutate(
        {"operation": "create", "revision": 0, "name": "Home", "members": [A]}, (A,)
    )
    key = f"alarmmesh.groups.{panel_entry.entry_id}"
    assert key in hass_storage
    assert await hass.config_entries.async_remove(panel_entry.entry_id)
    assert key not in hass_storage
    assert hass.states.get(A).state == "off"


async def test_reload_drains_an_in_flight_group_save(hass, panel_entry):
    panel = panel_entry.runtime_data.panel
    started, release = asyncio.Event(), asyncio.Event()
    save = panel.groups.store.async_save

    async def delayed_save(data):
        started.set()
        await release.wait()
        await save(data)

    with patch.object(panel.groups.store, "async_save", side_effect=delayed_save):
        write = asyncio.create_task(
            panel.groups.async_mutate(
                {
                    "operation": "create",
                    "revision": 0,
                    "name": "Survives reload",
                    "members": [A],
                },
                (A, B),
            )
        )
        await started.wait()
        reload = asyncio.create_task(
            hass.config_entries.async_reload(panel_entry.entry_id)
        )
        await asyncio.sleep(0)
        release.set()
        await write
        assert await reload
    assert panel_entry.runtime_data.panel.groups.groups[0]["name"] == "Survives reload"
    assert not panel.unsubscribers and not panel.runtime._observers


async def test_group_load_failure_does_not_leave_panel_or_sources(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_SOURCE_ENTITY_IDS: [A]}
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.alarmmesh.groups.GroupStore.async_load",
        side_effect=GroupError("invalid_storage"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert hass.data[DATA_HUB].controller is None
    assert "alarmmesh" not in hass.data[frontend.DATA_PANELS]
