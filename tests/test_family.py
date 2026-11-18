from datetime import timedelta
from unittest.mock import patch

import pytest
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import A, new_entry
from test_incident_features import outputs as outputs
from test_linking_runtime import configure, setup
from test_notification_route import companion as companion

from homeassistant.util import dt as dt_util

from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.care import CareJournal
from custom_components.alarmmesh.preview import source_preview


async def test_journal_replay_after_reload_and_changed_identity(hass):
    entry = await new_entry(hass, (A,))
    journal = entry.runtime_data.panel.care
    row = dict(
        id="a" * 32, identity="b" * 64, date="2026-11-18", kind="battery", note=""
    )
    await journal.append(row, lambda: True)
    loaded = CareJournal(hass, entry)
    await loaded.load()
    await loaded.append(row, lambda: True)
    assert loaded.rows == [row]
    with pytest.raises(AutomationError):
        await loaded.append({**row, "identity": "c" * 64}, lambda: True)
    with pytest.raises(AutomationError):
        await loaded.append({**row, "id": "d" * 32}, lambda: False)


async def test_mobile_link_activity_survives_reload_and_new_incident(hass, companion):
    from test_incident_features import settle

    entry = await new_entry(hass, (A,))
    effects = entry.runtime_data.panel.effects
    await effects.settings.save(
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": "mobile_app_simulation_phone", "enabled": True}],
        },
        0,
        True,
    )
    for state in ("on", "off", "on"):
        hass.states.async_set(A, state, {"device_class": "smoke"})
        await settle(hass, entry)
    first, second = [msg["data"] for _, msg in companion[1]]
    assert first["url"] == first["clickAction"] != second["url"]
    assert await hass.config_entries.async_reload(entry.entry_id)
    events = entry.runtime_data.panel.activity.snapshot()["events"]
    history = [e for e in events if e["correlation"] == first["url"].split("=")[1]]
    assert any(e["kind"] == "incident_origin" and e["source"] == A for e in history)
    assert any(e["kind"] == "incident_clear" for e in history)
    with patch.object(
        dt_util, "utcnow", return_value=dt_util.utcnow() + timedelta(days=31)
    ):
        assert not entry.runtime_data.panel.activity.snapshot()["events"]


async def test_full_practice_routes_do_not_dispatch(hass, catalog_devices, outputs):
    add, buzzer_calls = catalog_devices
    attic, hall = (add("HS1SA-E-PLUS", "Heiman") for _ in range(2))
    a, b = attic["source"], hall["source"]
    entry = await setup(hass, [a, b])
    for _ in range(2):
        await configure(hass, entry, [a, b], [hall])
    panel = entry.runtime_data.panel
    phones = ["mobile_app_simulation_a", "mobile_app_simulation_b"]
    await panel.effects.settings.save(
        {
            "enabled": True,
            "recovery": False,
            "recipients": [{"service": phone, "enabled": True} for phone in phones],
        },
        0,
        True,
    )
    hass.services.async_remove("notify", phones[1])
    before = (list(buzzer_calls), list(outputs[0]))
    route = source_preview(panel, a)
    (target,) = route["targets"]
    assert target["eligible"] and len(target["via"]) == 2
    assert {
        row["target"]: row["reason"] for row in route["phones"] if row["selected"]
    } == {phones[0]: "preview_eligible", phones[1]: "recipient_unavailable"}
    combined = source_preview(panel, a, [b])
    assert all(
        row["reason"] == "preview_target_smoke" for row in combined["targets"][0]["via"]
    )
    assert source_preview(panel, a)["targets"] == route["targets"]
    assert (buzzer_calls, outputs[0]) == before


async def test_care_journal_requires_admin(hass, hass_ws_client):
    entry = await new_entry(hass, (A,))
    user = await hass.auth.async_create_user("Reader", group_ids=["system-users"])
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    await client.send_json(
        {
            "type": "alarmmesh/care",
            "id": 1,
            "source": A,
            "record": {
                "id": "a" * 32,
                "identity": "b" * 64,
                "date": "2026-11-18",
                "kind": "clean",
                "note": "",
            },
        }
    )
    assert (await client.receive_json())["error"]["code"] == "unauthorized"
    assert entry.runtime_data.panel.care.rows == []
