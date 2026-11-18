"""Read-only routes and user observations: real HA, local simulated I/O only."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import A, new_entry, settle
from test_linking_runtime import configure, setup
from test_matter import matter_devices as matter_devices
from test_notification_route import companion as companion
from test_phone_profiles import phone
from test_zwave import zwave_device as zwave_device

from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.phone_evidence import LIMIT, PhoneEvidence
from custom_components.alarmmesh.preview import alarm_settings, source_preview


async def recorded(hass, companion):
    target = "mobile_app_simulation_phone"
    profile, registration = phone(hass, target, "ios")
    entry = await new_entry(hass, (A,))
    p = entry.runtime_data.panel
    await p.effects.settings.save(
        {
            "enabled": False,
            "recovery": False,
            "recipients": [{"service": target, "enabled": True, "profile": profile}],
        },
        0,
        True,
    )
    request = uuid4().hex
    await p.effects.manual(
        "notification", target, p.effects.confirmation(target, request), True, request
    )
    return entry, p, request, profile, registration


async def test_alarm_inventory_reuses_mixed_routes_and_deduplicates(
    hass, catalog_devices, matter_devices, zwave_device, companion
):
    add, calls = catalog_devices
    a = add("HS1SA-E-PLUS", "Heiman")
    b = add("SMSZB-120", "frient A/S", "zha", "siren", "siren", idle="off")
    m = matter_devices[0]()["source"]
    z = zwave_device[0]("binary_sensor", "smoke")
    entry = await setup(hass, [a["source"], b["source"], m, z])
    p = entry.runtime_data.panel
    for _ in range(2):
        await configure(hass, entry, [a["source"], b["source"], m, z], [a])
    await p.effects.settings.save(
        {
            "enabled": False,
            "recovery": False,
            "recipients": [{"service": "mobile_app_simulation_phone", "enabled": True}],
        },
        0,
        False,
    )
    before = deepcopy(
        (
            p.groups.groups,
            p.effects.settings.value,
            p.linking.attempted,
            p.effects.episodes,
        )
    )
    for _ in range(3):
        result = alarm_settings(p)
        assert result["readonly"] and len(result["rows"]) == 4
        for row in result["rows"]:
            route = source_preview(p, row["source"])
            assert row["targets"] == route["targets"]
            assert len(row["targets"]) == 1 and len(row["targets"][0]["via"]) == 2
            assert len(row["phones"]) == 1 and row["phones"][0]["reason"] == "disabled"
    hass.states.async_set(m, "unavailable", {"device_class": "smoke"})
    await settle(hass, entry)
    assert (
        next(r for r in alarm_settings(p)["rows"] if r["source"] == m)["status"]
        == "UNREACHABLE"
    )
    assert (
        p.groups.groups,
        p.effects.settings.value,
        p.linking.attempted,
        p.effects.episodes,
    ) == before
    assert calls == [] and companion[1] == [] and matter_devices[1] == []


@pytest.mark.parametrize(
    "received,heard", [(True, False), (False, True), (None, None), (True, True)]
)
async def test_observation_independent_fields_no_output_and_restart(
    hass, companion, received, heard
):
    entry, p, request, _, _ = await recorded(hass, companion)
    original = deepcopy(p.effects.settings.value)
    before = len(companion[1])
    evidence = p.phone_evidence
    await evidence.observe(
        request, evidence.revision, received, heard, True, lambda: True
    )
    row = evidence.snapshot()["requests"][0]
    assert row["current"] and row["observations"][-1] == {
        "at": row["observations"][-1]["at"],
        "received": received,
        "heard": heard,
        "simulation": True,
    }
    assert len(companion[1]) == before and p.effects.settings.value == original
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.panel.phone_evidence.snapshot()["requests"][0] == row
    assert entry.runtime_data.panel.effects.settings.value == original
    with pytest.raises(AutomationError, match="not_loaded"):
        await evidence.observe(
            request, evidence.revision, True, True, True, lambda: True
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sound", "US-EN-Alexa-Smoke-Detected-Generic.wav"),
        ("volume", 0.5),
        ("critical", False),
    ],
)
async def test_changed_profile_keeps_history_but_not_current(
    hass, companion, field, value
):
    _, p, request, profile, _ = await recorded(hass, companion)
    e = p.phone_evidence
    await e.observe(request, e.revision, True, True, True, lambda: True)
    profile[field] = value
    settings = deepcopy(p.effects.settings.value)
    settings["recipients"][0]["profile"] = profile
    await p.effects.settings.save(settings, p.effects.settings.revision, True)
    row = e.snapshot()["requests"][0]
    assert not row["current"] and row["reason"] == "phone_observation_old_profile"
    assert row["observations"][0]["heard"] and len(companion[1]) == 1


async def test_identity_missing_concurrency_and_missing_request(hass, companion):
    _, p, request, _, registration = await recorded(hass, companion)
    e = p.phone_evidence
    revision = e.revision
    results = await asyncio.gather(
        e.observe(request, revision, True, False, True, lambda: True),
        e.observe(request, revision, False, True, True, lambda: True),
        return_exceptions=True,
    )
    assert sum(isinstance(r, AutomationError) for r in results) == 1
    assert len(e.rows[0]["observations"]) == 1
    with pytest.raises(AutomationError, match="phone_request_missing"):
        await e.observe(uuid4().hex, e.revision, True, True, True, lambda: True)
    hass.config_entries.async_update_entry(
        registration, data={**registration.data, "device_id": "different"}
    )
    assert e.snapshot()["requests"][0]["reason"] == "phone_identity_changed"
    hass.services.async_remove("notify", "mobile_app_simulation_phone")
    assert e.snapshot()["requests"][0]["reason"] == "recipient_unavailable"


async def test_observation_authorization_payload_and_atomic_failure(
    hass, companion, hass_ws_client, hass_admin_user
):
    _, p, request, _, _ = await recorded(hass, companion)
    client = await hass_ws_client(hass)
    e = p.phone_evidence
    before = deepcopy(e.rows)
    msg = {
        "type": "alarmmesh/phone_observation",
        "request_id": request,
        "revision": e.revision,
        "received": True,
        "heard": True,
        "simulation": True,
    }
    await client.send_json({"id": 1, **msg, "target": "mobile_app_other"})
    assert not (await client.receive_json())["success"]
    hass_admin_user.groups = []
    await client.send_json({"id": 2, **msg})
    assert (await client.receive_json())["error"]["code"] == "unauthorized"
    await client.send_json({"id": 3, "type": "alarmmesh/alarm_settings"})
    assert (await client.receive_json())["error"]["code"] == "unauthorized"
    with patch.object(
        e.store, "async_save", AsyncMock(side_effect=OSError("simulated"))
    ):
        with pytest.raises(OSError):
            await e.observe(request, e.revision, True, True, True, lambda: True)
    assert e.rows == before and len(companion[1]) == 1


async def test_retention_bound_and_existing_installation_no_invented_evidence(
    hass, companion, freezer
):
    entry, p, request, _, _ = await recorded(hass, companion)
    e = p.phone_evidence
    for i in range(7):
        await e.observe(request, e.revision, bool(i % 2), None, True, lambda: True)
    assert len(e.rows[0]["observations"]) == 5
    sample = deepcopy(e.rows[0])
    values = [{**sample, "request_id": uuid4().hex} for _ in range(LIMIT + 10)]
    assert len(e._kept(values)) == LIMIT
    freezer.move_to(dt_util.utcnow() + timedelta(days=31))
    assert e.snapshot()["requests"] == []
    with pytest.raises(AutomationError, match="phone_request_missing"):
        await e.observe(request, e.revision, True, True, True, lambda: True)
    fresh = PhoneEvidence(hass, entry, p.effects, p.hub.publish)
    with patch.object(fresh.store, "async_load", AsyncMock(return_value=None)):
        await fresh.load()
    assert not fresh.rows and fresh.error is None


@pytest.mark.parametrize(
    "value", [{"schema": 9}, {"schema": 1, "revision": 0, "requests": [None]}]
)
async def test_damaged_evidence_never_overwrites_or_blocks_notifications(
    hass, companion, value
):
    _, p, _, _, _ = await recorded(hass, companion)
    e = p.phone_evidence
    with patch.object(e.store, "async_load", AsyncMock(return_value=value)):
        await e.load()
    with patch.object(e.store, "async_save", AsyncMock()) as save:
        request = uuid4().hex
        await p.effects.manual(
            "notification",
            "mobile_app_simulation_phone",
            p.effects.confirmation("mobile_app_simulation_phone", request),
            True,
            request,
        )
        assert (
            not save.called
            and e.error == "phone_evidence_storage"
            and len(companion[1]) == 2
        )


async def test_interrupted_request_reload_is_unknown_and_not_observable(
    hass, companion
):
    entry, p, request, _, _ = await recorded(hass, companion)
    e = p.phone_evidence
    value = {"schema": 1, "revision": e.revision, "requests": deepcopy(e.rows)}
    value["requests"][0].update(status="sending", attempted=False)
    restarted = PhoneEvidence(hass, entry, p.effects, p.hub.publish)
    with patch.object(restarted.store, "async_load", AsyncMock(return_value=value)):
        await restarted.load()
    assert restarted.rows[0]["status"] == "outcome_unknown"
    with pytest.raises(AutomationError, match="phone_request_missing"):
        await restarted.observe(
            request, restarted.revision, True, True, True, lambda: True
        )
    assert len(companion[1]) == 1


async def test_corrupt_evidence_never_marks_cached_observation_current(hass, companion):
    _, p, request, _, _ = await recorded(hass, companion)
    e = p.phone_evidence
    await e.observe(request, e.revision, True, True, True, lambda: True)
    with patch.object(e.store, "async_load", AsyncMock(side_effect=ValueError)):
        await e.load()
    row = e.snapshot()["requests"][0]
    assert not row["current"] and row["reason"] == "phone_evidence_storage"
    assert row["observations"][0]["received"]
    assert len(companion[1]) == 1


async def test_request_id_cannot_move_to_another_phone_after_restart(hass, companion):
    entry, p, request, _, _ = await recorded(hass, companion)
    await p.phone_evidence.observe(
        request, p.phone_evidence.revision, True, True, True, lambda: True
    )
    original = deepcopy(p.phone_evidence.rows)
    other = "mobile_app_other_simulation"
    other_calls = []

    async def output(call):
        other_calls.append(call)

    hass.services.async_register("notify", other, output)
    profile, _ = phone(hass, other, "ios")
    settings = deepcopy(p.effects.settings.value)
    settings["recipients"].append(
        {"service": other, "enabled": True, "profile": profile}
    )
    await p.effects.settings.save(settings, p.effects.settings.revision, True)
    assert await hass.config_entries.async_reload(entry.entry_id)
    current = entry.runtime_data.panel
    with pytest.raises(AutomationError, match="test_busy"):
        await current.effects.manual(
            "notification",
            other,
            current.effects.confirmation(other, request),
            True,
            request,
        )
    assert current.phone_evidence.rows == original
    assert other_calls == [] and len(companion[1]) == 1
