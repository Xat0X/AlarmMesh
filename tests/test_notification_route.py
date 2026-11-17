"""Companion's real HA service adapter; only the external transport is replaced."""

import asyncio
from uuid import uuid4

import pytest
from test_incident_features import A, new_entry, settle

from homeassistant.components.notify.legacy import BaseNotificationService

from custom_components.alarmmesh.preview import source_preview


@pytest.fixture
async def companion(hass):
    delivered = []

    class LocalCompanion(BaseNotificationService):
        @property
        def targets(self):
            return {"simulation_phone": "simulation_destination"}

        async def async_send_message(self, message, **kwargs):
            delivered.append((kwargs["target"][0], {"message": message, **kwargs}))

    target = "simulation_destination"
    service = LocalCompanion()
    await service.async_setup(hass, "mobile_app", "mobile_app")
    await service.async_register_services()
    return target, delivered


async def test_actual_companion_adapter_manual_and_incident(hass, companion):
    target, delivered = companion
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    result = await effects.manual(
        "notification", "mobile_app_simulation_phone", "", True, uuid4().hex
    )
    assert result["status"] == "accepted"
    assert effects.settings.value["enabled"] is False
    assert delivered[0][0] == target
    assert "Test notification" in delivered[0][1]["title"]
    assert delivered[0][1]["data"]["url"] == "/alarmmesh?view=incidents"
    await effects.settings.save(
        {
            "enabled": True,
            "recovery": True,
            "recipients": [{"service": "mobile_app_simulation_phone", "enabled": True}],
        },
        effects.settings.revision,
        True,
    )
    hass.states.async_set(A, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 2
    assert delivered[1][1]["data"]["url"].startswith("/alarmmesh?incident=")
    hass.states.async_set(A, "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 2
    hass.states.async_set(A, "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(delivered) == 3
    assert "cleared" in delivered[2][1]["title"]


@pytest.mark.parametrize("automatic", [False, True])
async def test_own_deadline_is_unknown_and_never_retried(hass, monkeypatch, automatic):
    calls = []

    async def hanging(call):
        calls.append(call)
        await asyncio.Event().wait()

    hass.services.async_register("notify", "mobile_app_simulation_timeout", hanging)
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    monkeypatch.setattr(
        "custom_components.alarmmesh.effects.REQUEST_TIMEOUT", 0.01, raising=False
    )
    if automatic:
        await effects.settings.save(
            {
                "enabled": True,
                "recovery": False,
                "recipients": [
                    {"service": "mobile_app_simulation_timeout", "enabled": True}
                ],
            },
            effects.settings.revision,
            True,
        )
        hass.states.async_set(A, "on", {"device_class": "smoke"})
        await settle(hass, entry)
        result = effects.episodes["notifications"]["receipts"][
            "mobile_app_simulation_timeout"
        ]
    else:
        result = await effects.manual(
            "notification", "mobile_app_simulation_timeout", "", True, uuid4().hex
        )
    assert result["status"] == "outcome_unknown"
    effects.changed()
    await settle(hass, entry)
    assert len(calls) == 1


async def test_ws_confirmation_current_context_and_no_replay(
    hass, companion, hass_ws_client
):
    _, delivered = companion
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    target = "mobile_app_simulation_phone"
    client = await hass_ws_client(hass)
    request = {
        "type": "alarmmesh/test",
        "kind": "notification",
        "target": target,
        "confirmed": True,
        "request_id": uuid4().hex,
    }
    token = effects.confirmation(target)
    hass.states.async_set(
        A, "off", {"device_class": "smoke", "friendly_name": "SIMULATED renamed"}
    )
    assert token != effects.confirmation(target)
    for number, identity in enumerate(["", token], 1):
        await client.send_json({**request, "id": number, "identity": identity})
        response = await client.receive_json()
        assert response["error"]["code"] == "notification_confirmation_stale"
    assert delivered == []
    request["identity"] = effects.confirmation(target)
    await client.send_json({**request, "id": 3})
    assert (await client.receive_json())["result"]["status"] == "accepted"
    await client.send_json({**request, "id": 4})
    assert (await client.receive_json())["error"]["code"] == "test_busy"
    assert len(delivered) == 1
    assert effects.manual_results[0]["request_id"] == request["request_id"]
    assert effects.manual_results[0]["started"]


async def test_disappeared_recipient_after_confirmation_before_dispatch(
    hass, companion
):
    _, delivered = companion
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    target = "mobile_app_simulation_phone"
    token = effects.confirmation(target)
    # Hold the actual bounded execution slot while the service disappears.
    semaphore = effects.linking._semaphore
    acquired = semaphore._value
    for _ in range(acquired):
        await semaphore.acquire()
    pending = asyncio.create_task(
        effects.manual("notification", target, token, True, uuid4().hex)
    )
    await asyncio.sleep(0)
    hass.services.async_remove("notify", target)
    for _ in range(acquired):
        semaphore.release()
    result = await pending
    assert result["status"] == "failed"
    assert result["error"] == "recipient_unavailable"
    assert delivered == []


async def test_timestamp_like_source_name_still_invalidates_confirmation(
    hass, companion
):
    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    hass.states.async_set(
        A, "off", {"device_class": "smoke", "friendly_name": "2026-11-17T foyer"}
    )
    token = effects.confirmation("mobile_app_simulation_phone")
    hass.states.async_set(
        A, "off", {"device_class": "smoke", "friendly_name": "2026-11-17T bedroom"}
    )
    assert effects.confirmation("mobile_app_simulation_phone") != token


async def test_readonly_route_shares_configuration_gate_and_preserves_missing(
    hass, companion
):
    _, delivered = companion
    entry = await new_entry(hass, (A,))
    panel = entry.runtime_data.panel
    effects = panel.effects
    target = "mobile_app_simulation_phone"
    assert source_preview(panel, A)["phones"][0]["reason"] == "recipient_not_selected"
    await effects.settings.save(
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": target, "enabled": True}],
        },
        effects.settings.revision,
        True,
    )
    preview = source_preview(panel, A)
    assert preview["phones"][0]["eligible"] is True
    assert "SIMULATED a" in preview["notification_preview"]["message"]
    hass.services.async_remove("notify", target)
    assert source_preview(panel, A)["phones"][0]["reason"] == "recipient_unavailable"
    assert effects.snapshot()["settings"]["recipients"] == [
        {"service": target, "enabled": True}
    ]
    assert delivered == []
