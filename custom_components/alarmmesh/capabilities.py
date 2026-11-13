"""Read cached registries/states only; a model name alone never authorizes control."""

import hashlib
import json
from dataclasses import asdict, dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


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

    def binding(self) -> dict:
        return {
            key: getattr(self, key)
            for key in ("source", "target", "profile", "identity")
        }


class Capabilities:
    """Conservative discovery; no reads from Zigbee/MQTT and no action calls."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

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
        if not entity or entity.platform != "mqtt" or not device:
            return ()
        ids = [
            value.removeprefix("zigbee2mqtt_")
            for domain, value in device.identifiers
            if domain == "mqtt" and value.startswith("zigbee2mqtt_")
        ]
        if len(ids) != 1:
            return ()
        prefix = f"{ids[0]}_smoke_"
        if not entity.unique_id.startswith(prefix) or not (
            base := entity.unique_id.removeprefix(prefix)
        ):
            return ()
        unique_id = f"{ids[0]}_{property_name}_{base}"
        return tuple(
            e
            for e in self.related(source)
            if e.platform == "mqtt" and e.unique_id == unique_id and not e.disabled_by
        )

    def test_blocked(self, source: str) -> bool:
        """An observed test never initiates or clears a smoke incident."""
        related = list(self.mqtt_property(source, "test"))
        related += [
            e
            for e in self.related(source)
            if e.platform == "zha" and e.translation_key in {"test", "self_test"}
        ]
        return any(
            (state := self.hass.states.get(e.entity_id)) is not None
            and state.state == "on"
            for e in related
        )

    def describe(self, source: str) -> dict:
        entity = er.async_get(self.hass).async_get(source)
        device = (
            dr.async_get(self.hass).async_get(entity.device_id)
            if entity and entity.device_id
            else None
        )
        origin = (
            entity.platform
            if entity and entity.platform in {"mqtt", "zha"}
            else "unknown_origin"
        )
        if entity and self.mqtt_property(source, "smoke"):
            origin = "zigbee2mqtt"
        result = {
            "origin": origin,
            "status": "detection_only",
            "reason": "no_verified_profile",
            "controls": [],
            "test_active": self.test_blocked(source),
            "physical_tested": False,
        }
        if not device or not entity or entity.disabled_by:
            return result
        source_state = self.hass.states.get(source)
        device_class = (
            entity.device_class
            or (source_state.attributes.get("device_class") if source_state else None)
            or entity.original_device_class
        )
        if entity.domain != "binary_sensor" or device_class != "smoke":
            result.update(reason="source_identity_changed")
            return result
        other_smoke = [
            e
            for e in self.related(source)
            if e.entity_id != source
            and not e.disabled_by
            and e.domain == "binary_sensor"
            and (e.device_class or e.original_device_class) == "smoke"
        ]
        if other_smoke:
            result.update(status="not_confirmed", reason="ambiguous_control")
            return result
        model = (device.model_id or device.model or "").casefold()
        # Older Z2M discovery appended the exact model to its description.
        aliases = {"jy-gz-01aq", "lumi.sensor_smoke.acn03", "hs1sa-e-plus", "smszb-120"}
        model = next(
            (m for m in aliases if model == m or model.endswith(f" ({m})")), model
        )
        vendor = (device.manufacturer or "").casefold()
        profile = None
        candidates = ()
        if (
            origin == "zigbee2mqtt"
            and model in {"jy-gz-01aq", "lumi.sensor_smoke.acn03"}
            and vendor in {"aqara", "lumi"}
        ):
            profile = "aqara_mqtt"
            candidates = self.mqtt_property(source, "buzzer")
            settings = self.mqtt_property(source, "linkage_alarm")
            setting = (
                self.hass.states.get(settings[0].entity_id)
                if len(settings) == 1
                else None
            )
            if not setting or settings[0].domain != "switch" or setting.state != "on":
                result.update(status="setting_needed", reason="aqara_linkage_required")
            if (device.sw_version or "").strip() in {"21", "0021", "0.0.0_0021"}:
                result.update(status="not_confirmed", reason="aqara_firmware_21")
        elif origin == "zigbee2mqtt" and model == "hs1sa-e-plus" and vendor == "heiman":
            profile = "heiman_mqtt"
            candidates = self.mqtt_property(source, "siren_for_automation_only")
        elif (
            model == "smszb-120"
            and vendor in {"develco", "develco products a/s", "frient", "frient a/s"}
            and origin in {"zha", "zigbee2mqtt"}
        ):
            profile = "smszb_zha" if origin == "zha" else "smszb_mqtt"
            candidates = tuple(
                e
                for e in self.related(source)
                if e.platform == entity.platform
                and e.domain == "siren"
                and not e.disabled_by
            )
        elif origin == "zha" and model in aliases:
            result.update(status="not_confirmed", reason="zha_route_unconfirmed")
            return result
        if not profile:
            return result
        if len(candidates) != 1:
            result.update(
                status="not_confirmed",
                reason="ambiguous_control" if candidates else "control_missing",
            )
            return result
        target = candidates[0]
        state = self.hass.states.get(target.entity_id)
        if not state or state.state in {"unknown", "unavailable"}:
            result.update(status="not_confirmed", reason="control_unavailable")
            return result
        action = {
            "domain": "select",
            "service": "select_option",
            "option": "alarm" if profile == "aqara_mqtt" else "smoke_siren",
            "safe_stop": profile == "heiman_mqtt",
        }
        if profile in {"aqara_mqtt", "heiman_mqtt"}:
            expected = (
                {"alarm", "mute"}
                if profile == "aqara_mqtt"
                else {"smoke_siren", "stop"}
            )
            options = state.attributes.get("options")
            if (
                target.domain != "select"
                or not isinstance(options, list)
                or not expected <= set(o for o in options if isinstance(o, str))
            ):
                result.update(status="not_confirmed", reason="invalid_control_options")
                return result
        else:
            features = state.attributes.get("supported_features", 0)
            tones = state.attributes.get("available_tones", [])
            required = 21 if profile == "smszb_mqtt" else 17
            if type(features) is not int or features & required != required:
                result.update(status="not_confirmed", reason="siren_features_missing")
                return result
            tone = "burglar" if profile == "smszb_mqtt" else "Burglar"
            if (features & 4 or profile == "smszb_mqtt") and (
                not isinstance(tones, list) or tone not in tones
            ):
                result.update(status="not_confirmed", reason="siren_tone_missing")
                return result
            action = {
                "domain": "siren",
                "service": "turn_on",
                "duration": 60,
                "tone": tone if features & 4 else None,
            }
        if not self.hass.services.has_service(action["domain"], action["service"]):
            result.update(status="not_confirmed", reason="service_missing")
            return result
        fingerprint = [
            entity.unique_id,
            entity.config_entry_id,
            target.unique_id,
            target.config_entry_id,
            device.id,
            origin,
            model,
            vendor,
            profile,
        ]
        identity = hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()
        control = Control(source, target.entity_id, profile, identity, **action)
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
