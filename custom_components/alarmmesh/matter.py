"""HA registry contracts only. No Matter client, network data or cluster commands."""

import asyncio
import hashlib
import json
import re

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .automation import AutomationError

DATA_SOURCES = "alarmmesh_matter_source_identities"
HA_SOURCE = "https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/matter/"
# HA 2026.10.4 and 2026.11.1 descriptions; not entity-id suffix matching.
CONTRACTS = {
    "smoke": ("binary_sensor", "SmokeCoAlarmSmokeStateSensor", 92, 1),
    "co": ("binary_sensor", "SmokeCoAlarmCOStateSensor", 92, 2),
    "battery_low": ("binary_sensor", "SmokeCoAlarmBatteryAlertSensor", 92, 3),
    "muted": ("binary_sensor", "SmokeCoAlarmDeviceMutedSensor", 92, 4),
    "test_in_progress": ("binary_sensor", "SmokeCoAlarmTestInProgressSensor", 92, 5),
    "fault": ("binary_sensor", "SmokeCoAlarmHardwareFaultAlertSensor", 92, 6),
    "end_of_service": ("binary_sensor", "SmokeCoAlarmEndfOfServiceSensor", 92, 7),
    "interconnect_smoke": (
        "binary_sensor",
        "SmokeCoAlarmInterconnectSmokeAlarmSensor",
        92,
        8,
    ),
    "interconnect_co": (
        "binary_sensor",
        "SmokeCoAlarmInterconnectCOAlarmSensor",
        92,
        9,
    ),
    "self_test_request": ("button", "SmokeCoAlarmSelfTestRequest", 92, 65529),
    "battery": ("sensor", "PowerSource", 47, 12),
    "battery_charge_low": ("binary_sensor", "BatteryChargeLevel", 47, 14),
    "contamination_state": ("sensor", "SmokeCOAlarmContaminationState", 92, 10),
    "expiry_date": ("sensor", "SmokeCOAlarmExpiryDate", 92, 12),
}


def path(entity):
    """Treat HA's device prefix as opaque. Never decode or export network IDs."""
    if entity is None or entity.platform != "matter":
        return None
    match = re.fullmatch(
        r"(.+)-(\d+)-([A-Za-z][A-Za-z0-9_]*)-(\d+)-(\d+)", entity.unique_id
    )
    if match is None:
        return None
    root, endpoint, key, cluster, attribute = match.groups()
    return root, int(endpoint), key, int(cluster), int(attribute)


def is_contract(entity, key):
    p = path(entity)
    contract = CONTRACTS[key]
    return bool(p and entity.domain == contract[0] and p[2:] == contract[1:])


def is_co_source(hass, source):
    entity = er.async_get(hass).async_get(source)
    return is_contract(entity, "co") or is_contract(entity, "interconnect_co")


def fingerprint(hass, source):
    entity = er.async_get(hass).async_get(source)
    device = (
        dr.async_get(hass).async_get(entity.device_id)
        if entity and entity.device_id
        else None
    )
    config = (
        hass.config_entries.async_get_entry(entity.config_entry_id)
        if entity and entity.config_entry_id
        else None
    )
    if (
        not entity
        or entity.platform != "matter"
        or not device
        or not path(entity)
        or not config
        or config.domain != "matter"
        or entity.config_entry_id != device.config_entry_id
        or not any(domain == "matter" for domain, _ in device.identifiers)
    ):
        return None
    return hashlib.sha256(
        json.dumps(
            [
                entity.id,
                entity.unique_id,
                entity.config_entry_id,
                device.id,
                device.via_device_id,
                device.manufacturer,
                device.model,
                device.model_id,
                sorted(device.identifiers),
            ]
        ).encode()
    ).hexdigest()


def identity_changed(hass, source):
    owner = hass.data.get(DATA_SOURCES)
    return bool(
        owner
        and (owner.error or owner.identities.get(source) != fingerprint(hass, source))
    )


def properties(hass, source, key):
    """Exact provider + HA config entry + device + opaque prefix + endpoint."""
    registry = er.async_get(hass)
    entity = registry.async_get(source)
    p = path(entity)
    config = (
        hass.config_entries.async_get_entry(entity.config_entry_id)
        if entity and entity.config_entry_id
        else None
    )
    if (
        not p
        or not entity.device_id
        or not config
        or config.domain != "matter"
        or not (
            is_contract(entity, "smoke") or is_contract(entity, "interconnect_smoke")
        )
    ):
        return ()
    rows = tuple(
        e
        for e in er.async_entries_for_device(registry, entity.device_id)
        if not e.disabled_by
        and e.platform == "matter"
        and e.config_entry_id == entity.config_entry_id
        and is_contract(e, key)
        and path(e)[:2] == p[:2]
    )
    return (
        properties(hass, source, "battery_charge_low")
        if key == "battery_low" and not rows
        else rows
    )


def transport(hass, source):
    """Read diagnostic entity identity only, never any Thread/Wi-Fi value."""
    entity = er.async_get(hass).async_get(source)
    p = path(entity)
    device = (
        dr.async_get(hass).async_get(entity.device_id)
        if entity and entity.device_id
        else None
    )
    if not p or not device:
        return "unknown"
    if device.via_device_id and not p[0].endswith("-MatterNodeDevice"):
        return "bridge"
    kinds = set()
    for e in er.async_entries_for_device(er.async_get(hass), device.id):
        ep = path(e)
        if (
            not ep
            or ep[0] != p[0]
            or ep[1] not in {0, p[1]}
            or e.config_entry_id != entity.config_entry_id
            or e.domain != "sensor"
        ):
            continue
        if ep[2:] in {
            ("ThreadDiagnosticsChannel", 53, 0),
            ("ThreadDiagnosticsRoutingRole", 53, 1),
        }:
            kinds.add("thread")
        if ep[2:] == ("WiFiDiagnosticsRssi", 54, 4):
            kinds.add("wifi")
    return next(iter(kinds)) if len(kinds) == 1 else "unknown"


def source_kind(hass, source):
    entity = er.async_get(hass).async_get(source)
    return (
        "local_smoke"
        if is_contract(entity, "smoke")
        else "interconnect_smoke"
        if is_contract(entity, "interconnect_smoke")
        else "unknown"
    )


def origin_allowed(hass, source):
    entity = er.async_get(hass).async_get(source)
    return bool(
        entity
        and fingerprint(hass, source)
        and source_kind(hass, source) == "local_smoke"
        and not identity_changed(hass, source)
        and not interconnect_unseparated(hass, source)
    )


def interconnect_unseparated(hass, source):
    from .catalog import recognize

    entity = er.async_get(hass).async_get(source)
    device = (
        dr.async_get(hass).async_get(entity.device_id)
        if entity and entity.device_id
        else None
    )
    entry = (
        recognize("matter", device.model or "", device.manufacturer or "")
        if device
        else None
    )
    return bool(
        entry
        and entry.get("native_interconnect")
        and not properties(hass, source, "interconnect_smoke")
    )


def describe(hass, source):
    kind = source_kind(hass, source)
    changed = identity_changed(hass, source)
    functions = []
    for key in (
        "smoke",
        "battery",
        "battery_low",
        "fault",
        "end_of_service",
        "test_in_progress",
        "self_test_request",
        "interconnect_smoke",
        "muted",
        "co",
    ):
        rows = properties(hass, source, key)
        available = (
            len(rows) == 1
            and (state := hass.states.get(rows[0].entity_id)) is not None
            and state.state != "unavailable"
            and (key == "self_test_request" or state.state != "unknown")
        )
        functions.append(
            {
                "key": key,
                "available": available,
                "reason": "matter_identity_changed"
                if changed
                else "matter_endpoint_ambiguous"
                if len(rows) > 1
                else "matter_entity_available"
                if available
                else "matter_entity_missing",
            }
        )
    functions.extend(
        {"key": key, "available": False, "reason": reason}
        for key, reason in (
            ("self_test_result", "matter_no_correlated_result"),
            ("activation", "matter_no_sounder_route"),
            ("stop", "matter_no_sounder_route"),
        )
    )
    return {
        "transport": transport(hass, source),
        "source_kind": kind,
        "identity_changed": changed,
        "origin_separation_missing": interconnect_unseparated(hass, source),
        "fingerprint": fingerprint(hass, source),
        "functions": functions,
        "evidence": HA_SOURCE + "binary_sensor.py",
    }


class MatterSources:
    """Pin selected registry identity; a replacement requires explicit admin review."""

    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.store = Store(
            hass, 1, f"alarmmesh.matter_sources.{entry.entry_id}", atomic_writes=True
        )
        self.identities, self.revision, self.error = {}, 0, None
        self.lock, self.closed = asyncio.Lock(), False

    async def load(self):
        try:
            data = await self.store.async_load()
            if data is not None:
                if (
                    not isinstance(data, dict)
                    or set(data) != {"schema", "revision", "identities"}
                    or type(data["schema"]) is not int
                    or data["schema"] != 1
                    or type(data["revision"]) is not int
                    or data["revision"] < 0
                    or not isinstance(data["identities"], dict)
                    or len(data["identities"]) > 256
                    or any(
                        not isinstance(k, str)
                        or not k.startswith("binary_sensor.")
                        or not isinstance(v, str)
                        or re.fullmatch("[a-f0-9]{64}", v) is None
                        for k, v in data["identities"].items()
                    )
                ):
                    raise ValueError
                self.identities, self.revision = data["identities"], data["revision"]
            selected = set(self.entry.runtime_data.source_entity_ids)
            # Explicitly selected new sources can be pinned once. Existing pins
            # are never overwritten by rename/replacement/reload or startup.
            current = {s: fingerprint(self.hass, s) for s in selected}
            pins = {s: v for s, v in self.identities.items() if s in selected}
            for source, value in current.items():
                if value and source not in self.identities:
                    pins[source] = value
            if len(pins) > 256:
                raise ValueError("Matter source identity limit")
            if pins != self.identities:
                await self.store.async_save(
                    {"schema": 1, "revision": self.revision, "identities": pins}
                )
                self.identities = pins
        except Exception:
            self.error = "matter_identity_storage_error"
        self.hass.data[DATA_SOURCES] = self

    async def review(self, source, identity, revision, confirmed):
        async with self.lock:
            await self._review(source, identity, revision, confirmed)

    async def _review(self, source, identity, revision, confirmed):
        if self.closed:
            raise AutomationError("not_loaded")
        if self.error:
            raise AutomationError(self.error)
        if type(revision) is not int or revision != self.revision:
            raise AutomationError("conflict")
        if (
            confirmed is not True
            or source not in self.entry.runtime_data.source_entity_ids
            or identity is None
            or fingerprint(self.hass, source) != identity
        ):
            raise AutomationError("matter_identity_changed")
        pins = {**self.identities, source: identity}
        await self.store.async_save(
            {"schema": 1, "revision": self.revision + 1, "identities": pins}
        )
        self.identities, self.revision = pins, self.revision + 1

    async def close(self):
        async with self.lock:
            self.closed = True
            if self.hass.data.get(DATA_SOURCES) is self:
                self.hass.data.pop(DATA_SOURCES)
