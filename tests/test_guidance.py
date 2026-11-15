"""Guidance derives from actual entries, registries and stored explicit choices."""

from copy import deepcopy

from test_catalog import catalog_devices as catalog_devices
from test_linking_runtime import configure, setup
from test_panel import A, B
from test_panel import panel_entry as panel_entry

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


def states(snapshot):
    return {step["id"]: step["status"] for step in snapshot["review"]["steps"]}


async def test_supported_but_unconfirmed_prerequisite_is_not_labelled_unsupported(
    hass, catalog_devices
):
    add, calls = catalog_devices
    item = add(
        "JY-GZ-01AQ",
        "Aqara",
        key="buzzer",
        idle="mute",
        attrs={"options": ["alarm", "mute"]},
        gate=("switch", "linkage_alarm", "off"),
    )
    entry = await setup(hass, [item["source"]])
    snapshot = entry.runtime_data.panel.snapshot()
    assert snapshot["sources"][0]["capability"]["status"] == "setting_needed"
    assert states(snapshot)["sounders"] == "disabled"
    assert not calls


async def test_guidance_is_current_metadata_not_a_persisted_checklist(
    hass, panel_entry
):
    panel = panel_entry.runtime_data.panel
    before_options = deepcopy(dict(panel_entry.options))
    snapshot = panel.snapshot()
    assert states(snapshot) == {
        "sources": "needs_attention",
        "rooms": "needs_attention",
        "groups": "disabled",
        "sounders": "not_supported",
        "notifications": "disabled",
        "scripts": "disabled",
        "check": "needs_attention",
    }
    hass.states.async_set(B, "off", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert states(panel.snapshot())["sources"] == "configured"
    room = ar.async_get(hass).async_create("SIMULATED room")
    for index, source in enumerate((A, B)):
        hass.states.async_remove(source)
        entry = er.async_get(hass).async_get_or_create(
            "binary_sensor",
            "test",
            f"guide-{index}",
            suggested_object_id=source.split(".")[1],
            original_device_class="smoke",
        )
        assert entry.entity_id == source
        er.async_get(hass).async_update_entity(source, area_id=room.id)
        hass.states.async_set(source, "off", {"device_class": "smoke"})
    await hass.async_block_till_done()
    assert states(panel.snapshot())["rooms"] == "configured"
    await panel.groups.async_mutate(
        {
            "operation": "create",
            "revision": 0,
            "name": "SIMULATED optional group",
            "members": [A, B],
            "origins": [],
        },
        (A, B),
    )
    snapshot = panel.snapshot()
    assert states(snapshot)["groups"] == "configured"
    assert (
        states(snapshot)["notifications"] == states(snapshot)["scripts"] == "disabled"
    )
    assert snapshot["review"]["issues"] == []
    assert panel_entry.options == before_options and panel_entry.data == {}
    assert set(panel.groups.groups[0]) <= {
        "id",
        "name",
        "members",
        "origins",
        "linking",
        "actions",
    }


async def test_missing_recipient_retained_off_without_optional_step_error(
    hass, panel_entry
):
    panel = panel_entry.runtime_data.panel
    value = {
        "enabled": False,
        "recovery": False,
        "recipients": [{"service": "mobile_app_simulated_gone", "enabled": False}],
    }
    # A previously valid saved recipient can disappear; load shape is still valid.
    panel.effects.settings.value = deepcopy(value)
    snapshot = panel.snapshot()
    assert states(snapshot)["notifications"] == "disabled"
    assert any(
        issue["code"] == "recipient_unavailable"
        for issue in snapshot["review"]["issues"]
    )
    assert panel.effects.settings.value == value


async def test_server_binding_review_retains_renamed_control_without_replacement(
    hass, catalog_devices
):
    add, calls = catalog_devices
    a = add("HS1SA-E-PLUS", "Heiman")
    b = add("HS1SA-E-PLUS", "Heiman")
    members = [a["source"], b["source"]]
    entry = await setup(hass, members)
    group_id = await configure(hass, entry, members, [b], enabled=False)
    panel = entry.runtime_data.panel
    original = deepcopy(panel.groups.groups)
    assert panel.snapshot()["groups"][0]["binding_checks"][0]["valid"]
    old_state = hass.states.get(b["target"])
    er.async_get(hass).async_update_entity(
        b["target"], new_entity_id="select.simulated_replacement"
    )
    hass.states.async_remove(b["target"])
    hass.states.async_set(
        "select.simulated_replacement", old_state.state, dict(old_state.attributes)
    )
    await hass.async_block_till_done()
    snapshot = panel.snapshot()
    check = snapshot["groups"][0]["binding_checks"][0]
    assert not check["valid"] and check["reason"] == "control_changed"
    assert states(snapshot)["sounders"] == "disabled"
    assert any(
        i["code"] == "control_changed" and i["group"] == group_id
        for i in snapshot["review"]["issues"]
    )
    assert panel.groups.groups == original and not calls


async def test_changed_source_class_cannot_leave_configuration_review_green(
    hass, catalog_devices
):
    add, calls = catalog_devices
    item = add("HS1SA-E-PLUS", "Heiman")
    room = ar.async_get(hass).async_create("SIMULATED room")
    dr.async_get(hass).async_update_device(item["device"], area_id=room.id)
    entry = await setup(hass, [item["source"]])
    panel = entry.runtime_data.panel
    result = entry.runtime_data.result
    assert states(panel.snapshot())["sources"] == "configured"
    assert states(panel.snapshot())["check"] == "configured"

    er.async_get(hass).async_update_entity(item["source"], device_class="opening")
    await hass.async_block_till_done()
    snapshot = panel.snapshot()
    assert snapshot["sources"][0]["capability"]["reason"] == "source_identity_changed"
    assert states(snapshot)["sources"] == "needs_attention"
    assert states(snapshot)["check"] == "needs_attention"
    assert any(
        i["code"] == "source_identity_changed" for i in snapshot["review"]["issues"]
    )
    assert entry.runtime_data.result == result and not calls

    er.async_get(hass).async_update_entity(item["source"], device_class="smoke")
    await hass.async_block_till_done()
    assert states(panel.snapshot())["sources"] == "configured"
    assert states(panel.snapshot())["check"] == "configured"
    assert entry.runtime_data.result == result and not calls
