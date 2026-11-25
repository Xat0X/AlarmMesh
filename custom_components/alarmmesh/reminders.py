"""Explicit calendar reminders. This module cannot start a device self-test."""

import asyncio
import hashlib
import json
from contextlib import suppress
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .automation import AutomationError, recipients, send_notification
from .runtime import valid_source_ref

INTERVALS = (0, 30, 90, 180, 365)
STATES = {
    "pending",
    "sending",
    "accepted",
    "failed",
    "outcome_unknown",
    "startup_suppressed",
    "handled",
}
FIELDS = {"identity", "enabled", "date", "interval", "recipient", "cycle", "status"}


def due_at(value: str):
    """09:00 local calendar time avoids ambiguous/nonexistent DST night hours."""
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError
    return datetime.combine(
        parsed, time(9), dt_util.get_default_time_zone()
    ).astimezone(dt_util.UTC)


class Reminders:
    def __init__(self, hass, entry, linking, publish, activity):
        self.hass, self.entry, self.linking, self.publish, self.activity = (
            hass,
            entry,
            linking,
            publish,
            activity,
        )
        self.store = Store(
            hass, 1, f"alarmmesh.reminders.{entry.entry_id}", atomic_writes=True
        )
        self.items, self.revision = {}, 0
        self.closed, self.paused, self.fault = False, True, None
        self.lock = asyncio.Lock()
        self.task = self.cancel_timer = self.startup_unsubscribe = None
        self.config_unsubscribe = None
        self.dirty = False

    def identity(self, source):
        if (
            source not in self.entry.runtime_data.source_entity_ids
            or self.linking.capabilities.source_identity_changed(source)
            or self.hass.states.get(source) is None
        ):
            return None
        entity = er.async_get(self.hass).async_get(source)
        if entity is None:
            return None
        return hashlib.sha256(
            json.dumps(
                [
                    entity.id,
                    entity.unique_id,
                    entity.platform,
                    entity.config_entry_id,
                    entity.device_id,
                ]
            ).encode()
        ).hexdigest()

    def _payload(self, items=None, revision=None):
        return {
            "schema": 1,
            "revision": self.revision if revision is None else revision,
            "items": deepcopy(self.items if items is None else items),
        }

    async def load(self):
        try:
            data = await self.store.async_load()
            if data is None:
                return
            if (
                not isinstance(data, dict)
                or set(data) != {"schema", "revision", "items"}
                or type(data["schema"]) is not int
                or data["schema"] != 1
                or type(data["revision"]) is not int
                or data["revision"] < 0
                or not isinstance(data["items"], dict)
                or len(data["items"]) > 256
            ):
                raise ValueError
            for source, item in data["items"].items():
                if (
                    not valid_source_ref(source)
                    or not isinstance(item, dict)
                    or set(item) != FIELDS
                ):
                    raise ValueError
                self._validate(item)
                if item["status"] == "sending":
                    item["status"] = "outcome_unknown"
            self.items, self.revision = data["items"], data["revision"]
        except Exception:
            self.fault = "reminder_storage_error"

    def _validate(self, item):
        if (
            type(item["enabled"]) is not bool
            or type(item["interval"]) is not int
            or item["interval"] not in INTERVALS
            or not isinstance(item["identity"], str)
            or len(item["identity"]) != 64
            or any(c not in "0123456789abcdef" for c in item["identity"])
            or not isinstance(item["cycle"], str)
            or len(item["cycle"]) != 32
            or not isinstance(item["status"], str)
            or item["status"] not in STATES
        ):
            raise ValueError
        from .automation import validate_notifications

        validate_notifications(
            {
                "enabled": False,
                "recovery": False,
                "recipients": [{"service": item["recipient"], "enabled": True}],
            }
        )
        due_at(item["date"])

    async def save(self, operation, source, revision, value, confirmed):
        if self.closed or self.paused or self.linking._paused or self.fault:
            raise AutomationError(self.fault or "not_loaded")
        if confirmed is not True:
            raise AutomationError("automation_confirmation_required")
        async with self.lock:
            if type(revision) is not int or revision != self.revision:
                raise AutomationError("conflict")
            items = deepcopy(self.items)
            old = items.get(source)
            if operation == "delete":
                if old is None or value:
                    raise AutomationError("invalid_reminder")
                del items[source]
            elif operation in {"save", "snooze", "handle"}:
                identity = self.identity(source)
                if (
                    identity is None
                    or old
                    and operation != "save"
                    and old["identity"] != identity
                ):
                    raise AutomationError("reminder_identity_changed")
                today = dt_util.as_local(dt_util.utcnow()).date()
                if operation == "save":
                    if (
                        not isinstance(value, dict)
                        or set(value)
                        != {"identity", "enabled", "date", "interval", "recipient"}
                        or value["identity"] != identity
                    ):
                        raise AutomationError("invalid_reminder")
                    item = {**value, "cycle": uuid4().hex, "status": "pending"}
                    if old and all(
                        old[key] == item[key]
                        for key in ("identity", "date", "recipient")
                    ):
                        item.update(cycle=old["cycle"], status=old["status"])
                else:
                    if old is None:
                        raise AutomationError("invalid_reminder")
                    item = old
                    if operation == "snooze":
                        if set(value) != {"date"}:
                            raise AutomationError("invalid_reminder")
                        try:
                            if date.fromisoformat(value["date"]) <= today:
                                raise ValueError
                        except ValueError, TypeError:
                            raise AutomationError("invalid_reminder") from None
                        item.update(
                            date=value["date"], cycle=uuid4().hex, status="pending"
                        )
                    else:
                        if value:
                            raise AutomationError("invalid_reminder")
                        item["status"] = "handled"
                        if item["enabled"] and item["interval"]:
                            item.update(
                                date=(
                                    today + timedelta(days=item["interval"])
                                ).isoformat(),
                                cycle=uuid4().hex,
                                status="pending",
                            )
                try:
                    self._validate(item)
                    if (
                        operation != "handle" or item["status"] == "pending"
                    ) and not today <= date.fromisoformat(
                        item["date"]
                    ) <= today + timedelta(days=3660):
                        raise ValueError
                except ValueError, TypeError, AutomationError:
                    raise AutomationError("invalid_reminder") from None
                available = {r["service"] for r in recipients(self.hass)}
                if item["recipient"] not in available and (
                    not old or old["recipient"] != item["recipient"]
                ):
                    raise AutomationError("recipient_unavailable")
                items[source] = item
            else:
                raise AutomationError("invalid_reminder")
            if len(items) > 256:
                raise AutomationError("invalid_reminder")
            await self.store.async_save(self._payload(items, self.revision + 1))
            self.items, self.revision = items, self.revision + 1
        self.activity.record(
            "configuration",
            "reminder",
            {"handle": "handled", "snooze": "snoozed"}.get(operation, "changed"),
            source=source,
        )
        self.changed()
        self.publish()

    def start(self):
        if (
            any(i["enabled"] for i in self.items.values())
            and self.hass.state is not CoreState.running
        ):
            self.startup_unsubscribe = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._started
            )
        else:
            self._started()

    @callback
    def _started(self, *_args):
        self.startup_unsubscribe = None
        if self.closed:
            return
        self.paused = False
        if self.config_unsubscribe:
            self.config_unsubscribe()
        self.config_unsubscribe = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self.changed
        )
        for item in self.items.values():
            if (
                item["enabled"]
                and item["status"] == "pending"
                and due_at(item["date"]) <= dt_util.utcnow()
            ):
                item["status"] = "startup_suppressed"
        self.changed()

    def _smoke(self):
        return self.linking.active or any(
            s.name == "SMOKE_REPORTED"
            for s in self.entry.runtime_data.source_statuses.values()
        )

    @callback
    def changed(self, *_args):
        if self.closed or self.paused or self.fault:
            return
        self.dirty = True
        if self.task is None or self.task.done():
            task = self.entry.async_create_background_task(
                self.hass, self._run(), "AlarmMesh reminders"
            )
            self.task = None if task.done() else task

    def _allowed(self, source, item):
        return (
            not (
                self.closed
                or self.paused
                or self.linking._paused
                or self.fault
                or self._smoke()
            )
            and self.items.get(source) is item
            and item["enabled"]
            and item["status"] == "pending"
            and self.identity(source) == item["identity"]
            and due_at(item["date"]) <= dt_util.utcnow()
        )

    async def _run(self):
        try:
            while self.dirty and not self.closed and not self.paused:
                self.dirty = False
                for source, item in tuple(self.items.items()):
                    if not self._allowed(source, item):
                        continue
                    async with self.lock:
                        if not self._allowed(source, item):
                            continue
                        item["status"] = "sending"
                        await self.store.async_save(self._payload())
                    self.activity.record(
                        "maintenance",
                        "reminder",
                        "sending",
                        source=source,
                        target=item["recipient"],
                        correlation=item["cycle"],
                    )
                    self.publish()
                    # Persisted intent is terminal on uncertainty, never an auto retry.
                    if (
                        self.closed
                        or self.paused
                        or self.linking._paused
                        or self._smoke()
                        or self.items.get(source) is not item
                        or not item["enabled"]
                        or self.identity(source) != item["identity"]
                    ):
                        item["status"] = "outcome_unknown"
                    else:
                        try:
                            nl = self.hass.config.language.startswith("nl")
                            state = self.hass.states.get(source)
                            name = str(
                                state.attributes.get("friendly_name", source)
                                if state
                                else source
                            )[:160]
                            link = "/alarmmesh?view=maintenance"
                            body = (
                                "Controleer volgens de fabrikantvoorschriften. "
                                "Geen zelftest gestart of resultaat bevestigd."
                                if nl
                                else "Check per manufacturer instructions. "
                                "No self-test started or result confirmed."
                            )
                            async with asyncio.timeout(10):
                                await send_notification(
                                    self.hass,
                                    item["recipient"],
                                    {
                                        "title": "AlarmMesh · "
                                        + (
                                            "Testherinnering"
                                            if nl
                                            else "Check reminder"
                                        ),
                                        "message": name + ": " + body,
                                        "data": {
                                            "url": link,
                                            "clickAction": link,
                                        },
                                    },
                                )
                        except asyncio.CancelledError:
                            item["status"] = "outcome_unknown"
                            self.activity.record(
                                "maintenance",
                                "reminder",
                                "outcome_unknown",
                                source=source,
                                target=item["recipient"],
                                correlation=item["cycle"],
                            )
                            raise
                        except Exception:
                            item["status"] = "failed"
                        else:
                            item["status"] = "accepted"
                    self.activity.record(
                        "maintenance",
                        "reminder",
                        item["status"],
                        source=source,
                        target=item["recipient"],
                        correlation=item["cycle"],
                    )
                    async with self.lock:
                        await self.store.async_save(self._payload())
                    self.publish()
                async with self.lock:
                    if self.items:
                        await self.store.async_save(self._payload())
        except asyncio.CancelledError:
            raise
        except Exception:
            self.fault = "reminder_storage_error"
            self.publish()
        finally:
            self.task = None
            self._schedule()

    def _schedule(self):
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.closed or self.paused or self.fault:
            return
        now = dt_util.utcnow()
        future = [
            due_at(i["date"])
            for i in self.items.values()
            if i["enabled"] and i["status"] == "pending" and due_at(i["date"]) > now
        ]
        if future:
            self.cancel_timer = async_call_later(
                self.hass, (min(future) - now).total_seconds(), self.changed
            )

    def snapshot(self):
        available = {r["service"] for r in recipients(self.hass)}
        rows = [
            {
                "source": source,
                **deepcopy(item),
                "attention": "reminder_identity_changed"
                if self.identity(source) != item["identity"]
                else "recipient_unavailable"
                if item["recipient"] not in available
                else "reminder_smoke_priority"
                if self._smoke() and item["enabled"] and item["status"] == "pending"
                else None,
            }
            for source, item in self.items.items()
        ]
        return {
            "items": rows,
            "revision": self.revision,
            "error": self.fault,
            "paused": self.paused,
            "time_zone": self.hass.config.time_zone,
        }

    async def pause(self):
        self.paused = True
        if self.config_unsubscribe:
            self.config_unsubscribe()
            self.config_unsubscribe = None
        if self.startup_unsubscribe:
            self.startup_unsubscribe()
            self.startup_unsubscribe = None
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        if self.items and not self.fault:
            try:
                async with self.lock:
                    await self.store.async_save(self._payload())
            except Exception:
                self.fault = "reminder_storage_error"

    async def close(self):
        self.closed = True
        await self.pause()
