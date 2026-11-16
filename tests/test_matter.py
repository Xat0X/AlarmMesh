"""HA registry/lifecycle fixtures, no Matter Server or radio. Action I/O is mocked."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from test_activity_reminders import settle
from test_catalog import catalog_devices as catalog_devices
from test_incident_features import outputs as outputs
from test_linking_runtime import configure, setup

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh import matter
from custom_components.alarmmesh.automation import AutomationError
from custom_components.alarmmesh.catalog import CATALOG, recognize
from custom_components.alarmmesh.config_flow import _validate_sources
from custom_components.alarmmesh.diagnostics import support_report
from custom_components.alarmmesh.preview import group_preview


@pytest.fixture
def matter_devices(hass):
    calls = []

    def add(model="HS1SA-M", vendor="HEIMAN", *, endpoint=1, shared=None, bridge=False):
        config = (
            shared["config"] if shared else MockConfigEntry(domain="matter", data={})
        )
        if shared is None:
            config.add_to_hass(hass)
        root = (
            shared["root"]
            if shared
            else f"SIMULATED-{len(dr.async_get(hass).devices)}-"
            + ("3" if bridge else "MatterNodeDevice")
        )
        parent = None
        if bridge and shared is None:
            parent = dr.async_get(hass).async_get_or_create(
                config_entry_id=config.entry_id,
                identifiers={("matter", root + "-parent")},
            )
        device = (
            shared["device"]
            if shared
            else dr.async_get(hass).async_get_or_create(
                config_entry_id=config.entry_id,
                identifiers={("matter", "deviceid_" + root)},
                manufacturer=vendor,
                model=model,
                model_id="2" if model == "MSC-1" else None,
                sw_version="21",
                via_device_id=parent.id if parent else None,
            )
        )

        def register(
            domain,
            key,
            cluster,
            attribute,
            state="off",
            *,
            ep=endpoint,
            cls=None,
            translation=None,
        ):
            e = er.async_get(hass).async_get_or_create(
                domain,
                "matter",
                f"{root}-{ep}-{key}-{cluster}-{attribute}",
                config_entry=config,
                device_id=device.id,
                suggested_object_id=f"simulated_matter_{len(er.async_get(hass).entities)}",
                original_name="SIMULATED Matter detector",
                original_device_class=cls,
                translation_key=translation,
            )
            hass.states.async_set(
                e.entity_id, state, {"device_class": cls} if cls else {}
            )
            return e.entity_id

        source = register(
            "binary_sensor", "SmokeCoAlarmSmokeStateSensor", 92, 1, cls="smoke"
        )
        return {
            "source": source,
            "register": register,
            "config": config,
            "device": device,
            "root": root,
        }

    async def press(call):
        calls.append(call.data["entity_id"])

    hass.services.async_register("button", "press", press)
    return add, calls


@pytest.mark.parametrize(
    "model,vendor",
    [
        ("HS1SA-M", "HEIMAN"),
        ("S1-M", "HEIMAN"),
        ("MS-1", "SENSEREO LIMITED"),
        ("MSC-1", "SENSEREO LIMITED"),
        ("Unknown model", "Unknown vendor"),
    ],
)
async def test_matter_detection_without_optional_entities_or_transport_assumptions(
    hass, matter_devices, model, vendor
):
    add, calls = matter_devices
    d = add(model, vendor)
    entry = await setup(hass, [d["source"]])
    p = entry.runtime_data.panel
    assert "matter" not in hass.config.components
    cap = p.linking.capabilities.describe(d["source"])
    assert (
        cap["origin"] == "matter"
        and cap["status"] == "detection_only"
        and not cap["controls"]
    )
    assert cap["matter"]["transport"] == "unknown"
    assert cap["details"]["maintenance"] == {
        "battery_percent": None,
        "battery_low": None,
        "fault": None,
        "end_of_service": None,
    }
    assert p.selftests.resolve(d["source"]) is None and not calls
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED" and not calls


async def test_transport_uses_metadata_only_and_bridge_is_not_thread(
    hass, matter_devices
):
    add, _ = matter_devices
    d = add()
    d["register"](
        "sensor",
        "ThreadDiagnosticsRoutingRole",
        53,
        1,
        "DO_NOT_EXPORT_NETWORK_VALUE",
        ep=0,
    )
    assert matter.transport(hass, d["source"]) == "thread"
    d["register"]("sensor", "WiFiDiagnosticsRssi", 54, 4, "PRIVATE", ep=0)
    assert matter.transport(hass, d["source"]) == "unknown"
    bridge = add(bridge=True)
    bridge["register"]("sensor", "ThreadDiagnosticsRoutingRole", 53, 1, "PRIVATE", ep=0)
    assert matter.transport(hass, bridge["source"]) == "bridge"


@pytest.mark.parametrize("shared_device", [True, False])
async def test_same_names_wrong_endpoint_and_bridge_child_never_bind_test(
    hass, matter_devices, shared_device
):
    add, calls = matter_devices
    a = add(bridge=not shared_device)
    b = add(shared=a if shared_device else None, endpoint=2, bridge=not shared_device)
    b["register"](
        "button",
        "SmokeCoAlarmSelfTestRequest",
        92,
        65529,
        "unknown",
        translation="self_test_request",
    )
    b["register"](
        "binary_sensor",
        "SmokeCoAlarmHardwareFaultAlertSensor",
        92,
        6,
        "on",
        translation="hardware_fault",
    )
    entry = await setup(hass, [a["source"], b["source"]])
    p = entry.runtime_data.panel
    assert p.selftests.resolve(a["source"]) is None
    assert p.selftests.resolve(b["source"]) is not None
    assert p.linking.capabilities.details(a["source"])["maintenance"]["fault"] is None
    assert not calls


async def test_identity_replacement_blocks_across_reload_until_exact_review(
    hass, matter_devices, catalog_devices
):
    add, _ = matter_devices
    a = add()
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [a["source"], b["source"]])
    p = entry.runtime_data.panel
    await configure(hass, entry, [a["source"], b["source"]], [b])
    e = er.async_get(hass).async_get(a["source"])
    er.async_get(hass).async_update_entity(
        a["source"], new_unique_id=e.unique_id.replace("SIMULATED-", "REPLACEMENT-")
    )
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert matter.identity_changed(hass, a["source"]) and not catalog_devices[1]
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await settle(hass, entry)
    p = entry.runtime_data.panel
    assert matter.identity_changed(hass, a["source"]) and not catalog_devices[1]
    current = matter.fingerprint(hass, a["source"])
    with pytest.raises(AutomationError):
        await p.matter_sources.review(a["source"], current, False, True)
    with pytest.raises(AutomationError):
        await p.matter_sources.review(a["source"], current, 0, False)
    await p.matter_sources.review(a["source"], current, p.matter_sources.revision, True)
    p.linking.changed()
    await settle(hass, entry)
    assert len(catalog_devices[1]) == 1


async def test_mixed_matter_origins_and_overlapping_groups_dedup(
    hass, matter_devices, catalog_devices
):
    a = matter_devices[0]()
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    c = catalog_devices[0](
        "SMSZB-120",
        "frient A/S",
        origin="zha",
        domain="siren",
        key="sounder",
        idle="off",
        attrs={"supported_features": 17},
    )
    entry = await setup(hass, [a["source"], b["source"], c["source"]])
    p = entry.runtime_data.panel
    g = await configure(hass, entry, [a["source"], b["source"]], [b])
    await configure(hass, entry, [a["source"], b["source"], c["source"]], [b, c])
    example = group_preview(p, g, a["source"])
    assert example["targets"][0]["eligible"] and not catalog_devices[1]
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(catalog_devices[1]) == 2
    for _ in range(3):
        p.linking.changed()
    await settle(hass, entry)
    assert len(catalog_devices[1]) == 2
    assert not p.linking.capabilities.describe(a["source"])["controls"]
    hass.states.async_set(a["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    hass.states.async_set(a["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert (
        len(
            [
                r
                for r in catalog_devices[1]
                if r[1] == "turn_on" or r[2].get("option") == "smoke_siren"
            ]
        )
        == 3
    )


async def test_interconnect_is_visible_not_independent_and_co_is_not_smoke(
    hass, matter_devices, catalog_devices
):
    d = matter_devices[0]("MSC-1", "SENSEREO LIMITED")
    forwarded = d["register"](
        "binary_sensor",
        "SmokeCoAlarmInterconnectSmokeAlarmSensor",
        92,
        8,
        cls="smoke",
        translation="interconnected_smoke_alarm",
    )
    co = d["register"](
        "binary_sensor", "SmokeCoAlarmCOStateSensor", 92, 2, cls="carbon_monoxide"
    )
    assert _validate_sources(hass, [co]) == "wrong_device_class"
    er.async_get(hass).async_update_entity(co, device_class="smoke")
    assert _validate_sources(hass, [co]) == "wrong_device_class"
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [d["source"], forwarded, b["source"]])
    p = entry.runtime_data.panel
    await configure(hass, entry, [d["source"], forwarded, b["source"]], [b])
    hass.states.async_set(forwarded, "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert (
        entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
        and forwarded not in p.linking.active
        and not catalog_devices[1]
    )
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(catalog_devices[1]) == 1
    hass.states.async_set(d["source"], "off", {"device_class": "smoke"})
    await settle(hass, entry)
    assert (
        len(catalog_devices[1]) == 2
        and entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    )


async def test_known_native_interlink_without_separation_blocks_only_execution(
    hass, matter_devices, catalog_devices
):
    d = matter_devices[0]("MS-1 Interlink", "Sensereo")
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [d["source"], b["source"]])
    await configure(hass, entry, [d["source"], b["source"]], [b])
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert (
        entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
        and not catalog_devices[1]
    )
    assert (
        entry.runtime_data.panel.linking.capabilities.describe(d["source"])["reason"]
        == "matter_interconnect_unseparated"
    )


@pytest.mark.parametrize("result", ["finish", "timeout", "fail", "smoke", "remove"])
async def test_matter_selftest_request_scoping_real_smoke_and_no_fake_success(
    hass, matter_devices, result, freezer
):
    add, calls = matter_devices
    d = add()
    button = d["register"](
        "button",
        "SmokeCoAlarmSelfTestRequest",
        92,
        65529,
        "unknown",
        translation="self_test_request",
    )
    flag = d["register"](
        "binary_sensor",
        "SmokeCoAlarmTestInProgressSensor",
        92,
        5,
        translation="test_in_progress",
    )
    d["register"]("button", "IdentifyButton", 3, 0, "unknown")
    entry = await setup(hass, [d["source"]])
    p = entry.runtime_data.panel
    s = p.selftests
    control = s.resolve(d["source"])
    assert (
        control and control["target"] == button and not control["has_explicit_result"]
    )
    with pytest.raises(AutomationError):
        await s.start(d["source"], control["identity"], False, request_id=uuid4().hex)
    assert not calls
    if result == "fail":
        with patch.object(
            type(hass.services),
            "async_call",
            AsyncMock(side_effect=RuntimeError("SIMULATED failed button")),
        ):
            record = await s.start(
                d["source"], control["identity"], True, request_id=uuid4().hex
            )
        assert record["status"] == "failed"
        return
    await s.start(d["source"], control["identity"], True, request_id=uuid4().hex)
    assert calls == [button] and s.record["status"] == "request_sent"
    hass.states.async_set(flag, "on")
    await settle(hass, entry)
    assert s.record["status"] == "test_active"
    assert not p.linking.active
    if result == "smoke":
        hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
        await settle(hass, entry)
        assert (
            entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
            and d["source"] in p.linking.active
        )
    elif result == "remove":
        er.async_get(hass).async_remove(button)
        await settle(hass, entry)
        assert s.record["status"] == "outcome_unknown"
    elif result == "timeout":
        freezer.tick(timedelta(seconds=121))
        async_fire_time_changed(hass, dt_util.utcnow())
        await settle(hass, entry)
        assert s.record["status"] == "outcome_unknown"
    else:
        hass.states.async_set(flag, "off")
        await settle(hass, entry)
        assert s.record["status"] == "outcome_unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert s.closed and not s.tasks and not s.requests


async def test_matter_maintenance_activity_diagnosis_no_network_values(
    hass, matter_devices, outputs
):
    d = matter_devices[0]("MSC-1", "SENSEREO LIMITED")
    percent = d["register"]("sensor", "PowerSource", 47, 12, "72", cls="battery")
    hass.states.async_set(
        percent, "72", {"device_class": "battery", "unit_of_measurement": "%"}
    )
    eos = d["register"](
        "binary_sensor",
        "SmokeCoAlarmEndfOfServiceSensor",
        92,
        7,
        cls="problem",
        translation="end_of_service",
    )
    d["register"](
        "binary_sensor",
        "SmokeCoAlarmHardwareFaultAlertSensor",
        92,
        6,
        cls="problem",
        translation="hardware_fault",
    )
    d["register"](
        "sensor", "ThreadDiagnosticsRoutingRole", 53, 1, "PRIVATE_NETWORK_VALUE", ep=0
    )
    entry = await setup(hass, [d["source"]])
    p = entry.runtime_data.panel
    health = p.linking.capabilities.details(d["source"])["maintenance"]
    assert (
        health["battery_percent"] == 72
        and health["fault"] is False
        and health["end_of_service"] is False
    )
    hass.states.async_set(eos, "on")
    await settle(hass, entry)
    assert any(
        r["kind"] == "end_of_service" and r["result"] == "problem"
        for r in p.activity.rows
    )
    report = support_report(p.snapshot(), "0.1.0-beta.7", "2026.11.1")
    import json

    assert "PRIVATE_NETWORK_VALUE" not in json.dumps(report) and d[
        "root"
    ] not in json.dumps(report)
    assert (
        report["sources"][0]["provider"] == "matter"
        and report["sources"][0]["transport"] == "thread"
    )
    assert report["sources"][0]["end_of_service"] is True and not outputs[0]


def test_matter_catalog_keeps_models_variants_and_authority_separate():
    assert len(CATALOG["matter_entries"]) == 5
    assert recognize("matter", "HS1SA-E-PLUS", "HEIMAN") is None
    assert recognize("matter", "S1-M", "HEIMAN")["model"] == "S1-M"
    assert recognize("matter", "MS1", "SENSEREO LIMITED")["product_id"] == 1
    assert (
        recognize("matter", "MS-1 Interlink", "Sensereo")["id"]
        != recognize("matter", "MS-1", "Sensereo")["id"]
    )


async def test_saved_co_only_selection_never_becomes_smoke(hass, matter_devices):
    d = matter_devices[0]("MSC-1", "SENSEREO LIMITED")
    co = d["register"](
        "binary_sensor", "SmokeCoAlarmCOStateSensor", 92, 2, "on", cls="carbon_monoxide"
    )
    entry = await setup(
        hass, [co]
    )  # Deliberately invalid old/saved options, no new flow.
    await settle(hass, entry)
    assert entry.runtime_data.result.smoke_status.name == "INDETERMINATE"
    assert entry.runtime_data.source_statuses[co].name == "UNKNOWN"


async def test_matter_device_identifier_replacement_requires_review(
    hass, matter_devices
):
    d = matter_devices[0]()
    entry = await setup(hass, [d["source"]])
    dr.async_get(hass).async_update_device(
        d["device"].id, new_identifiers={("matter", "SIMULATED_REPLACEMENT_DEVICE")}
    )
    await settle(hass, entry)
    assert matter.identity_changed(hass, d["source"])
    assert not matter.origin_allowed(hass, d["source"])


async def test_matter_corrupt_pin_storage_blocks_execution_not_current_smoke(
    hass, matter_devices
):
    d = matter_devices[0]()
    original_load = matter.Store.async_load

    async def corrupt_only_matter(store):
        if store.key.startswith("alarmmesh.matter_sources."):
            return {"schema": 999}
        return await original_load(store)

    with patch.object(matter.Store, "async_load", corrupt_only_matter):
        entry = await setup(hass, [d["source"]])
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    p = entry.runtime_data.panel
    assert p.matter_sources.error == "matter_identity_storage_error"
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    assert d["source"] not in p.linking.active
    with pytest.raises(AutomationError, match="matter_identity_storage_error"):
        await p.matter_sources.review(
            d["source"], matter.fingerprint(hass, d["source"]), 0, True
        )


async def test_matter_optional_values_unknown_and_control_replacement_fail_closed(
    hass, matter_devices
):
    d, calls = matter_devices[0](), matter_devices[1]
    target = d["register"](
        "button", "SmokeCoAlarmSelfTestRequest", 92, 65529, "unknown"
    )
    fault = d["register"](
        "binary_sensor", "SmokeCoAlarmHardwareFaultAlertSensor", 92, 6, "unknown"
    )
    battery = d["register"]("sensor", "PowerSource", 47, 12, "invalid", cls="battery")
    eos = d["register"](
        "binary_sensor", "SmokeCoAlarmEndfOfServiceSensor", 92, 7, "unavailable"
    )
    entry = await setup(hass, [d["source"]])
    p = entry.runtime_data.panel
    assert p.linking.capabilities.details(d["source"])["maintenance"] == {
        "battery_percent": None,
        "battery_low": None,
        "fault": None,
        "end_of_service": None,
    }
    control = p.selftests.resolve(d["source"])
    assert control
    e = er.async_get(hass).async_get(target)
    er.async_get(hass).async_update_entity(
        target, new_unique_id=e.unique_id.replace("-1-", "-2-")
    )
    await settle(hass, entry)
    with pytest.raises(AutomationError):
        await p.selftests.start(
            d["source"], control["identity"], True, request_id=uuid4().hex
        )
    assert not calls
    for entity_id in (fault, battery, eos):
        hass.states.async_remove(entity_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert p.matter_sources.closed


async def test_matter_review_websocket_requires_admin_exact_identity_and_revision(
    hass, matter_devices, hass_ws_client
):
    d = matter_devices[0]()
    entry = await setup(hass, [d["source"]])
    guard = entry.runtime_data.panel.matter_sources
    user = await hass.auth.async_create_user(
        "Simulation reader", group_ids=["system-users"]
    )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id="https://example.com"
    )
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    message = {
        "id": 1,
        "type": "alarmmesh/matter_review",
        "source": d["source"],
        "identity": matter.fingerprint(hass, d["source"]),
        "revision": guard.revision,
        "confirmed": True,
    }
    await client.send_json(message)
    result = await client.receive_json()
    assert not result["success"] and result["error"]["code"] == "unauthorized"
    admin = await hass_ws_client(hass)
    for i, invalid in enumerate(
        (
            {"revision": guard.revision + 1},
            {"identity": "f" * 64},
            {"confirmed": False},
        ),
        1,
    ):
        await admin.send_json({**message, "id": i, **invalid})
        assert not (await admin.receive_json())["success"]
    assert guard.revision == message["revision"]
    assert not matter_devices[1]


async def test_lost_interconnect_evidence_blocks_dispatch_without_false_clear(
    hass, matter_devices, catalog_devices
):
    d = matter_devices[0]("MS-1 Interlink", "Sensereo")
    forwarded = d["register"](
        "binary_sensor", "SmokeCoAlarmInterconnectSmokeAlarmSensor", 92, 8, cls="smoke"
    )
    b = catalog_devices[0]("HS1SA-E-PLUS", "Heiman")
    entry = await setup(hass, [d["source"], b["source"]])
    await configure(hass, entry, [d["source"], b["source"]], [b])
    p = entry.runtime_data.panel
    hass.states.async_set(d["source"], "on", {"device_class": "smoke"})
    await settle(hass, entry)
    assert len(catalog_devices[1]) == 1
    er.async_get(hass).async_remove(forwarded)
    await settle(hass, entry)
    assert (
        d["source"] in p.linking.active
    )  # Unknown provenance is not a smoke-free report.
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    control, reason = p.linking.assess(p.linking._plan()[0])
    assert control is None and reason == "preview_origin_blocked"
    assert len(catalog_devices[1]) == 1  # No repeat, and no false stop.


async def test_panel_displays_matter_model_name_instead_of_numeric_product_id(
    hass, matter_devices
):
    add, calls = matter_devices
    device = add("MSC-1", "SENSEREO LIMITED")
    entry = await setup(hass, [device["source"]])
    rows = entry.runtime_data.panel.snapshot()["sources"]
    row = next(row for row in rows if row["entity_id"] == device["source"])
    assert row["model"] == "MSC-1"
    assert dr.async_get(hass).async_get(device["device"].id).model_id == "2"
    assert not calls
