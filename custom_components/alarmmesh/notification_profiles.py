"""Reviewed Companion payloads, never phone permission or delivery assertions.

Contracts and bundled filenames: docs/phone-alerts.md (2026-11-17).
No audio is shipped, downloaded or played by AlarmMesh.
"""

import hashlib
import json
import math
import re
from copy import deepcopy

from homeassistant.util import slugify

IOS_SOUNDS = {
    "default": "sound_default",
    "US-EN-Alexa-Smoke-Detected-Generic.wav": "sound_smoke",
    "US-EN-Alexa-Smoke-Detected-In-Kitchen.wav": "sound_kitchen",
    "US-EN-Alexa-Smoke-Detected-In-Garage.wav": "sound_garage",
}


class ProfileError(ValueError):
    """Allowlisted public error, without registration data."""


def receiver_metadata(hass, target):
    """Match an unambiguous mobile_app registration, never guess from its name."""
    service = hass.services.async_services().get("notify", {}).get(target)
    matches = [
        entry
        for entry in hass.config_entries.async_entries("mobile_app")
        if isinstance(entry.data.get("device_name"), str)
        and "mobile_app_" + slugify(entry.data["device_name"]) == target
    ]
    if len(matches) == 1:
        entry = matches[0]
        os_name = str(entry.data.get("os_name", "")).lower()
        platform = {"ios": "ios", "android": "android"}.get(os_name, "unknown")
        identity = [entry.entry_id, entry.unique_id, entry.data.get("device_id")]
        origin = "metadata" if platform != "unknown" else "user"
        scope = "registration"
    else:
        platform, origin, scope = "unknown", "user", "session"
        # Without a reliable registration, a restart/replacement requires review.
        # This binding is deliberately not represented as a durable phone identity.
        identity = [target, id(service)]
    return {
        "platform": platform,
        "origin": origin,
        "identity_scope": scope,
        "identity": hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        if service
        else "",
    }


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ProfileError("invalid_phone_profile")
    common = {"version", "platform", "origin", "identity", "critical"}
    ios = {"sound", "sound_source", "volume"}
    if (
        set(profile) != common | (ios if profile.get("platform") == "ios" else set())
        or any(
            not isinstance(profile.get(k), str)
            for k in ("platform", "origin", "identity")
        )
        or type(profile.get("version")) is not int
        or profile["version"] != 1
        or profile.get("platform") not in {"unknown", "ios", "android"}
        or profile.get("origin") not in {"user", "metadata"}
        or type(profile.get("critical")) is not bool
        or not isinstance(profile.get("identity"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", profile["identity"])
        or profile["critical"]
        and profile["platform"] == "unknown"
    ):
        raise ProfileError("invalid_phone_profile")
    if profile["platform"] == "ios":
        sound, volume = profile["sound"], profile["volume"]
        if (
            not isinstance(sound, str)
            or not isinstance(profile["sound_source"], str)
            or profile["sound_source"] not in {"bundled", "imported"}
            or profile["sound_source"] == "bundled"
            and sound not in IOS_SOUNDS
            or profile["sound_source"] == "imported"
            and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,95}\.(wav|caf|aiff)", sound
            )
            or type(volume) not in {int, float}
            or not math.isfinite(volume)
            or not 0 <= volume <= 1
        ):
            raise ProfileError("invalid_phone_sound")


def check_profile(hass, target, profile):
    validate_profile(profile)
    current = receiver_metadata(hass, target)
    if profile["identity"] != current["identity"]:
        raise ProfileError("phone_identity_changed")
    if (
        current["platform"] != "unknown"
        and current["platform"] != profile["platform"]
        or profile["origin"] == "metadata"
        and current["platform"] == "unknown"
    ):
        raise ProfileError("phone_platform_changed")


def build_plan(hass, target, profile, message, *, smoke):
    """One side-effect-free plan for preview, explicit test and incident dispatch."""
    payload = deepcopy(message)
    if profile is None:
        return payload  # beta.11 ordinary messages remain byte-for-byte equivalent.
    check_profile(hass, target, profile)
    data = payload.setdefault("data", {})
    if profile["platform"] == "android" and "url" in data:
        data["clickAction"] = data.pop("url")
    if not smoke:
        return payload  # Recovery is ordinary, including default sound.
    if profile["platform"] == "ios":
        sound = profile["sound"]
        if profile["critical"]:
            sound = {"name": sound, "critical": 1, "volume": profile["volume"]}
        data["push"] = {"sound": sound}
    elif profile["platform"] == "android" and profile["critical"]:
        data.update(priority="high", ttl=0, channel="alarm_stream")
    return payload
