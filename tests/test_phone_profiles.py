"""Per-phone plans through HA's real service layer, never external delivery."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import A, new_entry, settle
from test_notification_route import companion as companion

from custom_components.alarmmesh.notification_profiles import receiver_metadata


def phone(hass, target, platform, critical=True):
    entry = MockConfigEntry(
        domain="mobile_app",
        unique_id=uuid4().hex,
        data={
            "device_name": target.removeprefix("mobile_app_"),
            "device_id": uuid4().hex,
            "os_name": platform,
        },
    )
    entry.add_to_hass(hass)
    profile = {
        "version": 1,
        "platform": platform,
        "origin": "metadata",
        "identity": receiver_metadata(hass, target)["identity"],
        "critical": critical,
    }
    if platform == "ios":
        profile.update(sound="default", sound_source="bundled", volume=1.0)
    return profile, entry


@pytest.mark.parametrize("platform", ["ios", "android"])
async def test_critical_real_adapter_and_ordinary_recovery(hass, companion, platform):
    _, delivered = companion
    target = "mobile_app_simulation_phone"
    profile, _ = phone(hass, target, platform)
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    await effects.settings.save(
        {
            "enabled": True,
            "recovery": True,
            "recipients": [{"service": target, "enabled": True, "profile": profile}],
        },
        0,
        True,
    )
    assert delivered == []
    hass.states.async_set(A, "on", {"device_class": "smoke", "friendly_name": "Senne"})
    await settle(hass, entry)
    data = delivered[0][1]["data"]
    assert delivered[0][1]["title"] == "Smoke alert · Senne"
    episode = effects.episodes["notifications"]
    link = "url" if platform == "ios" else "clickAction"
    assert data[link] == f"/alarmmesh?incident={episode['id']}"
    if platform == "ios":
        assert data["push"]["sound"] == {
            "name": "default",
            "critical": 1,
            "volume": 1.0,
        }
        assert "channel" not in data
    else:
        assert (data["priority"], data["ttl"], data["channel"]) == (
            "high",
            0,
            "alarm_stream",
        )
        assert "push" not in data and "url" not in data
    hass.states.async_set(A, "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 1
    hass.states.async_set(A, "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 2
    assert not {"push", "channel", "ttl", "priority"}.intersection(
        delivered[1][1]["data"]
    )


async def test_saving_during_smoke_does_not_send(hass, companion, hass_ws_client):
    _, delivered = companion
    entry = await new_entry(hass, (A,))
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "alarmmesh/settings",
            "revision": 0,
            "confirmed": True,
            "notifications": {
                "enabled": True,
                "recovery": False,
                "recipients": [
                    {"service": "mobile_app_simulation_phone", "enabled": True}
                ],
            },
        }
    )
    assert (await client.receive_json())["success"]
    await settle(hass, entry)
    assert delivered == []
    hass.states.async_set(A, "off", {"device_class": "smoke"})
    await settle(hass, entry)
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 1


@pytest.mark.parametrize("platform", ["ios", "android"])
async def test_ordinary_profile_and_preview_request_binding(
    hass, companion, hass_ws_client, platform
):
    _, delivered = companion
    target = "mobile_app_simulation_phone"
    profile, _ = phone(hass, target, platform, False)
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    await effects.settings.save(
        {
            "enabled": False,
            "recovery": False,
            "recipients": [{"service": target, "enabled": True, "profile": profile}],
        },
        0,
        False,
    )
    client = await hass_ws_client(hass)
    request = uuid4().hex
    await client.send_json(
        {
            "id": 1,
            "type": "alarmmesh/notification_preview",
            "target": target,
            "request_id": request,
        }
    )
    plan = (await client.receive_json())["result"]
    assert delivered == []
    assert plan["phone_confirmed"] is False
    assert plan["confirmation"] != effects.confirmation(target)
    from custom_components.alarmmesh.automation import AutomationError

    with pytest.raises(AutomationError, match="notification_confirmation_stale"):
        await effects.manual(
            "notification", target, plan["confirmation"], True, uuid4().hex
        )
    result = await effects.manual(
        "notification", target, plan["confirmation"], True, request
    )
    assert result["status"] == "accepted"
    assert len(delivered) == 1
    data = delivered[0][1]["data"]
    if platform == "ios":
        assert data["push"]["sound"] == "default"
    else:
        assert not {"push", "channel", "priority", "ttl", "url"}.intersection(data)
        assert data["clickAction"] == "/alarmmesh?view=incidents"
    with pytest.raises(AutomationError, match="test_busy"):
        await effects.manual(
            "notification", target, plan["confirmation"], True, request
        )
    assert len(delivered) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("volume", -0.1),
        ("volume", 1.1),
        ("volume", True),
        ("volume", "1"),
        ("volume", float("nan")),
        ("volume", float("inf")),
        ("sound", "invented.wav"),
        ("sound", []),
        ("sound_source", []),
        ("platform", {}),
        ("origin", []),
        ("critical", 1),
        ("identity", "wrong"),
        ("version", True),
    ],
)
async def test_invalid_profile_rejected_without_silent_downgrade(
    hass, companion, field, value
):
    from custom_components.alarmmesh.notification_profiles import (
        ProfileError,
        validate_profile,
    )

    profile, _ = phone(hass, "mobile_app_simulation_phone", "ios")
    profile[field] = value
    with pytest.raises(ProfileError):
        validate_profile(profile)
    assert companion[1] == []


@pytest.mark.parametrize(
    "sound,source",
    [
        ("default", "bundled"),
        ("US-EN-Alexa-Smoke-Detected-Generic.wav", "bundled"),
        ("my imported.caf", "imported"),
    ],
)
@pytest.mark.parametrize("volume", [0, 1])
async def test_reviewed_sound_and_volume_bounds(hass, companion, sound, source, volume):
    from custom_components.alarmmesh.notification_profiles import build_plan

    profile, _ = phone(hass, "mobile_app_simulation_phone", "ios")
    profile.update(sound=sound, sound_source=source, volume=volume)
    original = deepcopy(profile)
    plan = build_plan(
        hass,
        "mobile_app_simulation_phone",
        profile,
        {"message": "simulation"},
        smoke=True,
    )
    assert plan["data"]["push"]["sound"] == {
        "name": sound,
        "critical": 1,
        "volume": volume,
    }
    assert profile == original


async def test_changed_metadata_blocks_without_erasing_profile(hass, companion):
    from custom_components.alarmmesh.automation import AutomationError

    target = "mobile_app_simulation_phone"
    profile, registration = phone(hass, target, "ios")
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    value = {
        "enabled": True,
        "recovery": False,
        "recipients": [{"service": target, "enabled": True, "profile": profile}],
    }
    await effects.settings.save(value, 0, True)
    for changed, error in [
        ({"os_name": "Android"}, "phone_platform_changed"),
        ({"device_id": "replacement"}, "phone_identity_changed"),
    ]:
        hass.config_entries.async_update_entry(
            registration, data={**registration.data, **changed}
        )
        with pytest.raises(AutomationError, match=error):
            effects.phone_plan(target, test=True)
        assert effects.settings.value == value
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert companion[1] == []


async def test_profile_and_message_changes_invalidate_confirmation(hass, companion):
    from custom_components.alarmmesh.automation import AutomationError

    target = "mobile_app_simulation_phone"
    profile, _ = phone(hass, target, "ios")
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    value = {
        "enabled": False,
        "recovery": False,
        "recipients": [{"service": target, "enabled": True, "profile": profile}],
    }
    await effects.settings.save(value, 0, True)
    request = uuid4().hex
    token = effects.confirmation(target, request)
    profile["volume"] = 0.5
    await effects.settings.save(value, 1, True)
    with pytest.raises(AutomationError, match="notification_confirmation_stale"):
        await effects.manual("notification", target, token, True, request)
    token = effects.confirmation(target, request)
    hass.states.async_set(
        A, "off", {"device_class": "smoke", "friendly_name": "Changed source"}
    )
    assert effects.confirmation(target, request) != token
    assert companion[1] == []


async def test_mixed_profiles_failure_isolation_and_restart(hass):
    from homeassistant.exceptions import HomeAssistantError

    calls = []

    async def notify(call):
        calls.append((call.service, dict(call.data)))
        if call.service.endswith("ios"):
            raise HomeAssistantError("simulation failure")

    targets = ["mobile_app_simulation_ios", "mobile_app_simulation_android"]
    for target in targets:
        hass.services.async_register("notify", target, notify)
    rows = []
    for target, platform in zip(targets, ["ios", "android"], strict=True):
        profile, _ = phone(hass, target, platform)
        rows.append({"service": target, "enabled": True, "profile": profile})
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    value = {"enabled": True, "recovery": True, "recipients": rows}
    await effects.settings.save(value, 0, True)
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(calls) == 2
    actual = dict(calls)
    assert actual[targets[0]]["data"]["push"]["sound"]["critical"] == 1
    assert actual[targets[1]]["data"]["channel"] == "alarm_stream"
    receipts = effects.episodes["notifications"]["receipts"]
    assert receipts[targets[0]]["status"] == "failed"
    assert receipts[targets[1]]["status"] == "accepted"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    assert entry.runtime_data.panel.effects.settings.value == value
    assert len(calls) == 2
    hass.states.async_set(A, "on", {"device_class": "smoke", "extra": "repeat"})
    await settle(hass, entry)
    assert len(calls) == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert effects.closed


async def test_beta11_storage_preserved_without_critical_upgrade(hass, companion):
    from custom_components.alarmmesh.automation import NotificationStore

    entry = await new_entry(hass, (A,))
    original = {
        "enabled": True,
        "recovery": True,
        "recipients": [{"service": "mobile_app_simulation_phone", "enabled": True}],
    }
    effects = entry.runtime_data.panel.effects
    await effects.settings.save(original, 0, True)
    store = NotificationStore(hass, entry.entry_id)
    await store.load()
    assert store.value == original
    assert store.revision == 1
    assert (
        effects.phone_plan("mobile_app_simulation_phone", test=True)["profile"] is None
    )
    assert (
        "push"
        not in effects.phone_plan("mobile_app_simulation_phone", test=True)["message"][
            "data"
        ]
    )


@pytest.mark.parametrize("platform", ["ios", "android"])
async def test_maintenance_and_reminders_stay_ordinary_with_critical_profile(
    hass, companion, catalog_devices, freezer, platform
):
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    from test_activity_reminders import schedule
    from test_activity_reminders import settle as all_settled
    from test_maintenance_delivery import enable, prepare

    from homeassistant.util import dt as dt_util

    freezer.move_to("2026-11-17T06:00:00Z")
    await hass.config.async_update(time_zone="Europe/Brussels")
    target = "mobile_app_simulation_phone"
    profile, _ = phone(hass, target, platform)
    entry, d = await prepare(hass, catalog_devices)
    p = entry.runtime_data.panel
    await p.effects.settings.save(
        {
            "enabled": True,
            "recovery": True,
            "recipients": [{"service": target, "enabled": True, "profile": profile}],
        },
        0,
        True,
    )
    await enable(hass, entry, recipients=[{"service": target, "enabled": True}])
    hass.states.async_set(d["battery"], "5", {"unit_of_measurement": "%"})
    await all_settled(hass, entry)
    assert len(companion[1]) == 1
    await schedule(hass, entry, d["source"], "2026-11-17", recipient=target)
    freezer.move_to("2026-11-17T08:00:00Z")
    async_fire_time_changed(hass, dt_util.utcnow())
    await all_settled(hass, entry)
    assert len(companion[1]) == 2
    for _, payload in companion[1]:
        assert not {"push", "channel", "priority", "ttl"}.intersection(
            payload.get("data", {})
        )
    assert p.effects.settings.value["recipients"][0]["profile"]["critical"]
