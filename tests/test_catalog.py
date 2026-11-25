"""Reviewed contracts with real HA registries, mocked actions; no driver claims."""

import asyncio
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_linking_runtime import configure, flush, setup

from homeassistant.components.siren import SirenEntityFeature
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.capabilities import Capabilities
from custom_components.alarmmesh.catalog import CATALOG, recognize, validate_catalog
from custom_components.alarmmesh.linking import plan_activations
from custom_components.alarmmesh.profiles import PROFILES, Profile, validate_profiles


async def test_real_ha_siren_feature_enum_is_a_valid_bitmask(hass, catalog_devices):
    add, calls = catalog_devices
    device = add(
        "SMSZB-120",
        "Develco",
        domain="siren",
        key="warning",
        idle="off",
        attrs={
            "supported_features": SirenEntityFeature.TURN_ON
            | SirenEntityFeature.TONES
            | SirenEntityFeature.DURATION,
            "available_tones": ["burglar"],
        },
    )
    assert Capabilities(hass).describe(device["source"])["status"] == "linkable"
    assert not calls


@pytest.fixture
def catalog_devices(hass):
    """Independent input/output contracts, not generated from the catalog."""
    calls = []

    async def command(call):
        calls.append((call.domain, call.service, dict(call.data)))
        target = call.data["entity_id"]
        hass.states.async_set(
            target,
            call.data.get("option", "off" if call.service == "turn_off" else "on"),
            dict(hass.states.get(target).attributes),
            context=call.context,
        )

    for domain, service in (
        ("select", "select_option"),
        ("switch", "turn_on"),
        ("siren", "turn_on"),
        ("siren", "turn_off"),
        ("switch", "turn_off"),
    ):
        hass.services.async_register(domain, service, command)

    def add(
        model,
        vendor,
        origin="mqtt",
        domain="select",
        key="siren_for_automation_only",
        attrs=None,
        idle="stop",
        gate=None,
    ):
        index = len(dr.async_get(hass).devices)
        entry = MockConfigEntry(domain=origin, data={})
        entry.add_to_hass(hass)
        identifier = f"mock{index}"
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={
                (
                    origin,
                    f"zigbee2mqtt_{identifier}" if origin == "mqtt" else identifier,
                )
            },
            manufacturer=vendor,
            model_id=model,
            model=model,
        )

        def register(domain, prop, state, attrs, cls=None):
            entity = er.async_get(hass).async_get_or_create(
                domain,
                origin,
                f"{identifier}_{prop}_zigbee2mqtt"
                if origin == "mqtt"
                else f"{identifier}-{prop}",
                config_entry=entry,
                device_id=device.id,
                suggested_object_id=f"catalog_{index}_{prop}",
                translation_key=prop if origin == "zha" else None,
                original_device_class=cls,
            )
            hass.states.async_set(entity.entity_id, state, attrs)
            return entity.entity_id

        if (vendor, model, origin) == ("Alecto", "SMART-SMOKE10", "mqtt"):
            source = register("sensor", "smoke_state", "normal", {})
        else:
            source = register(
                "binary_sensor", "smoke", "off", {"device_class": "smoke"}, "smoke"
            )
        target = register(
            domain,
            key,
            idle,
            attrs
            if attrs is not None
            else {"options": ["stop", "smoke_siren", "co_siren"]},
        )
        setting = (
            register(gate[0], gate[1], gate[2] if len(gate) == 3 else "on", {})
            if gate
            else None
        )
        return {
            "source": source,
            "target": target,
            "setting": setting,
            "device": device.id,
            "register": register,
        }

    return add, calls


async def test_alecto_selection_requires_the_registered_z2m_smoke_property(
    hass, catalog_devices
):
    from custom_components.alarmmesh.config_flow import _validate_sources
    from custom_components.alarmmesh.runtime import current_source_status
    from custom_components.alarmmesh.status import SourceStatus

    add, calls = catalog_devices
    alecto = add("SMART-SMOKE10", "Alecto")
    source = alecto["register"]("sensor", "smoke_state", "normal", {})
    registry = er.async_get(hass)
    renamed = registry.async_update_entity(
        source, new_entity_id="sensor.simulated_renamed"
    ).entity_id
    hass.states.async_set(renamed, "alarm")
    assert _validate_sources(hass, [renamed]) is None
    assert current_source_status(hass, renamed) is SourceStatus.SMOKE_REPORTED

    unrelated = [
        alecto["register"]("sensor", "smoke_value", "alarm", {}),
        add("SMART-SMOKE10", "Other")["register"]("sensor", "smoke_state", "alarm", {}),
        add("Other", "Alecto")["register"]("sensor", "smoke_state", "alarm", {}),
        add("SMART-SMOKE10", "Alecto", "zha")["register"](
            "sensor", "smoke_state", "alarm", {}
        ),
    ]
    for entity_id in unrelated:
        assert _validate_sources(hass, [entity_id]) == "wrong_domain"
        assert current_source_status(hass, entity_id) is SourceStatus.UNKNOWN
    registry.async_update_entity(renamed, disabled_by=er.RegistryEntryDisabler.USER)
    assert _validate_sources(hass, [renamed]) == "wrong_domain"
    assert current_source_status(hass, renamed) is SourceStatus.UNKNOWN
    assert not calls


async def test_replace_unavailable_tuya_source_with_offline_alecto(
    hass, catalog_devices
):
    from homeassistant.data_entry_flow import FlowResultType

    from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS
    from custom_components.alarmmesh.status import SourceStatus

    add, calls = catalog_devices
    previous = add("Legacy smoke", "Simulation", "tuya")["source"]
    replacement = add("SMART-SMOKE10", "Alecto")["source"]
    hass.states.async_set(previous, "unavailable", {"device_class": "smoke"})
    hass.states.async_set(replacement, "unavailable")
    entry = await setup(hass, [previous])
    options = hass.config_entries.options
    form = await options.async_init(entry.entry_id)
    field = next(iter(form["data_schema"].schema.values()))
    assert {previous, replacement} <= set(field.config["include_entities"])
    assert entry.runtime_data.source_entity_ids == (previous,)
    result = await options.async_configure(
        form["flow_id"], {CONF_SOURCE_ENTITY_IDS: [replacement]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.runtime_data.source_statuses == {replacement: SourceStatus.UNREACHABLE}
    hass.states.async_set(replacement, "normal")
    await hass.async_block_till_done()
    assert entry.runtime_data.source_statuses == {
        replacement: SourceStatus.NO_SMOKE_REPORTED
    }
    assert not calls
    assert await hass.config_entries.async_unload(entry.entry_id)


def test_catalog_complete_generated_and_provider_specific():
    validate_catalog(CATALOG)
    snapshot = json.loads(Path("dev/catalog/review.json").read_text(encoding="utf-8"))
    from dev.catalog.build import render

    assert Path("custom_components/alarmmesh/catalog_data.py").read_text(
        encoding="utf-8"
    ) == render(snapshot)
    assert CATALOG == snapshot
    assert CATALOG["definitions"] == 53 and CATALOG["website_rows"] == 68
    assert CATALOG["variants"] == 15
    for entry in CATALOG["entries"]:
        for alias in entry["aliases"]:
            assert set(alias["providers"]) == {"zigbee2mqtt", "zha"}
            assert alias["providers"]["zha"]["activation"] == "unconfirmed"
            assert alias["providers"]["zha"]["profile"] is None
    for entry in CATALOG["entries"]:
        assert entry["providers"]["zigbee2mqtt"]["sources"]
        assert entry["providers"]["zha"]["sources"]
        assert entry["physical_tested"] is False
    assert recognize("zigbee2mqtt", "94430", "Frient")["model"] == "SMSZB-120"
    assert recognize("zha", "94430", "frient A/S") is None
    assert recognize("zha", "TS0601", "_TZE200_aycxwiau")["model"] == "R7049"
    assert recognize("zha", "TS0601", "_UNKNOWN_manufacturer") is None
    assert recognize("zha", "TS0601", "Tuya") is None
    assert recognize("zigbee2mqtt", "HS1SA-E-PLUS", "unrelated") is None


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "missing_provider", "dangling_profile", "stop", "physical", "count"],
)
def test_catalog_rejects_incomplete_or_expanded_authority(mutation):
    data = deepcopy(CATALOG)
    first = data["entries"][0]
    if mutation == "duplicate":
        data["entries"][1]["id"] = first["id"]
    elif mutation == "missing_provider":
        first["providers"].pop("zha")
    elif mutation == "dangling_profile":
        first["providers"]["zha"]["profile"] = "invented"
    elif mutation == "stop":
        first["providers"]["zha"]["stop"] = "implemented"
    elif mutation == "physical":
        first["physical_tested"] = True
    else:
        data["website_rows"] += 1
    with pytest.raises(ValueError):
        validate_catalog(data)


def test_stop_is_limited_to_the_reviewed_models_and_external_tone(monkeypatch):
    stops = {
        (provider, model["model"])
        for model in CATALOG["entries"]
        for provider, review in model["providers"].items()
        if review["stop"] == "implemented"
    }
    assert stops == {
        ("zigbee2mqtt", model)
        for model in (
            "HS1SA-E-PLUS",
            "HS1SA-E Lover",
            "HM-636THV-AC-M",
            "S1-M",
            "S1-TL",
            "S1-TL-AI",
            "S2-E",
        )
    }
    monkeypatch.setitem(
        PROFILES,
        "heiman_cascade_mqtt",
        replace(PROFILES["heiman_cascade_mqtt"], key="temporary_mute"),
    )
    with pytest.raises(ValueError, match="stop authority"):
        validate_profiles()


def test_legacy_contract_does_not_silently_expand(monkeypatch):
    validate_profiles()
    monkeypatch.setitem(
        PROFILES,
        "heiman_mqtt",
        Profile("zigbee2mqtt", "select", option="co_siren", legacy_identity=True),
    )
    with pytest.raises(ValueError, match="legacy authority"):
        validate_profiles()


CASES = (
    (
        "S1-M",
        "Heiman",
        "mqtt",
        "select",
        "siren_for_automation_only",
        "stop",
        {"options": ["stop", "smoke_siren", "co_siren"]},
        None,
        "heiman_cascade_mqtt",
        {"option": "smoke_siren"},
    ),
    (
        "HS1SA-EF-3.0",
        "HEIMAN",
        "zha",
        "siren",
        "sounder",
        "off",
        {"supported_features": 17},
        None,
        "basic_ias_zha",
        {"duration": 60},
    ),
    (
        "lumi.sensor_smoke.acn03",
        "LUMI",
        "zha",
        "switch",
        "buzzer_manual_alarm",
        "off",
        {},
        ("switch", "linkage_alarm"),
        "aqara_zha",
        {},
    ),
    (
        "SD-8SCZBS",
        "Climax",
        "mqtt",
        "siren",
        "sounder",
        "off",
        {"supported_features": 21, "available_tones": ["burglar"]},
        None,
        "ias_mqtt",
        {"tone": "burglar", "duration": 60},
    ),
    (
        "SD8SC_00.00.03.12TC",
        "Climax",
        "zha",
        "siren",
        "sounder",
        "off",
        {"supported_features": 21, "available_tones": ["Burglar"]},
        None,
        "ias_zha",
        {"tone": "Burglar", "duration": 60},
    ),
    (
        "SMSZB-120",
        "Develco",
        "mqtt",
        "siren",
        "sounder",
        "off",
        {"supported_features": 21, "available_tones": ["burglar"]},
        None,
        "smszb_mqtt",
        {"tone": "burglar", "duration": 60},
    ),
    (
        "SMSZB-120",
        "Develco",
        "zha",
        "siren",
        "sounder",
        "off",
        {"supported_features": 17},
        None,
        "smszb_zha",
        {"duration": 60},
    ),
    (
        "8750001213",
        "Bosch",
        "mqtt",
        "select",
        "alarm",
        "stop",
        {"options": ["stop", "pre_alarm", "fire", "burglar"]},
        None,
        "bosch_twinguard_mqtt",
        {"option": "fire"},
    ),
    (
        "BSD-2",
        "Bosch",
        "mqtt",
        "siren",
        "alarm_control",
        "off",
        {"supported_features": 5, "available_tones": ["smoke", "burglar"]},
        ("switch", "broadcast_alarms", "off"),
        "bosch_bsd_mqtt",
        {"tone": "smoke"},
    ),
    (
        "FAM-300Z",
        "ShinaSystem",
        "mqtt",
        "switch",
        "force_smoke_alarm",
        "off",
        {},
        ("binary_sensor", "remote_control_permission"),
        "shina_mqtt",
        {},
    ),
)


@pytest.mark.parametrize("case", CASES, ids=[case[-2] for case in CASES])
async def test_adapter_commands_and_reviewed_stop(hass, catalog_devices, case):
    add, calls = catalog_devices
    model, vendor, origin, domain, key, idle, attrs, gate, profile, expected = case
    target = add(model, vendor, origin, domain, key, attrs, idle, gate)
    source = add("Unknown", "Simulation")
    entry = await setup(hass, [target["source"], source["source"]])
    info = Capabilities(hass).describe(target["source"])
    assert info["status"] == "linkable" and info["controls"][0]["profile"] == profile
    can_stop = profile == "heiman_cascade_mqtt"
    assert info["controls"][0]["safe_stop"] is can_stop
    assert not calls  # Discovery, setup and snapshots never actuate.
    await configure(hass, entry, [target["source"], source["source"]], [target])
    hass.states.async_set(source["source"], "on")
    await flush(hass, entry)
    assert calls == [
        (
            domain,
            "select_option" if domain == "select" else "turn_on",
            {"entity_id": target["target"], **expected},
        )
    ]
    # Local smoke on a sounding target takes priority over any linked stop.
    hass.states.async_set(target["source"], "on")
    await flush(hass, entry)
    hass.states.async_set(source["source"], "on", {"extra": "repeat"})
    hass.states.async_set(source["source"], "off")
    await flush(hass, entry)
    assert len(calls) == 1
    hass.states.async_set(target["source"], "off")
    await flush(hass, entry)
    assert calls[1:] == (
        [("select", "select_option", {"entity_id": target["target"], "option": "stop"})]
        if can_stop
        else []
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_s1m_saved_start_only_binding_requires_review(
    hass, catalog_devices, monkeypatch
):
    add, calls = catalog_devices
    target = add(
        "S1-M",
        "Heiman",
        key="siren_for_automation_only",
        idle="stop",
        attrs={"options": ["smoke_siren", "stop"]},
    )
    source = add("Unknown", "Simulation")
    members = [source["source"], target["source"]]
    entry = await setup(hass, members)
    panel = entry.runtime_data.panel
    with monkeypatch.context() as old:
        review = recognize("zigbee2mqtt", "S1-M", "Heiman")["providers"]["zigbee2mqtt"]
        old.setitem(review, "profile", "heiman_activation_mqtt")
        old.setitem(
            PROFILES,
            "heiman_activation_mqtt",
            replace(PROFILES["heiman_cascade_mqtt"], safe_stop=False),
        )
        await configure(hass, entry, members, [target])
        binding = dict(panel.groups.groups[0]["linking"]["bindings"][0])
    assert panel.linking.capabilities.resolve(binding) is None
    hass.states.async_set(source["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    hass.states.async_set(source["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert not calls
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_new_select_never_adopts_manual_fire_or_burglar(hass, catalog_devices):
    add, calls = catalog_devices
    target = add(
        "8750001213",
        "Bosch",
        key="alarm",
        idle="burglar",
        attrs={"options": ["stop", "fire", "burglar"]},
    )
    source = add("Unknown", "Simulation")
    entry = await setup(hass, [source["source"], target["source"]])
    await configure(hass, entry, [source["source"], target["source"]], [target])
    hass.states.async_set(source["source"], "on")
    await flush(hass, entry)
    assert not calls and not entry.runtime_data.panel.linking.owned
    assert (
        entry.runtime_data.panel.linking.records[target["target"]]["status"]
        == "already_active"
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_prerequisites_firmware_features_and_identity(hass, catalog_devices):
    add, calls = catalog_devices
    d = add(
        "lumi.sensor_smoke.acn03",
        "LUMI",
        "zha",
        "switch",
        "buzzer_manual_alarm",
        {},
        "off",
        ("switch", "linkage_alarm"),
    )
    cap = Capabilities(hass)
    control = cap.describe(d["source"])["controls"][0]
    saved = {k: control[k] for k in ("source", "target", "profile", "identity")}
    for value in ("off", "unknown", "unavailable"):
        hass.states.async_set(d["setting"], value)
        assert cap.resolve(saved) is None
    hass.states.async_set(d["setting"], "on")
    dr.async_get(hass).async_update_device(d["device"], sw_version="21")
    assert cap.resolve(saved) is None
    dr.async_get(hass).async_update_device(d["device"], sw_version="other")
    registry = er.async_get(hass)
    old = registry.async_get(d["target"])
    registry.async_update_entity(d["target"], new_entity_id="switch.renamed_simulation")
    hass.states.async_set("switch.renamed_simulation", "off")
    renamed = cap.describe(d["source"])["controls"][0]
    assert renamed["identity"] == saved["identity"]
    assert cap.resolve(saved) is None  # Stored mapping uses the fixed selected ID.
    registry.async_update_entity(renamed["target"], new_unique_id="replacement")
    assert cap.describe(d["source"])["controls"][0]["identity"] != saved["identity"]
    assert cap.resolve({**saved, "target": renamed["target"]}) is None
    assert not calls and old.unique_id


@pytest.mark.parametrize(
    "attrs",
    [
        {"supported_features": 1},
        {"supported_features": True},
        {"supported_features": 5, "available_tones": ["burglar"]},
    ],
)
async def test_bosch_never_guesses_tone_or_duration(hass, catalog_devices, attrs):
    add, calls = catalog_devices
    d = add(
        "BSD-2", "Bosch", domain="siren", key="alarm_control", attrs=attrs, idle="off"
    )
    assert Capabilities(hass).describe(d["source"])["controls"] == []
    assert not calls


async def test_cached_diagnostics_never_infer_contact_and_keep_test_separate(
    hass, catalog_devices
):
    add, calls = catalog_devices
    d = add("S1-M", "Heiman")
    d["register"]("sensor", "battery", "72", {"unit_of_measurement": "%"})
    d["register"]("binary_sensor", "fault_state", "off", {})
    test = d["register"]("binary_sensor", "test", "on", {})
    cap = Capabilities(hass)
    before = cap.details(d["source"])
    assert before["recent_contact"] is None
    assert next(v for v in before["values"] if v["key"] == "battery")["value"] == 72
    assert all(v["changed_at"] for v in before["values"])
    entry = await setup(hass, [d["source"]])
    hass.states.async_set(d["source"], "on")
    await flush(hass, entry)
    assert (
        not entry.runtime_data.panel.linking.active
    )  # Known self-test cannot initiate.
    assert entry.runtime_data.source_statuses[d["source"]].name == "SMOKE_REPORTED"
    hass.states.async_set(test, "off")
    await flush(hass, entry)
    assert not entry.runtime_data.panel.linking.active and not calls
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_published_binding_fingerprint_remains_unchanged(hass, catalog_devices):
    add, _ = catalog_devices
    d = add("HS1SA-E-PLUS", "Heiman")
    entities = er.async_get(hass)
    source, target = entities.async_get(d["source"]), entities.async_get(d["target"])
    old = hashlib.sha256(
        json.dumps(
            [
                source.unique_id,
                source.config_entry_id,
                target.unique_id,
                target.config_entry_id,
                d["device"],
                "zigbee2mqtt",
                "hs1sa-e-plus",
                "heiman",
                "heiman_mqtt",
            ]
        ).encode()
    ).hexdigest()
    assert Capabilities(hass).describe(d["source"])["controls"][0]["identity"] == old


@pytest.mark.parametrize(
    "model,vendor,prop,active,cleared",
    [
        ("228WZH", "Tuya", "self_test", "Checking", "Check success"),
        ("R7049", "Woox", "test_alarm_result", "checking", "check_success"),
        ("BSD-2", "Bosch", "test_mode", "on", "off"),
    ],
)
async def test_read_only_test_flags_are_not_test_commands(
    hass, catalog_devices, model, vendor, prop, active, cleared
):
    add, calls = catalog_devices
    d = add(model, vendor)
    entity = d["register"]("sensor", prop, active, {})
    cap = Capabilities(hass)
    assert cap.test_blocked(d["source"])
    hass.states.async_set(entity, cleared)
    assert not cap.test_blocked(d["source"])
    assert not calls


async def test_cross_entry_control_and_permission_replacement_fail_closed(
    hass, catalog_devices
):
    add, calls = catalog_devices
    d = add(
        "FAM-300Z",
        "ShinaSystem",
        domain="switch",
        key="force_smoke_alarm",
        idle="off",
        attrs={},
        gate=("binary_sensor", "remote_control_permission"),
    )
    cap = Capabilities(hass)
    control = cap.describe(d["source"])["controls"][0]
    binding = {k: control[k] for k in ("source", "target", "profile", "identity")}
    er.async_get(hass).async_update_entity(
        d["setting"], new_unique_id="replaced_permission"
    )
    assert cap.resolve(binding) is None
    er.async_get(hass).async_update_entity(
        d["target"], disabled_by=er.RegistryEntryDisabler.USER
    )
    assert not cap.describe(d["source"])["controls"] and not calls


async def test_other_config_entry_cannot_supply_the_same_device_siren(
    hass, catalog_devices
):
    add, calls = catalog_devices
    d = add(
        "SD-8SCZBS",
        "Climax",
        domain="siren",
        key="warning",
        idle="off",
        attrs={"supported_features": 21, "available_tones": ["burglar"]},
    )
    registry = er.async_get(hass)
    registry.async_update_entity(d["target"], disabled_by=er.RegistryEntryDisabler.USER)
    other = MockConfigEntry(domain="mqtt", data={})
    other.add_to_hass(hass)
    target = registry.async_get_or_create(
        "siren",
        "mqtt",
        "other-config-warning",
        config_entry=other,
        device_id=d["device"],
    )
    hass.states.async_set(
        target.entity_id,
        "off",
        {"supported_features": 21, "available_tones": ["burglar"]},
    )
    assert not Capabilities(hass).describe(d["source"])["controls"] and not calls


async def test_changed_new_contract_invalidates_saved_authority(
    hass, catalog_devices, monkeypatch
):
    add, calls = catalog_devices
    d = add(
        "SD-8SCZBS",
        "Climax",
        domain="siren",
        key="warning",
        idle="off",
        attrs={"supported_features": 21, "available_tones": ["burglar"]},
    )
    cap = Capabilities(hass)
    control = cap.describe(d["source"])["controls"][0]
    saved = {key: control[key] for key in ("source", "target", "profile", "identity")}
    monkeypatch.setitem(
        PROFILES, "ias_mqtt", replace(PROFILES["ias_mqtt"], duration=30)
    )
    assert cap.describe(d["source"])["controls"][0]["identity"] != saved["identity"]
    assert cap.resolve(saved) is None and not calls


async def test_changed_origin_device_class_cannot_drive_a_sounder(
    hass, catalog_devices
):
    add, calls = catalog_devices
    source = add("Unknown", "Simulation")
    target = add("HS1SA-E-PLUS", "Heiman")
    selected = [source["source"], target["source"]]
    entry = await setup(hass, selected)
    await configure(hass, entry, selected, [target])
    er.async_get(hass).async_update_entity(source["source"], device_class="opening")
    hass.states.async_set(source["source"], "on", {"device_class": "opening"})
    await flush(hass, entry)
    assert not calls
    # Current-state interpretation is unchanged; this is an execution gate.
    assert entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_origin_identity_loss_is_not_an_explicit_smoke_release(
    hass, catalog_devices
):
    add, calls = catalog_devices
    source = add("Unknown", "Simulation")
    target = add("HS1SA-E-PLUS", "Heiman")
    selected = [source["source"], target["source"]]
    entry = await setup(hass, selected)
    await configure(hass, entry, selected, [target])
    hass.states.async_set(source["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1
    er.async_get(hass).async_update_entity(source["source"], device_class="opening")
    hass.states.async_set(source["source"], "off", {"device_class": "opening"})
    await flush(hass, entry)
    assert (
        len(calls) == 1 and source["source"] in entry.runtime_data.panel.linking.active
    )
    er.async_get(hass).async_update_entity(source["source"], device_class="smoke")
    hass.states.async_set(source["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 2 and calls[-1][2]["option"] == "stop"
    assert await hass.config_entries.async_unload(entry.entry_id)


def test_z2m_white_label_evidence_cannot_authorize_a_zha_alias():
    data = deepcopy(CATALOG)
    aqara = next(entry for entry in data["entries"] if entry["model"] == "JY-GZ-01AQ")
    alias = aqara["aliases"][0]
    alias["providers"]["zha"] = deepcopy(aqara["providers"]["zha"])
    with pytest.raises(ValueError, match="own provider matcher"):
        validate_catalog(data)


async def test_bosch_test_mode_with_discovery_switch_id_blocks_test_origin(
    hass, catalog_devices
):
    add, calls = catalog_devices
    device = bsd_target(add)
    cap = Capabilities(hass)
    switch = device["register"]("switch", "switch_test_mode", "on", {})
    assert cap.test_blocked(device["source"])
    hass.states.async_set(switch, "off")
    assert not cap.test_blocked(device["source"])
    assert not calls


def bsd_target(add, *, prerequisite=True):
    return add(
        "BSD-2",
        "Bosch",
        domain="siren",
        key="alarm_control",
        idle="off",
        attrs={"supported_features": 5, "available_tones": ["smoke", "burglar"]},
        gate=("switch", "broadcast_alarms", "off") if prerequisite else None,
    )


@pytest.mark.parametrize("value", [None, "on", "unknown", "unavailable"])
async def test_bsd_broadcast_must_explicitly_be_off(hass, catalog_devices, value):
    add, calls = catalog_devices
    device = bsd_target(add, prerequisite=value is not None)
    if value is not None:
        hass.states.async_set(device["setting"], value)
    info = Capabilities(hass).describe(device["source"])
    assert info["status"] == "setting_needed"
    assert info["reason"] == "bosch_broadcast_must_be_off"
    assert not calls


@pytest.mark.parametrize("change", ["disabled", "wrong_domain", "foreign", "replaced"])
async def test_bsd_broadcast_identity_is_bound_and_required(
    hass, catalog_devices, change
):
    add, calls = catalog_devices
    device = bsd_target(add)
    cap = Capabilities(hass)
    control = cap.describe(device["source"])["controls"][0]
    saved = {key: control[key] for key in ("source", "target", "profile", "identity")}
    registry = er.async_get(hass)
    setting = registry.async_get(device["setting"])
    if change == "disabled":
        registry.async_update_entity(
            device["setting"], disabled_by=er.RegistryEntryDisabler.USER
        )
    elif change == "wrong_domain":
        registry.async_remove(device["setting"])
        device["register"]("binary_sensor", "broadcast_alarms", "off", {})
    elif change == "foreign":
        registry.async_remove(device["setting"])
        other = MockConfigEntry(domain="mqtt", data={})
        other.add_to_hass(hass)
        entry = registry.async_get_or_create(
            "switch",
            "mqtt",
            setting.unique_id,
            config_entry=other,
            device_id=device["device"],
        )
        hass.states.async_set(entry.entity_id, "off")
    else:
        registry.async_update_entity(
            device["setting"], new_unique_id="other-broadcast-property"
        )
    assert cap.resolve(saved) is None
    assert not calls


async def test_bsd_changed_prerequisite_contract_requires_new_confirmation(
    hass, catalog_devices, monkeypatch
):
    add, calls = catalog_devices
    device = bsd_target(add)
    cap = Capabilities(hass)
    guarded = cap.describe(device["source"])["controls"][0]
    original = PROFILES["bosch_bsd_mqtt"]
    monkeypatch.setitem(PROFILES, "bosch_bsd_mqtt", replace(original, gate=None))
    previous = cap.describe(device["source"])["controls"][0]
    assert previous["identity"] != guarded["identity"]
    monkeypatch.setitem(PROFILES, "bosch_bsd_mqtt", original)
    saved = {key: previous[key] for key in ("source", "target", "profile", "identity")}
    assert cap.resolve(saved) is None and not calls


async def test_bsd_gate_change_after_preview_rejects_save(hass, catalog_devices):
    from custom_components.alarmmesh.groups import GroupError

    add, calls = catalog_devices
    target, source = bsd_target(add), add("Unknown", "Simulation")
    members = [target["source"], source["source"]]
    entry = await setup(hass, members)
    control = Capabilities(hass).describe(target["source"])["controls"][0]
    saved = {key: control[key] for key in ("source", "target", "profile", "identity")}
    hass.states.async_set(target["setting"], "on")
    with pytest.raises(GroupError, match="control_changed"):
        await entry.runtime_data.panel.groups.async_mutate(
            {
                "operation": "create",
                "revision": 0,
                "name": "Blocked broadcast",
                "members": members,
                "linking": {"enabled": True, "bindings": [saved]},
                "confirmed": True,
            },
            tuple(members),
        )
    assert not entry.runtime_data.panel.groups.groups and not calls
    assert hass.states.is_state(target["setting"], "on")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_bsd_gate_rechecked_after_waiting_before_dispatch(hass, catalog_devices):
    add, calls = catalog_devices
    target, source = bsd_target(add), add("Unknown", "Simulation")
    members = [target["source"], source["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [target])
    engine = entry.runtime_data.panel.linking
    engine._semaphore = asyncio.Semaphore(0)
    hass.states.async_set(source["source"], "on")
    await hass.async_block_till_done()
    assert engine._task is not None
    hass.states.async_set(target["setting"], "on")
    await hass.async_block_till_done()
    engine._semaphore.release()
    await flush(hass, entry)
    assert not calls and hass.states.is_state(target["setting"], "on")
    assert (
        entry.runtime_data.panel.snapshot()["groups"][0]["linking_status"]
        == "review_needed"
    )
    hass.states.async_set(target["setting"], "off")
    await flush(hass, entry)
    assert calls == [
        ("siren", "turn_on", {"entity_id": target["target"], "tone": "smoke"})
    ]
    hass.states.async_set(source["source"], "off")
    await flush(hass, entry)
    assert len(calls) == 1  # No switch write or automatic stop.
    assert await hass.config_entries.async_unload(entry.entry_id)


def catalog_variants():
    for definition in CATALOG["entries"]:
        for row in [definition, *definition["aliases"]]:
            for provider, integration in (("zigbee2mqtt", "mqtt"), ("zha", "zha")):
                yield definition, row, provider, integration


def simulated_catalog_device(add, definition, row, provider, integration):
    adapters = {
        case[-2]: (case[3], case[4], case[6], case[5], case[7]) for case in CASES
    }
    adapters["heiman_mqtt"] = adapters["heiman_cascade_mqtt"]
    adapters["aqara_mqtt"] = (
        "select",
        "buzzer",
        {"options": ["alarm", "mute"]},
        "mute",
        ("switch", "linkage_alarm"),
    )
    model, vendor = row["model"], row["vendor"]
    review = row["providers"][provider]
    profile = review["profile"]
    if provider == "zha" and profile:
        signature = definition["matchers"][provider][0]
        model, vendor = signature["model"], signature["vendor"]
    # A plausible sounder on an unreviewed model must not grant a binding.
    adapter = adapters[profile or "heiman_mqtt"]
    device = add(model, vendor, integration, *adapter)
    if profile == "aqara_mqtt":
        device["register"]("binary_sensor", "buzzer_manual_alarm", "off", {})
    return device


async def test_all_catalog_variants_as_directional_routes(hass, catalog_devices):
    """Check provider recognition and routing between distinct simulated devices."""
    add, calls = catalog_devices
    caps = Capabilities(hass)
    origins, bindings, reviewed_targets = [], [], set()
    provider_counts = {"mqtt": 0, "zha": 0}
    for definition, row, provider, integration in catalog_variants():
        review = row["providers"][provider]
        profile = review["profile"]
        device = simulated_catalog_device(add, definition, row, provider, integration)
        controls = caps.describe(device["source"])["controls"]
        assert [c["profile"] for c in controls] == ([profile] if profile else []), (
            row["model"],
            provider,
        )
        if controls:
            control = controls[0]
            assert control["safe_stop"] == (review["stop"] == "implemented")
            bindings.append(
                {k: control[k] for k in ("source", "target", "profile", "identity")}
            )
            reviewed_targets.add(device["target"])
            provider_counts[integration] += 1
        if definition["kind"] == "smoke":
            if row["model"] == "SMART-SMOKE10" and provider == "zha":
                continue  # Only the Zigbee2MQTT smoke_state route was reviewed.
            # Use two devices when pairing the same model.
            origin = add(row["model"], row["vendor"], integration)["source"]
            origins.append(origin)
    assert len(origins) == 123 and provider_counts == {"mqtt": 21, "zha": 10}
    members = origins + [b["source"] for b in bindings]
    group = {
        "members": members,
        "origins": origins,
        "linking": {"enabled": True, "bindings": bindings},
    }
    for source in origins:
        routes = plan_activations({source}, [group, group])
        assert {r.binding["target"] for r in routes} == reviewed_targets
        assert len(routes) == len(reviewed_targets)
        assert all(r.origins == {source} for r in routes)
    group["linking"]["enabled"] = False
    assert not plan_activations(set(origins), [group])
    assert not calls


@pytest.mark.parametrize(
    "definition,row,provider,integration",
    [
        pytest.param(
            definition, row, provider, integration, id=f"{row['model']}-{integration}"
        )
        for definition, row, provider, integration in catalog_variants()
        if row["providers"][provider]["profile"]
    ],
)
async def test_link_across_providers_records_only_actual_call(
    hass, catalog_devices, definition, row, provider, integration
):
    add, calls = catalog_devices
    target = simulated_catalog_device(add, definition, row, provider, integration)
    origin = (
        add("HS1SA-E-PLUS", "Heiman")
        if integration == "zha"
        else add("SMSZB-120", "Develco", "zha")
    )
    members = [origin["source"], target["source"]]
    entry = await setup(hass, members)
    await configure(hass, entry, members, [target])
    hass.states.async_set(origin["source"], "on", {"device_class": "smoke"})
    await flush(hass, entry)
    assert len(calls) == 1 and calls[0][2]["entity_id"] == target["target"]
    commands = [
        r
        for r in entry.runtime_data.panel.activity.snapshot()["events"]
        if r["kind"] == "sounder_command"
    ]
    assert [(r["result"], r["source"], r["origins"]) for r in commands] == [
        ("start_requested", target["source"], [origin["source"]])
    ]
    hass.states.async_set(target["source"], "on", {"device_class": "smoke"})
    hass.states.async_set(origin["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    assert entry.runtime_data.panel.snapshot()["result"]["smoke"] == "SMOKE_REPORTED"
    assert len(calls) == 1
    hass.states.async_set(target["source"], "off", {"device_class": "smoke"})
    await flush(hass, entry)
    stop = row["providers"][provider]["stop"] == "implemented"
    assert calls[1:] == (
        [("select", "select_option", {"entity_id": target["target"], "option": "stop"})]
        if stop
        else []
    )
    recorded = [
        r["result"]
        for r in reversed(entry.runtime_data.panel.activity.snapshot()["events"])
        if r["kind"] == "sounder_command"
    ]
    assert recorded == (
        ["start_requested", "stop_requested"] if stop else ["start_requested"]
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
