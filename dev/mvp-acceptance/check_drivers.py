"""Real HA MQTT discovery + offline ZHA actions. Only a private synthetic broker.

Not a running Zigbee2MQTT instance, coordinator, pairing or hardware test.
The wrapper creates the broker alias exclusively on this run's internal network.
"""

import argparse
import asyncio
import json
import sys
import traceback
from importlib.metadata import version
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import paho.mqtt.client as paho
from check_runtime import require

from homeassistant import bootstrap
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import __version__
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.runner import RuntimeConfig

# Expected HA commands and wire payloads are independent of AlarmMesh profiles.
MQTT = (
    (
        "Heiman",
        "S1-M",
        "select",
        "siren_for_automation_only",
        ["stop", "smoke_siren", "co_siren"],
        "stop",
        None,
        "smoke_siren",
        "heiman_activation_mqtt",
    ),
    (
        "Aqara",
        "JY-GZ-03AQ",
        "select",
        "buzzer",
        ["alarm", "mute"],
        "mute",
        ("switch", "linkage_alarm"),
        "alarm",
        "aqara_mqtt",
    ),
    (
        "Heiman",
        "HS15A-M",
        "siren",
        "warning",
        [],
        "off",
        None,
        {"warning": {"mode": "burglar", "duration": 60}},
        "ias_mqtt",
    ),
    (
        "Bosch",
        "8750001213",
        "select",
        "alarm",
        ["stop", "pre_alarm", "fire", "burglar"],
        "stop",
        None,
        "fire",
        "bosch_twinguard_mqtt",
    ),
    (
        "Bosch",
        "BSD-2",
        "siren",
        "alarm_control",
        [],
        "off",
        ("switch", "broadcast_alarms", "off"),
        "smoke",
        "bosch_bsd_mqtt",
    ),
    (
        "ShinaSystem",
        "FAM-300Z",
        "switch",
        "force_smoke_alarm",
        [],
        "OFF",
        ("binary_sensor", "remote_control_permission"),
        "ON",
        "shina_mqtt",
    ),
)


async def zha_checks(passed):
    """Execute actual installed ZHA action methods and an actual Aqara quirk.

    Discovery/initialization is tested separately with HA registry fixtures. These
    action objects are initialized only for the method under test. Endpoint I/O
    and event emission are replaced; no application/controller is started.
    """
    import zigpy.types as t
    from zha.application.platforms.siren import AdvancedSiren, BasicSiren
    from zha.application.platforms.switch import AqaraBuzzerManualAlarm
    from zhaquirks.xiaomi.aqara.smoke import LumiSensorSmokeAcn03, OppleCluster
    from zigpy.device import Device
    from zigpy.zcl.clusters.security import IasWd, IasZone, WarningMode
    from zigpy.zcl.foundation import Status, WriteAttributesStatusRecord

    app = MagicMock()
    app.get_sequence.return_value = 1
    base = Device(app, t.EUI64.convert("00:00:00:00:00:00:00:01"), 0x1234)
    base.manufacturer, base.model = "LUMI", "lumi.sensor_smoke.acn03"
    for ep_id, signature in LumiSensorSmokeAcn03.signature["endpoints"].items():
        ep = base.add_endpoint(ep_id)
        ep.profile_id, ep.device_type = (
            signature["profile_id"],
            signature["device_type"],
        )
        for cluster in signature["input_clusters"]:
            ep.add_input_cluster(cluster)
        for cluster in signature["output_clusters"]:
            ep.add_output_cluster(cluster)
    device = LumiSensorSmokeAcn03(app, base.ieee, base.nwk, base)
    endpoint = device.endpoints[1]
    opple = endpoint.in_clusters[OppleCluster.cluster_id]
    zone = endpoint.in_clusters[IasZone.cluster_id]
    opple.update_attribute(0x013A, 0)
    for attr in (0x013D, 0x014C, 0x0127):
        opple.update_attribute(attr, 1)
        require(not zone.get("zone_status"), "Buzzer/linkage/test became smoke")
    opple.update_attribute(0x013A, 1)
    require(bool(zone.get("zone_status")), "Aqara quirk did not map real smoke")
    opple.update_attribute(0x013A, 0)
    require(not zone.get("zone_status"), "Aqara smoke did not clear")
    passed("zha_actual_aqara_quirk_status_separation")

    # Retain real cluster serialization; the endpoint request is the I/O boundary.
    endpoint.request = AsyncMock(
        return_value=([WriteAttributesStatusRecord(status=Status.SUCCESS)],)
    )
    switch = object.__new__(AqaraBuzzerManualAlarm)
    switch._cluster = opple
    switch.maybe_emit_state_changed_event = Mock()
    await switch.async_turn_on()
    require(
        endpoint.request.await_count == 1, "Aqara action did not reach mocked endpoint"
    )
    data = endpoint.request.call_args.kwargs["data"]
    require(b"\x3d\x01" in data, "Unexpected Aqara attribute serialized")
    require(
        b"\x26\x01" not in data and b"\x27\x01" not in data, "Mute/self-test serialized"
    )
    passed("zha_actual_aqara_switch_action")

    for cls, kwargs, name in (
        (BasicSiren, {"duration": 60}, "zha_actual_basic_ias_action"),
        (
            AdvancedSiren,
            {"duration": 60, "tone": WarningMode.Burglar},
            "zha_actual_advanced_ias_action",
        ),
    ):
        action = object.__new__(cls)
        action._cluster = IasWd(endpoint)
        original = action._cluster.start_warning

        async def serialize_warning(original=original, **parameters):
            return await original(**parameters)

        action._cluster.start_warning = AsyncMock(side_effect=serialize_warning)
        previous_requests = endpoint.request.await_count
        action._off_listener = None
        action._tracked_handles = []
        action.maybe_emit_state_changed_event = Mock()
        if cls is AdvancedSiren:
            from zigpy.zcl.clusters.security import SirenLevel, Strobe, StrobeLevel

            action.defaults = dict.fromkeys(
                (WarningMode, SirenLevel, Strobe, StrobeLevel)
            )
        await action.async_turn_on(**kwargs)
        sent = action._cluster.start_warning.call_args.kwargs
        require(
            sent["warning_duration"] == 60
            and sent["warning"].mode == WarningMode.Burglar,
            "Unsafe IAS tone/duration",
        )
        require(action._cluster.start_warning.await_count == 1, "Duplicate IAS command")
        require(
            endpoint.request.await_count == previous_requests + 1,
            "IAS serialization did not reach mock endpoint",
        )
        action._cancel_off_listener()
        passed(name)


async def main(requested):
    root = Path("/config")
    context = json.loads((root / "run-context.json").read_text("utf-8-sig"))
    report = {
        **context,
        "actual_ha_version": __version__,
        "result": "FAIL",
        "scope": (
            "Real HA MQTT discovery on own isolated synthetic broker; "
            "offline ZHA actions/quirks with mocked endpoint I/O. "
            "No radio, live network or hardware validation."
        ),
        "scenarios": {},
        "packages": {
            name: version(name) for name in ("zha", "zha-quirks", "zigpy", "paho-mqtt")
        },
    }
    hass, mqtt = None, None
    current = "driver_setup"

    def passed(name):
        report["scenarios"][name] = "PASS"

    try:
        require(
            __version__ == requested == context["requested_ha_version"],
            "HA version mismatch",
        )
        config = root / "drivers"
        require(not config.exists(), "Driver configuration must be fresh")
        config.mkdir()
        (config / "custom_components").symlink_to(
            root / "custom_components", target_is_directory=True
        )
        (config / "configuration.yaml").write_text(
            "homeassistant:\n  name: AlarmMesh DRIVER SIMULATION ONLY\n"
            "frontend:\nconfig:\napi:\nhttp:\n",
            encoding="utf-8",
        )
        sys.path.insert(0, str(config))
        hass = await bootstrap.async_setup_hass(
            RuntimeConfig(config_dir=str(config), skip_pip=True, log_no_color=True)
        )
        require(
            hass is not None and not hass.config.recovery_mode, "Driver HA setup failed"
        )
        await hass.async_start()
        flow = await hass.config_entries.flow.async_init(
            "mqtt", context={"source": SOURCE_USER}
        )
        flow = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                "broker": "alarmmesh-sim-broker",
                "port": 1883,
                "protocol": "3.1.1",
                "other_settings": {
                    "set_client_cert": False,
                    "set_ca_cert": "off",
                    "transport": "tcp",
                },
            },
        )
        require(flow["type"] is FlowResultType.CREATE_ENTRY, "MQTT flow failed")
        await hass.async_block_till_done()
        loop = asyncio.get_running_loop()
        connected, subscribed = asyncio.Event(), asyncio.Event()
        messages = asyncio.Queue()
        mqtt = paho.Client(
            paho.CallbackAPIVersion.VERSION2, client_id="alarmmesh-synthetic-discovery"
        )
        mqtt.on_connect = lambda *args: loop.call_soon_threadsafe(connected.set)
        mqtt.on_subscribe = lambda *args: loop.call_soon_threadsafe(subscribed.set)
        mqtt.on_message = lambda _c, _u, m: loop.call_soon_threadsafe(
            messages.put_nowait, (m.topic, m.payload.decode())
        )
        await asyncio.to_thread(mqtt.connect, "alarmmesh-sim-broker", 1883)
        mqtt.loop_start()
        await asyncio.wait_for(connected.wait(), 10)
        mqtt.subscribe("alarmmesh_simulation/+/set/#")
        await asyncio.wait_for(subscribed.wait(), 10)

        async def publish(topic, data):
            payload = data if isinstance(data, str) else json.dumps(data)
            info = mqtt.publish(topic, payload, qos=1, retain=True)
            await asyncio.to_thread(info.wait_for_publish, 10)

        states, targets, sources = {}, [], []
        registry = er.async_get(hass)
        for index, row in enumerate(MQTT):
            vendor, model, domain, key, options, idle, gate, _expected, _profile = row
            uid = f"synthetic{index}"
            topic = f"alarmmesh_simulation/{uid}"
            device = {
                "identifiers": [f"zigbee2mqtt_{uid}"],
                "manufacturer": vendor,
                "model": model,
                "model_id": model,
                "name": f"SIMULATED {index}",
                "sw_version": "2.2.0",
            }

            async def discover(
                domain, prop, payload, uid=uid, topic=topic, device=device
            ):
                unique = f"{uid}_{prop}_zigbee2mqtt"
                await publish(
                    f"homeassistant/{domain}/{unique}/config",
                    {
                        "unique_id": unique,
                        "device": device,
                        "name": prop,
                        "state_topic": topic,
                        "availability_topic": topic + "/availability",
                        **payload,
                    },
                )
                return unique

            await discover(
                "binary_sensor",
                "smoke",
                {
                    "device_class": "smoke",
                    "value_template": "{{ value_json.smoke }}",
                    "payload_on": True,
                    "payload_off": False,
                },
            )
            await discover(
                "sensor",
                "battery",
                {
                    "device_class": "battery",
                    "unit_of_measurement": "%",
                    "value_template": "{{ value_json.battery }}",
                },
            )
            await discover(
                "binary_sensor",
                "test",
                {
                    "value_template": "{{ value_json.test }}",
                    "payload_on": True,
                    "payload_off": False,
                },
            )
            payload = {"command_topic": topic + "/set/" + key}
            if domain == "select":
                payload.update(
                    options=options,
                    value_template="{{ value_json." + key + " }}",
                    command_template="{{ value }}",
                )
            elif domain == "switch":
                payload.update(
                    value_template="{{ value_json." + key + " }}",
                    payload_on="ON",
                    payload_off="OFF",
                )
            else:
                payload.update(
                    available_tones=["smoke", "burglar"]
                    if key == "alarm_control"
                    else ["burglar", "fire"],
                    support_duration=key != "alarm_control",
                    support_volume_set=False,
                    state_value_template=(
                        '{{ {"state": value_json.siren_state} | to_json }}'
                    ),
                )
                payload["command_template"] = (
                    "{{ tone }}"
                    if key == "alarm_control"
                    else (
                        '{{ {"warning": {"mode": tone, "duration": duration}}'
                        " | to_json }}"
                    )
                )
            target_uid = await discover(domain, key, payload)
            if gate:
                gd, gk = gate[:2]
                extra = {
                    "value_template": "{{ value_json." + gk + " }}",
                    "payload_on": "True" if gd == "binary_sensor" else "ON",
                    "payload_off": "False" if gd == "binary_sensor" else "OFF",
                }
                if gd == "switch":
                    extra["command_topic"] = topic + "/set/" + gk
                await discover(gd, gk, extra)
            states[index] = {
                "smoke": False,
                "battery": 72,
                "test": False,
                key: idle,
                "siren_state": "OFF",
                **(
                    {
                        gate[1]: "OFF"
                        if len(gate) == 3 and gate[2] == "off"
                        else "True"
                        if gate[0] == "binary_sensor"
                        else "ON"
                    }
                    if gate
                    else {}
                ),
            }
            await publish(topic + "/availability", "online")
            await publish(topic, states[index])
            for _ in range(100):
                await asyncio.sleep(0.05)
                source = registry.async_get_entity_id(
                    "binary_sensor", "mqtt", f"{uid}_smoke_zigbee2mqtt"
                )
                target = registry.async_get_entity_id(domain, "mqtt", target_uid)
                if (
                    source
                    and target
                    and hass.states.is_state(source, "off")
                    and hass.states.get(target)
                    and hass.states.get(target).state not in {"unknown", "unavailable"}
                ):
                    break
            else:
                raise AssertionError(f"MQTT discovery/state failed for fixture {index}")
            sources.append(source)
            targets.append(target)
        passed("real_mqtt_discovery_and_states")
        from custom_components.alarmmesh.capabilities import Capabilities
        from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS

        cap = Capabilities(hass)
        for index, row in enumerate(MQTT):
            info = cap.describe(sources[index])
            require(
                info["status"] == "linkable"
                and info["controls"][0]["profile"] == row[-1],
                f"Actual MQTT metadata/profile mismatch {index}: {info['reason']}",
            )
            require(
                any(
                    v["key"] == "battery" and v["value"] == 72
                    for v in info["details"]["values"]
                ),
                "Actual MQTT battery not read",
            )
        require(messages.empty(), "Discovery sent an unsolicited command")
        # Source 0 is a normal discovered smoke entity; its own target is excluded.
        flow = await hass.config_entries.flow.async_init(
            "alarmmesh", context={"source": SOURCE_USER}
        )
        flow = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {CONF_SOURCE_ENTITY_IDS: sources}
        )
        require(flow["type"] is FlowResultType.CREATE_ENTRY, "AlarmMesh config failed")
        entry = flow["result"]

        async def settle():
            for _ in range(8):
                await hass.async_block_till_done()
                task = entry.runtime_data.panel.linking._task
                if task is None:
                    return
                await task
            raise AssertionError("Driver linking failed to settle")

        await settle()
        panel = entry.runtime_data.panel

        async def wait_state(predicate):
            for _ in range(100):
                if predicate():
                    return
                await asyncio.sleep(0.05)
            raise AssertionError("Synthetic MQTT state did not arrive")

        states[0]["test"] = True
        await publish("alarmmesh_simulation/synthetic0", states[0])
        await wait_state(lambda: cap.test_blocked(sources[0]))
        states[0]["smoke"] = True
        await publish("alarmmesh_simulation/synthetic0", states[0])
        await wait_state(lambda: hass.states.is_state(sources[0], "on"))
        await settle()
        require(
            not panel.linking.active and messages.empty(),
            "Known MQTT self-test initiated an incident",
        )
        states[0]["smoke"] = False
        await publish("alarmmesh_simulation/synthetic0", states[0])
        await wait_state(lambda: hass.states.is_state(sources[0], "off"))
        await settle()
        states[0]["test"] = False
        await publish("alarmmesh_simulation/synthetic0", states[0])
        await wait_state(lambda: not cap.test_blocked(sources[0]))
        await settle()
        passed("real_mqtt_profile_and_read_only_details")
        bindings = [
            {
                k: cap.describe(source)["controls"][0][k]
                for k in ("source", "target", "profile", "identity")
            }
            for source in sources[1:]
        ]
        bsd_index = next(i for i, row in enumerate(MQTT) if row[-1] == "bosch_bsd_mqtt")
        bsd_source = sources[bsd_index]
        bsd_binding = next(b for b in bindings if b["source"] == bsd_source)
        from custom_components.alarmmesh.groups import GroupError

        for broadcast in ("ON",):
            states[bsd_index]["broadcast_alarms"] = broadcast
            await publish(
                f"alarmmesh_simulation/synthetic{bsd_index}", states[bsd_index]
            )
            await wait_state(lambda: cap.resolve(bsd_binding) is None)
            await settle()
            require(
                cap.describe(bsd_source)["reason"] == "bosch_broadcast_must_be_off",
                "Wrong broadcast blocking reason",
            )
            try:
                await panel.groups.async_mutate(
                    {
                        "operation": "create",
                        "revision": 0,
                        "name": "Blocked broadcast",
                        "members": sources,
                        "linking": {"enabled": True, "bindings": [bsd_binding]},
                        "confirmed": True,
                    },
                    tuple(sources),
                )
            except GroupError:
                pass
            else:
                raise AssertionError("Broadcast setting did not block confirmation")
            require(
                messages.empty() and not panel.groups.groups,
                "Broadcast prerequisite emitted commands or saved unsafe group",
            )
            states[bsd_index]["broadcast_alarms"] = "OFF"
            await publish(
                f"alarmmesh_simulation/synthetic{bsd_index}", states[bsd_index]
            )
            await wait_state(lambda: cap.resolve(bsd_binding) is not None)
        passed("real_mqtt_bsd_broadcast_prerequisite")
        await panel.groups.async_mutate(
            {
                "operation": "create",
                "revision": 0,
                "name": "Synthetic MQTT only",
                "members": sources,
                "linking": {"enabled": True, "bindings": bindings},
                "confirmed": True,
            },
            tuple(sources),
        )
        panel.linking.changed()
        await settle()
        states[0]["smoke"] = True
        await publish("alarmmesh_simulation/synthetic0", states[0])
        for _ in range(100):
            await asyncio.sleep(0.05)
            if hass.states.is_state(sources[0], "on"):
                break
        await settle()
        observed = dict([await asyncio.wait_for(messages.get(), 10) for _ in bindings])
        for index, row in enumerate(MQTT[1:], 1):
            payload = observed[f"alarmmesh_simulation/synthetic{index}/set/{row[3]}"]
            require(
                (json.loads(payload) if isinstance(row[-2], dict) else payload)
                == row[-2],
                f"Unexpected real MQTT payload for {row[-1]}",
            )
            passed("mqtt_action_" + row[-1])
        # Test the extra Heiman family through a genuinely discovered target too.
        states[0]["smoke"] = False
        await publish("alarmmesh_simulation/synthetic0", states[0])
        await asyncio.sleep(0.1)
        await settle()
        group = panel.groups.groups[0]
        heiman = cap.describe(sources[0])["controls"][0]
        await panel.groups.async_mutate(
            {
                "operation": "update",
                "group_id": group["id"],
                "revision": panel.groups.revision,
                "name": group["name"],
                "members": sources,
                "linking": {
                    "enabled": True,
                    "bindings": [
                        {
                            k: heiman[k]
                            for k in ("source", "target", "profile", "identity")
                        }
                    ],
                },
                "confirmed": True,
            },
            tuple(sources),
        )
        states[1]["smoke"] = True
        await publish("alarmmesh_simulation/synthetic1", states[1])
        await asyncio.sleep(0.1)
        panel.linking.changed()
        await settle()
        topic, payload = await asyncio.wait_for(messages.get(), 10)
        require(
            topic.endswith("synthetic0/set/siren_for_automation_only")
            and payload == "smoke_siren",
            "Heiman MQTT payload",
        )
        passed("mqtt_action_heiman_activation_mqtt")
        engine = panel.linking
        require(
            await hass.config_entries.async_unload(entry.entry_id),
            "Driver unload failed",
        )
        states[1]["smoke"] = False
        await publish("alarmmesh_simulation/synthetic1", states[1])
        engine.changed()
        await hass.async_block_till_done()
        require(engine._closed and messages.empty(), "Retired engine sent command")
        passed("real_mqtt_unload_no_commands")
        current = "offline_zha"
        await zha_checks(passed)
        report["result"] = "PASS"
    except Exception as exc:
        report["scenarios"][current] = "FAIL"
        report["error_type"] = type(exc).__name__
        (root / "driver-failure-traceback.log").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
    finally:
        if mqtt:
            await asyncio.to_thread(mqtt.disconnect)
            mqtt.loop_stop()
        if hass:
            await hass.async_stop(force=True)
        (root / "driver-result.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ha-version", required=True, choices=("2026.10.4", "2026.11.1")
    )
    sys.exit(asyncio.run(main(parser.parse_args().ha_version)))
