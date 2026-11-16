"""Actual HA Matter classes/descriptions, fake attributes and command I/O only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from homeassistant.components.matter import binary_sensor, button, sensor
from homeassistant.components.matter.models import MatterEntityInfo
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


async def offline_matter(passed, require):
    from custom_components.alarmmesh.matter import CONTRACTS, path

    schemas = {
        s.entity_description.key: s
        for m in (binary_sensor, button, sensor)
        for s in m.DISCOVERY_SCHEMAS
    }
    for domain, key, cluster, attribute in CONTRACTS.values():
        schema = schemas[key]
        require(
            str(schema.platform) == domain
            and (
                schema.required_attributes[0].cluster_id,
                schema.required_attributes[0].attribute_id,
            )
            == (cluster, attribute),
            "Matter HA contract changed",
        )
    values = {}
    node = SimpleNamespace(
        node_id=77,
        available=True,
        is_bridge_device=False,
        endpoints={},
        get_compose_parent=lambda _ep: None,
    )
    endpoint = SimpleNamespace(
        node=node,
        endpoint_id=1,
        is_bridged_device=False,
        device_info=SimpleNamespace(vendorID=0, productID=0),
        has_attribute=lambda *_: False,
        get_attribute_value=lambda _c, a: values.get((a.cluster_id, a.attribute_id)),
    )
    node.endpoints[1] = endpoint
    client = SimpleNamespace(
        server_info=SimpleNamespace(compressed_fabric_id=1),
        send_device_command=AsyncMock(),
    )

    def entity(key):
        schema = schemas[key]
        info = MatterEntityInfo(
            endpoint=endpoint,
            platform=schema.platform,
            attributes_to_watch=list(schema.required_attributes),
            entity_description=schema.entity_description,
            entity_class=schema.entity_class,
            discovery_schema=schema,
        )
        return schema.entity_class(client, endpoint, info)

    smoke = entity("SmokeCoAlarmSmokeStateSensor")
    require(smoke.is_on is None, "Absent Matter smoke must be unknown")
    values[92, 1] = 0
    smoke._update_from_device()
    require(smoke.is_on is False, "Matter explicit normal mapping")
    values[92, 1] = 1
    smoke._update_from_device()
    require(smoke.is_on is True, "Matter smoke warning mapping")
    co = entity("SmokeCoAlarmCOStateSensor")
    require(co.device_class == "carbon_monoxide", "Matter CO must remain separate")
    values[92, 2] = 2
    co._update_from_device()
    require(co.is_on is True, "Matter CO mapping")
    require(smoke.unique_id != co.unique_id, "Matter local smoke/CO identity collision")
    require(
        schemas["PowerSource"].entity_description.device_to_ha(144) == 72,
        "Matter battery half-percent mapping",
    )
    require(
        path(SimpleNamespace(platform="matter", unique_id=smoke.unique_id))[1:]
        == (1, "SmokeCoAlarmSmokeStateSensor", 92, 1),
        "Actual HA identity parser mismatch",
    )
    passed("matter_actual_ha_descriptions_mapping_and_identity")
    test = entity("SmokeCoAlarmSelfTestRequest")
    await test.async_press()
    call = client.send_device_command.call_args.kwargs
    require(
        call["endpoint_id"] == 1
        and call["node_id"] == 77
        and call["command"].cluster_id == 92
        and call["command"].command_id == 0,
        "SelfTestRequest must not become Identify/mute/siren",
    )
    require(
        schemas["SmokeCoAlarmSelfTestRequest"].value_contains == 0,
        "HA accepted-command discovery gate",
    )
    passed("matter_actual_selftest_button_mock_endpoint_no_controller")
    return smoke, test


async def matter_registry_checks(hass, passed, require):
    from custom_components.alarmmesh import matter
    from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS

    smoke, test = await offline_matter(passed, require)
    owner = ConfigEntry(
        domain="matter",
        title="SIMULATED ignored Matter registry owner",
        data={},
        options={},
        version=1,
        minor_version=1,
        source=SOURCE_IGNORE,
        unique_id="alarmmesh_offline_matter_check",
        discovery_keys={},
        subentries_data=[],
    )
    manager_type = type(hass.config_entries)
    original = manager_type.async_setup

    async def no_controller(manager, entry_id, *args, **kwargs):
        if entry_id == owner.entry_id:
            return False
        return await original(manager, entry_id, *args, **kwargs)

    with patch.object(manager_type, "async_setup", no_controller):
        await hass.config_entries.async_add(owner)
    require(
        "matter" not in hass.config.components and owner.data == {},
        "Matter controller must remain absent",
    )
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=owner.entry_id,
        identifiers={("matter", "deviceid_SIMULATION")},
        manufacturer="HEIMAN",
        model="HS1SA-M",
    )
    registry = er.async_get(hass)

    def register(domain, unique, cls=None, key=None):
        return registry.async_get_or_create(
            domain,
            "matter",
            unique,
            config_entry=owner,
            device_id=device.id,
            original_name="SIMULATED Matter",
            original_device_class=cls,
            translation_key=key,
        ).entity_id

    source = register("binary_sensor", smoke.unique_id, "smoke")
    target = register("button", test.unique_id, key="self_test_request")
    prefix = smoke.unique_id.rsplit("-", 4)[0]
    flag = register(
        "binary_sensor",
        prefix + "-1-SmokeCoAlarmTestInProgressSensor-92-5",
        key="test_in_progress",
    )
    forwarded = register(
        "binary_sensor",
        prefix + "-1-SmokeCoAlarmInterconnectSmokeAlarmSensor-92-8",
        "smoke",
        key="interconnected_smoke_alarm",
    )
    other = register(
        "button",
        prefix + "-2-SmokeCoAlarmSelfTestRequest-92-65529",
        key="self_test_request",
    )
    for eid, state, attrs in (
        (source, "off", {"device_class": "smoke"}),
        (target, "unknown", {}),
        (flag, "off", {}),
        (forwarded, "off", {"device_class": "smoke"}),
        (other, "unknown", {}),
    ):
        hass.states.async_set(eid, state, attrs)
    entry = hass.config_entries.async_entries("alarmmesh")[0]
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: [source, forwarded]}
    )
    require(
        await hass.config_entries.async_setup(entry.entry_id), "Matter AlarmMesh setup"
    )
    p = entry.runtime_data.panel

    async def settle():
        for _ in range(16):
            await hass.async_block_till_done()
            tasks = [
                p.linking._task,
                p.activity.task,
                p.effects._task,
                p.maintenance.task,
                p.reminders.task,
                *p.selftests.tasks,
            ]
            if not any(tasks):
                return
            for task in tasks:
                if task is not None:
                    await task
        raise AssertionError("Matter workers did not settle")

    require(
        [e.entity_id for e in matter.properties(hass, source, "self_test_request")]
        == [target],
        "Wrong endpoint self-test bound",
    )
    control = p.selftests.resolve(source)
    require(
        control is not None and control["target"] == target,
        "Matter standard button missing",
    )

    async def mocked_press(call):
        require(call.data == {"entity_id": target}, "Unexpected Matter mock target")
        await test.async_press()

    hass.services.async_register("button", "press", mocked_press)
    await p.selftests.start(source, control["identity"], True, request_id=uuid4().hex)
    hass.states.async_set(flag, "on")
    await settle()
    require(
        p.selftests.record["status"] == "test_active" and not p.linking.active,
        "Test activity became smoke",
    )
    hass.states.async_set(source, "on", {"device_class": "smoke"})
    await settle()
    require(
        source in p.linking.active
        and entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED",
        "Matter real smoke suppressed by test",
    )
    hass.states.async_set(flag, "off")
    await settle()
    require(
        p.selftests.record["status"] == "outcome_unknown",
        "Test completion falsely reported success",
    )
    passed("matter_registry_endpoint_selftest_and_real_smoke_fixture")
    hass.states.async_set(source, "off", {"device_class": "smoke"})
    hass.states.async_set(forwarded, "on", {"device_class": "smoke"})
    await settle()
    require(
        forwarded not in p.linking.active
        and entry.runtime_data.result.smoke_status.name == "SMOKE_REPORTED",
        "Interconnect hidden or used as independent origin",
    )
    require(await hass.config_entries.async_unload(entry.entry_id), "Matter unload")
    require(
        p.selftests.closed and p.activity.closed and p.matter_sources.closed,
        "Matter retired controller remained active",
    )
    passed("matter_interconnect_readonly_and_unload_cleanup")
