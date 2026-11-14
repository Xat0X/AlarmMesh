"""Reviewed HA action contracts; catalog names alone never authorize execution."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Profile:
    provider: str
    domain: str
    key: str | None = None
    option: str | None = None
    options: tuple[str, ...] = ()
    idle: tuple[str, ...] = ("off",)
    features: int = 0
    tone: str | None = None
    optional_tone: bool = False
    duration: int | None = None
    gate: tuple[str, str] | tuple[str, str, str] | None = None
    blocked_firmware: tuple[str, ...] = ()
    safe_stop: bool = False
    legacy_identity: bool = False

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


PROFILES = {
    "heiman_mqtt": Profile(
        "zigbee2mqtt",
        "select",
        "siren_for_automation_only",
        "smoke_siren",
        ("smoke_siren", "stop"),
        ("stop",),
        safe_stop=True,
        legacy_identity=True,
    ),
    "aqara_mqtt": Profile(
        "zigbee2mqtt",
        "select",
        "buzzer",
        "alarm",
        ("alarm", "mute"),
        ("mute",),
        gate=("switch", "linkage_alarm"),
        blocked_firmware=("21", "0021", "0.0.0_0021"),
        legacy_identity=True,
    ),
    "smszb_mqtt": Profile(
        "zigbee2mqtt",
        "siren",
        features=21,
        tone="burglar",
        duration=60,
        legacy_identity=True,
    ),
    "smszb_zha": Profile(
        "zha",
        "siren",
        features=17,
        tone="Burglar",
        optional_tone=True,
        duration=60,
        legacy_identity=True,
    ),
    "heiman_activation_mqtt": Profile(
        "zigbee2mqtt",
        "select",
        "siren_for_automation_only",
        "smoke_siren",
        ("smoke_siren", "stop"),
        ("stop",),
    ),
    "ias_mqtt": Profile(
        "zigbee2mqtt", "siren", features=21, tone="burglar", duration=60
    ),
    "ias_zha": Profile("zha", "siren", features=21, tone="Burglar", duration=60),
    "basic_ias_zha": Profile(
        "zha",
        "siren",
        features=17,
        tone="Burglar",
        optional_tone=True,
        duration=60,
    ),
    "aqara_zha": Profile(
        "zha",
        "switch",
        "buzzer_manual_alarm",
        gate=("switch", "linkage_alarm"),
        blocked_firmware=("21", "0021", "0.0.0_0021"),
    ),
    "bosch_twinguard_mqtt": Profile(
        "zigbee2mqtt",
        "select",
        "alarm",
        "fire",
        ("fire", "stop"),
        ("stop",),
    ),
    "bosch_bsd_mqtt": Profile(
        "zigbee2mqtt",
        "siren",
        "alarm_control",
        features=5,
        tone="smoke",
        gate=("switch", "broadcast_alarms", "off"),
    ),
    "shina_mqtt": Profile(
        "zigbee2mqtt",
        "switch",
        "force_smoke_alarm",
        gate=("binary_sensor", "remote_control_permission"),
    ),
}

# Frozen beta.2 contracts retain existing saved fingerprints. A changed legacy
# contract must receive a new identity (and admin review), never silent powers.
LEGACY_DIGESTS = {
    "heiman_mqtt": "bde55efd5c75eeec24eb18f880ee048d797b48fdc82d4cf3ce4d66c420e92e61",
    "aqara_mqtt": "45281253b3f6732e255b91240f8a03a2478384f831ad2f369126ec5de59a618d",
    "smszb_mqtt": "7cac8b565d9b39ce3fea0661245b8d569faf78cabd1e52fbf80f0c02f1d6fe1d",
    "smszb_zha": "907f7c474cf02a3bc29028cdc5e90c25e84253a1e1d20711ec73b4d3ea114ad0",
}


def validate_profiles() -> None:
    for name, profile in PROFILES.items():
        if profile.provider not in {"zigbee2mqtt", "zha"} or profile.domain not in {
            "select",
            "siren",
            "switch",
        }:
            raise ValueError("Unreviewed action adapter")
        if profile.gate and (
            len(profile.gate) not in (2, 3)
            or profile.gate[0] not in {"switch", "binary_sensor"}
            or (len(profile.gate) == 3 and profile.gate[2] not in {"on", "off"})
        ):
            raise ValueError("Invalid prerequisite contract")
        if profile.duration is not None and not 1 <= profile.duration <= 60:
            raise ValueError("Unbounded sounder duration")
        if profile.safe_stop and name != "heiman_mqtt":
            raise ValueError("Unreviewed stop authority")
        if profile.legacy_identity and LEGACY_DIGESTS.get(name) != profile.digest():
            raise ValueError("Changed legacy authority requires a new profile identity")


validate_profiles()
