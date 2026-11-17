"""Bounded configuration and current HA targets; no arbitrary service payloads."""

import asyncio
import hashlib
import json
import re
from copy import deepcopy

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

MAX_RECIPIENTS = 20
MAX_SCRIPTS = 20
DEFAULT_NOTIFICATIONS = {"enabled": False, "recovery": False, "recipients": []}
DEFAULT_ACTIONS = {"enabled": False, "start": [], "recovery": []}


class AutomationError(ValueError):
    """Public translated rejection code; provider exception text stays private."""


def script_receipt_key(phase: str, binding: dict) -> str:
    return f"{phase}:{binding['entity_id']}:{binding['identity']}"


def notification_plan(old, phase, active, origins, explicitly_clear):
    """Pure receipt decision, shared with the non-executing action example."""
    seen = (
        [
            source
            for source in old["seen"]
            if phase != "start" or not explicitly_clear(source)
        ]
        if old
        else []
    )
    needed = not (
        old
        and old["phase"] == phase
        and (active if phase == "start" else set(origins)) <= set(seen)
    ) and not (phase == "recovery" and old is None)
    return needed, seen


def recipients(hass: HomeAssistant) -> list[dict]:
    """Companion's documented legacy notify services, actually registered now."""
    return [
        {"service": name, "name": name.removeprefix("mobile_app_")}
        for name in sorted(hass.services.async_services().get("notify", {}))
        if re.fullmatch(r"mobile_app_[a-z0-9_]+", name)
    ]


async def send_notification(hass: HomeAssistant, target: str, message: dict) -> None:
    """Shared Companion route; callers construct bounded messages server-side."""
    if target not in {row["service"] for row in recipients(hass)}:
        raise AutomationError("recipient_unavailable")
    await hass.services.async_call("notify", target, message, blocking=True)


def notification_route(
    hass,
    settings,
    target,
    *,
    phase="start",
    source_allowed=True,
    paused=False,
    fault=None,
):
    """Shared configuration gate for execution and read-only route inspection."""
    chosen = next((r for r in settings["recipients"] if r["service"] == target), None)
    selected = bool(chosen and chosen["enabled"])
    available = target in {row["service"] for row in recipients(hass)}
    reason = (
        "execution_paused"
        if paused
        else fault
        or (
            "recipient_not_selected"
            if not selected
            else "disabled"
            if not settings["enabled"]
            or (phase == "recovery" and not settings["recovery"])
            else "recipient_unavailable"
            if not available
            else "preview_origin_blocked"
            if not source_allowed
            else "preview_eligible"
        )
    )
    return {
        "target": target,
        "selected": selected,
        "enabled": settings["enabled"],
        "available": available,
        "eligible": reason == "preview_eligible",
        "reason": reason,
    }


def script_target(hass: HomeAssistant, entity_id: str) -> dict | None:
    """Bind an existing script to registry identity, not just its displayed ID."""
    if not isinstance(entity_id, str) or not entity_id.startswith("script."):
        return None
    entry = er.async_get(hass).async_get(entity_id)
    state = hass.states.get(entity_id)
    if (
        entry is None
        or entry.platform != "script"
        or entry.disabled_by
        or state is None
        or state.state in {"unknown", "unavailable"}
        or not hass.services.has_service("script", "turn_on")
    ):
        return None
    identity = hashlib.sha256(
        json.dumps(
            [entry.id, entry.unique_id, entry.platform, entry.config_entry_id]
        ).encode()
    ).hexdigest()
    return {
        "entity_id": entity_id,
        "identity": identity,
        "name": entry.name or state.attributes.get("friendly_name") or entity_id,
    }


def scripts(hass: HomeAssistant) -> list[dict]:
    return [
        target
        for entity in er.async_get(hass).entities.values()
        if (target := script_target(hass, entity.entity_id)) is not None
    ]


def validate_actions(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"enabled", "start", "recovery"}
        or type(value["enabled"]) is not bool
        or (value["enabled"] and not value["start"] and not value["recovery"])
    ):
        raise AutomationError("invalid_actions")
    for phase in ("start", "recovery"):
        rows = value[phase]
        if not isinstance(rows, list) or len(rows) > MAX_SCRIPTS:
            raise AutomationError("invalid_actions")
        seen = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != {"entity_id", "identity"}
                or not isinstance(row["entity_id"], str)
                or not re.fullmatch(r"script\.[a-z0-9_]+", row["entity_id"])
                or row["entity_id"] in seen
                or not isinstance(row["identity"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["identity"])
            ):
                raise AutomationError("invalid_actions")
            seen.add(row["entity_id"])


def validate_notifications(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"enabled", "recovery", "recipients"}
        or type(value["enabled"]) is not bool
        or type(value["recovery"]) is not bool
        or not isinstance(value["recipients"], list)
        or len(value["recipients"]) > MAX_RECIPIENTS
    ):
        raise AutomationError("invalid_notifications")
    seen = set()
    for row in value["recipients"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"service", "enabled"}
            or not isinstance(row["service"], str)
            or not re.fullmatch(r"mobile_app_[a-z0-9_]+", row["service"])
            or row["service"] in seen
            or type(row["enabled"]) is not bool
        ):
            raise AutomationError("invalid_notifications")
        seen.add(row["service"])


class NotificationStore:
    """Atomic optimistic settings, independent from unchanged source options."""

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self.hass = hass
        self.store = Store(
            hass, 1, f"alarmmesh.notifications.{entry_id}", atomic_writes=True
        )
        self.value = deepcopy(DEFAULT_NOTIFICATIONS)
        self.revision = 0
        self.lock = asyncio.Lock()
        self.closed = False

    async def load(self):
        if (data := await self.store.async_load()) is not None:
            if (
                not isinstance(data, dict)
                or set(data) != {"revision", "value"}
                or type(data["revision"]) is not int
                or data["revision"] < 0
            ):
                raise AutomationError("invalid_storage")
            validate_notifications(data["value"])
            self.value, self.revision = deepcopy(data["value"]), data["revision"]

    async def save(self, value, revision, confirmed):
        async with self.lock:
            if self.closed:
                raise AutomationError("not_loaded")
            if type(revision) is not int or revision != self.revision:
                raise AutomationError("conflict")
            validate_notifications(value)
            available = {r["service"] for r in recipients(self.hass)}
            old = {r["service"] for r in self.value["recipients"]}
            if any(r["service"] not in available | old for r in value["recipients"]):
                raise AutomationError("recipient_unavailable")
            if value["enabled"] and (
                confirmed is not True
                or not any(r["enabled"] for r in value["recipients"])
            ):
                raise AutomationError("automation_confirmation_required")
            new = {"revision": self.revision + 1, "value": deepcopy(value)}
            await self.store.async_save(new)
            self.value, self.revision = new["value"], new["revision"]

    async def close(self):
        async with self.lock:
            self.closed = True
