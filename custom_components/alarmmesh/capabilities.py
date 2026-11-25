"""Read cached registries/states only; a model name alone never authorizes control."""

import hashlib
import json
from dataclasses import asdict, dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from . import matter, zwave
from .catalog import action_profile, recognize
from .const import DOMAIN
from .profiles import PROFILES
from .runtime import is_alecto_source, mqtt_source_parts


@dataclass(frozen=True)
class Control:
    """An exact, reviewed HA action, bound to source and target registry identity."""

    source: str
    target: str
    profile: str
    identity: str
    domain: str
    service: str
    option: str | None = None
    tone: str | None = None
    duration: int | None = None
    safe_stop: bool = False
    idle_states: tuple[str, ...] = ("off",)

    def binding(self) -> dict:
        return {
            key: getattr(self, key)
            for key in ("source", "target", "profile", "identity")
        }


class Capabilities:
    """Conservative discovery; no reads from Zigbee/MQTT and no action calls."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    def source_identity_changed(self, source: str) -> bool:
        """Identity/provenance contradictions block execution, never clear smoke."""
        entity = er.async_get(self.hass).async_get(source)
        state = self.hass.states.get(source)
        if source.startswith("sensor."):
            return not is_alecto_source(self.hass, entity)
        device_class = (
            (entity.device_class if entity else None)
            or (state.attributes.get("device_class") if state else None)
            or (entity.original_device_class if entity else None)
        )
        return (
            source.partition(".")[0] != "binary_sensor"
            or (entity is not None and entity.platform == DOMAIN)
            or (device_class is not None and device_class != "smoke")
            or zwave.invalid_source(self.hass, source)
            or entity is not None
            and entity.platform == "matter"
            and (
                matter.identity_changed(self.hass, source)
                or matter.is_contract(entity, "co")
                or matter.is_contract(entity, "interconnect_co")
                or matter.interconnect_unseparated(self.hass, source)
            )
        )

    def related(self, source: str) -> tuple:
        registry = er.async_get(self.hass)
        entity = registry.async_get(source)
        return (
            tuple(er.async_entries_for_device(registry, entity.device_id))
            if entity and entity.device_id
            else ()
        )

    def mqtt_property(self, source: str, property_name: str) -> tuple:
        """Use Z2M's documented registry unique-ID structure, never display names."""
        entity = er.async_get(self.hass).async_get(source)
        device = (
            dr.async_get(self.hass).async_get(entity.device_id)
            if entity and entity.device_id
            else None
        )
        parts = mqtt_source_parts(entity, device)
        if not parts:
            return ()
        mqtt_id, base = parts
        unique_id = f"{mqtt_id}_{property_name}_{base}"
        # Writable binary exposes use a switch_ discovery object ID. The shorter
        # form is also used by existing installations and other entity types.
        switch_id = f"{mqtt_id}_switch_{property_name}_{base}"
        return tuple(
            e
            for e in self.related(source)
            if e.platform == "mqtt"
            and (
                e.unique_id == unique_id
                or (e.domain == "switch" and e.unique_id == switch_id)
            )
            and not e.disabled_by
            and e.config_entry_id == entity.config_entry_id
        )

    def metadata(self, source: str) -> tuple:
        entity = er.async_get(self.hass).async_get(source)
        device = (
            dr.async_get(self.hass).async_get(entity.device_id)
            if entity and entity.device_id
            else None
        )
        origin = (
            entity.platform
            if entity and entity.platform in {"mqtt", "zha", "matter", "zwave_js"}
            else "unknown_origin"
        )
        if is_alecto_source(self.hass, entity) or (
            entity
            and entity.domain == "binary_sensor"
            and self.mqtt_property(source, "smoke")
        ):
            origin = "zigbee2mqtt"
        model = (
            (
                (device.model or "")
                if origin in {"matter", "zwave_js"}
                else (device.model_id or device.model or "")
            )
            if device
            else ""
        )
        vendor = (device.manufacturer or "") if device else ""
        catalog = recognize(origin, model, vendor)
        if (
            origin == "matter"
            and catalog
            and catalog.get("product_id") is not None
            and device.model_id
            and str(device.model_id) != str(catalog["product_id"])
        ):
            catalog = None
        return entity, device, origin, model, vendor, catalog

    def bound(self, source: str) -> tuple:
        entity = er.async_get(self.hass).async_get(source)
        return tuple(
            e
            for e in self.related(source)
            if entity
            and not e.disabled_by
            and e.platform == entity.platform
            and e.config_entry_id == entity.config_entry_id
        )

    def _property(self, source: str, origin: str, key: str) -> tuple:
        if origin == "zwave_js":
            return ()  # Never infer test/control contracts from translation keys.
        if origin == "matter":
            return (
                matter.properties(self.hass, source, key)
                if key in matter.CONTRACTS
                else ()
            )
        return (
            self.mqtt_property(source, key)
            if origin == "zigbee2mqtt"
            else tuple(e for e in self.bound(source) if e.translation_key == key)
        )

    def test_blocked(self, source: str) -> bool:
        """Only observed test status is read; commands/settings are never executed."""
        _, _, origin, _, _, catalog = self.metadata(source)
        flags = {"test": ["on"]}
        if origin == "matter":
            flags["test_in_progress"] = ["on"]
        if origin == "zigbee2mqtt" and catalog:
            flags.update(catalog["test_flags"])
        if origin == "zha":
            flags.update(
                {
                    "self_test": ["on"],
                    "self_test_state": ["on"],
                    "test_in_progress": ["on"],
                }
            )
        return any(
            (state := self.hass.states.get(e.entity_id)) is not None
            and state.state.casefold() in active
            for key, active in flags.items()
            for e in self._property(source, origin, key)
        )

    def details(self, source: str) -> dict:
        """Cached HA values, with change times; never infer last radio contact."""
        _, device, origin, _, _, catalog = self.metadata(source)
        values = []
        maintenance = {"battery_percent": None, "battery_low": None, "fault": None}
        expected = {
            "battery",
            "battery_low",
            "battery_state",
            "checking_result",
            "smoke_battery",
            "fault",
            "fault_state",
            "trouble",
            "chamber_contamination",
            "test",
            "self_test",
            "self_test_result",
            "test_alarm_result",
            "test_in_progress",
            "test_mode",
            "halo_test_result",
            "smoke_level",
        }
        if origin == "matter":
            maintenance["end_of_service"] = None
            entities = [
                (key, e)
                for key in matter.CONTRACTS
                if key not in {"smoke", "self_test_request", "battery_charge_low"}
                for e in matter.properties(self.hass, source, key)
            ]
        elif origin == "zwave_js":
            entities = zwave.properties(self.hass, source)
        elif origin == "zigbee2mqtt":
            props = (
                catalog["providers"][origin]["information"]
                if catalog
                else ["battery", "battery_low", "test"]
            )
            entities = [
                (key, e)
                for key in props
                if key in expected
                for e in self.mqtt_property(source, key)
            ]
        else:
            entities = []
            for e in self.bound(source):
                state = self.hass.states.get(e.entity_id)
                cls = (
                    e.device_class
                    or e.original_device_class
                    or (state.attributes.get("device_class") if state else None)
                )
                if e.domain == "sensor" and cls == "battery":
                    entities.append(("battery", e))
                elif e.domain == "binary_sensor" and cls in {"battery", "problem"}:
                    entities.append(("battery_low" if cls == "battery" else "fault", e))
                elif e.translation_key in expected | {"self_test_state"}:
                    entities.append((e.translation_key, e))
        for key, e in entities:
            state = self.hass.states.get(e.entity_id)
            value = (
                state.state
                if state and state.state not in {"unknown", "unavailable"}
                else None
            )
            if key == "battery" and value is not None:
                try:
                    value = float(value)
                    if not 0 <= value <= 100:
                        value = None
                except ValueError, TypeError:
                    value = None
                if (
                    value is not None
                    and e.domain == "sensor"
                    and state.attributes.get("unit_of_measurement") in (None, "%")
                ):
                    old = maintenance["battery_percent"]
                    maintenance["battery_percent"] = (
                        min(old, value) if old is not None else value
                    )
            # Only documented same-device binary entities can supply flags.
            # Missing/invalid values stay unknown; one positive flag wins over off.
            flag = (
                "battery_low"
                if key == "battery_low"
                else "fault"
                if key in {"fault", "fault_state", "trouble"}
                else "end_of_service"
                if key == "end_of_service"
                else None
            )
            if flag and e.domain == "binary_sensor" and value in {"on", "off"}:
                maintenance[flag] = maintenance[flag] is True or value == "on"
            values.append(
                {
                    "key": key,
                    "value": value,
                    "entity_id": e.entity_id,
                    "changed_at": state.last_changed.isoformat() if state else None,
                    "unit": state.attributes.get("unit_of_measurement")
                    if state
                    else None,
                }
            )
        return {
            "firmware": device.sw_version if device else None,
            "values": values,
            "recent_contact": None,
            "maintenance": maintenance,
        }

    def aqara_feedback(self, source):
        matches = self.mqtt_property(source, "buzzer_manual_alarm")
        if len(matches) == 1 and matches[0].domain == "binary_sensor":
            return matches[0]
        return None

    def describe(self, source: str) -> dict:
        entity, device, origin, raw_model, raw_vendor, catalog = self.metadata(source)
        result = {
            "origin": origin,
            "status": "detection_only",
            "reason": "no_verified_profile",
            "controls": [],
            "test_active": self.test_blocked(source),
            "physical_tested": False,
            "catalog_id": catalog["id"] if catalog else None,
            "kind": catalog["kind"] if catalog else None,
            "details": self.details(source),
        }
        if origin == "zwave_js":
            result.update(
                zwave=zwave.describe(self.hass, source),
                kind="smoke",
                reason="source_identity_changed"
                if self.source_identity_changed(source)
                else "zwave_observation_only",
            )
            return result
        if origin == "matter":
            info = matter.describe(self.hass, source)
            result.update(
                matter=info,
                reason="matter_identity_changed"
                if info["identity_changed"]
                else "matter_interconnect_unseparated"
                if info["origin_separation_missing"]
                else "matter_interconnect_origin"
                if info["source_kind"] == "interconnect_smoke"
                else "matter_origin_unknown"
                if info["source_kind"] != "local_smoke"
                else "matter_no_sounder_route",
            )
            return result
        if not device or not entity or entity.disabled_by:
            return result
        if is_alecto_source(self.hass, entity):
            return result
        source_state = self.hass.states.get(source)
        cls = (
            entity.device_class
            or (source_state.attributes.get("device_class") if source_state else None)
            or entity.original_device_class
        )
        if entity.domain != "binary_sensor" or cls != "smoke":
            result.update(reason="source_identity_changed")
            return result
        if any(
            e.entity_id != source
            and e.domain == "binary_sensor"
            and (e.device_class or e.original_device_class) == "smoke"
            for e in self.bound(source)
        ):
            result.update(status="not_confirmed", reason="ambiguous_control")
            return result
        name = (
            action_profile(catalog, origin, raw_model, raw_vendor) if catalog else None
        )
        if not name:
            return result
        profile = PROFILES[name]
        if profile.gate:
            domain, key = profile.gate[:2]
            required_state = profile.gate[2] if len(profile.gate) == 3 else "on"
            settings = self._property(source, origin, key)
            setting = (
                self.hass.states.get(settings[0].entity_id)
                if len(settings) == 1
                else None
            )
            if (
                not setting
                or settings[0].domain != domain
                or setting.state != required_state
            ):
                if key == "linkage_alarm":
                    if len(settings) > 1:
                        reason = "aqara_linkage_ambiguous"
                    elif not settings or settings[0].domain != domain:
                        reason = "aqara_linkage_missing"
                    elif not setting or setting.state not in {"on", "off"}:
                        reason = "aqara_linkage_unavailable"
                    else:
                        reason = "aqara_linkage_required"
                elif key == "broadcast_alarms":
                    reason = "bosch_broadcast_must_be_off"
                else:
                    reason = "remote_permission_required"
                result.update(status="setting_needed", reason=reason)
        if (device.sw_version or "").strip() in profile.blocked_firmware:
            result.update(status="not_confirmed", reason="aqara_firmware_21")
        candidates = (
            self._property(source, origin, profile.key)
            if profile.key
            else tuple(
                e
                for e in self.related(source)
                if e.domain == profile.domain
                and e.platform == entity.platform
                and not e.disabled_by
            )
        )
        if len(candidates) != 1:
            result.update(
                status="not_confirmed",
                reason="ambiguous_control" if candidates else "control_missing",
            )
            return result
        target = candidates[0]
        state = self.hass.states.get(target.entity_id)
        # Z2M exposes Aqara's buzzer as a write-only select. Read its actual
        # manual-alarm flag through the same device and discovery identity.
        feedback = self.aqara_feedback(source) if name == "aqara_mqtt" else None
        if (
            not state
            or state.state == "unavailable"
            or (state.state == "unknown" and name != "aqara_mqtt")
        ):
            result.update(status="not_confirmed", reason="control_unavailable")
            return result
        if (
            target.domain != profile.domain
            or target.config_entry_id != entity.config_entry_id
        ):
            result.update(status="not_confirmed", reason="invalid_control_options")
            return result
        action = {
            "domain": profile.domain,
            "service": "select_option" if profile.domain == "select" else "turn_on",
            "option": profile.option,
            "safe_stop": profile.safe_stop
            and not state.attributes.get("assumed_state", False),
            "idle_states": profile.idle,
        }
        if profile.domain == "select":
            options = state.attributes.get("options")
            if not isinstance(options, list) or not set(profile.options) <= {
                o for o in options if isinstance(o, str)
            }:
                result.update(status="not_confirmed", reason="invalid_control_options")
                return result
        elif profile.domain == "siren":
            features = state.attributes.get("supported_features", 0)
            if (
                not isinstance(features, int)
                or isinstance(features, bool)
                or features & profile.features != profile.features
            ):
                result.update(status="not_confirmed", reason="siren_features_missing")
                return result
            tones = state.attributes.get("available_tones", [])
            if (
                profile.tone
                and (features & 4 or not profile.optional_tone)
                and (not isinstance(tones, list) or profile.tone not in tones)
            ):
                result.update(status="not_confirmed", reason="siren_tone_missing")
                return result
            action.update(
                duration=profile.duration, tone=profile.tone if features & 4 else None
            )
        elif state.state not in {"on", "off"}:
            result.update(status="not_confirmed", reason="invalid_control_options")
            return result
        if not self.hass.services.has_service(action["domain"], action["service"]):
            result.update(status="not_confirmed", reason="service_missing")
            return result
        if name == "aqara_mqtt":
            observed = self.hass.states.get(feedback.entity_id) if feedback else None
            if not observed or observed.state not in {"on", "off"}:
                if result["status"] == "detection_only":
                    result.update(
                        status="not_confirmed", reason="aqara_feedback_needed"
                    )
                return result

        model, vendor = raw_model.casefold(), raw_vendor.casefold()
        # Normalize published legacy model names before binding the registry identities.
        if profile.legacy_identity:
            model = next(
                (
                    m
                    for m in {
                        "jy-gz-01aq",
                        "lumi.sensor_smoke.acn03",
                        "hs1sa-e-plus",
                        "smszb-120",
                    }
                    if model == m or model.endswith(f" ({m})")
                ),
                model,
            )
        fingerprint = [
            entity.unique_id,
            entity.config_entry_id,
            target.unique_id,
            target.config_entry_id,
            device.id,
            origin,
            model,
            vendor,
            name,
        ]
        if not profile.legacy_identity:
            fingerprint.extend(
                [
                    profile.digest(),
                    [(e.unique_id, e.config_entry_id) for e in settings]
                    if profile.gate
                    else [],
                ]
            )
        if feedback:
            # Existing Aqara assignments require review before this readback
            # can authorize a command with an unknown select value.
            fingerprint.extend(
                [feedback.id, feedback.unique_id, feedback.config_entry_id]
            )
        identity = hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()
        control = Control(source, target.entity_id, name, identity, **action)
        result["controls"] = [asdict(control)]
        if result["status"] == "detection_only":
            result.update(
                status="linkable",
                reason="automation_stop_separate"
                if control.safe_stop
                else "no_safe_stop",
            )
        return result

    def resolve(self, binding: dict) -> Control | None:
        info = self.describe(binding.get("source", ""))
        if info["status"] != "linkable":
            return None
        for data in info["controls"]:
            control = Control(**data)
            if control.binding() == binding:
                return control
        return None

    def is_idle(self, control: Control) -> bool:
        """Shared read-only idle test; never adopt manual/external sounding."""
        state = self.hass.states.get(control.target)
        if control.profile == "aqara_mqtt":
            feedback = self.aqara_feedback(control.source)
            return bool(
                state
                and state.state in {"unknown", "alarm", "mute"}
                and feedback
                and self.hass.states.is_state(feedback.entity_id, "off")
            )
        return state is not None and state.state in control.idle_states
