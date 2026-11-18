"""Bounded observations, independent of action ownership and smoke calculation."""

import asyncio
from collections import deque
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

LIMIT = 1000
PENDING_LIMIT = 128
CATEGORIES = {"alarm", "maintenance", "selftest", "configuration"}
KINDS = {
    "phone_observation",
    "end_of_service",
    "source",
    "sounder",
    "notification",
    "script",
    "selftest",
    "battery",
    "fault",
    "unavailable",
    "reminder",
    "configuration",
}
RESULTS = {
    "user_observed",
    "SMOKE_REPORTED",
    "NO_SMOKE_REPORTED",
    "UNKNOWN",
    "UNREACHABLE",
    "MISSING",
    "usable",
    "problem",
    "recovered",
    "changed",
    "handled",
    "snoozed",
    "sending",
    "accepted",
    "failed",
    "blocked",
    "outcome_unknown",
    "sent",
    "sent_no_auto_stop",
    "stopping",
    "stopped",
    "stop_failed",
    "not_stopped",
    "already_active",
    "request_sent",
    "test_active",
    "device_success",
    "device_failed",
    "storage_error",
    "startup_suppressed",
}
FIELDS = {
    "id",
    "observed_at",
    "category",
    "kind",
    "result",
    "source",
    "groups",
    "target",
    "correlation",
}


class Activity:
    """One bounded queue/worker. Failures never escape into incident processing."""

    def __init__(self, hass, entry, publish):
        self.hass, self.entry, self.publish = hass, entry, publish
        self.store = Store(
            hass, 1, f"alarmmesh.activity.{entry.entry_id}", atomic_writes=True
        )
        self.rows, self.pending = [], deque()
        self.previous = None
        self.source_incidents = {}
        self.conditions = {}
        self.object_ids = {}
        self.task = self.cancel_timer = None
        self.closed = self.incomplete = self.damaged = False
        self.paused = False
        self.stop_unsubscribe = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._stop
        )

    async def load(self):
        try:
            data = await self.store.async_load()
            if data is None:
                return
            if (
                not isinstance(data, dict)
                or set(data) != {"schema", "incomplete", "events"}
                or type(data["schema"]) is not int
                or data["schema"] != 1
                or type(data["incomplete"]) is not bool
                or not isinstance(data["events"], list)
                or len(data["events"]) > LIMIT
            ):
                raise ValueError
            for row in data["events"]:
                if (
                    not isinstance(row, dict)
                    or set(row) != FIELDS
                    or any(
                        not isinstance(row[k], str) or len(row[k]) > 255
                        for k in FIELDS - {"groups"}
                    )
                    or row["category"] not in CATEGORIES
                    or row["kind"] not in KINDS
                    or row["result"] not in RESULTS
                    or not isinstance(row["groups"], list)
                    or len(row["groups"]) > 100
                    or any(not isinstance(g, str) or len(g) > 64 for g in row["groups"])
                ):
                    raise ValueError
                when = dt_util.parse_datetime(row["observed_at"])
                if when is None or when.tzinfo is None:
                    raise ValueError
            if len({row["id"] for row in data["events"]}) != len(data["events"]):
                raise ValueError
            self.rows, self.incomplete = data["events"], data["incomplete"]
            previous_count = len(self.rows)
            self._prune()
            if len(self.rows) != previous_count:
                await self.store.async_save(
                    {
                        "schema": 1,
                        "incomplete": self.incomplete,
                        "events": deepcopy(self.rows),
                    }
                )
        except Exception:
            self.incomplete = self.damaged = True

    def _prune(self):
        cutoff = dt_util.utcnow() - timedelta(days=30)
        self.rows = [
            r for r in self.rows if dt_util.parse_datetime(r["observed_at"]) > cutoff
        ][-LIMIT:]

    def record(
        self, category, kind, result, *, source="", groups=(), target="", correlation=""
    ):
        if self.closed or self.paused:
            return
        if category not in CATEGORIES or kind not in KINDS or result not in RESULTS:
            self.incomplete = True
            return
        row = {
            "id": uuid4().hex,
            "observed_at": dt_util.utcnow().isoformat(),
            "category": category,
            "kind": kind,
            "result": result,
            "source": str(source)[:255],
            "groups": list(groups)[:100],
            "target": str(target)[:255],
            "correlation": str(correlation)[:255],
        }
        if len(self.pending) >= PENDING_LIMIT:
            self.pending.popleft()
            self.incomplete = True
        self.pending.append(row)
        self._wake()

    def _wake(self):
        if not self.closed and (self.task is None or self.task.done()):
            task = self.entry.async_create_background_task(
                self.hass, self._flush(), "AlarmMesh activity"
            )
            self.task = None if task.done() else task

    async def _flush(self):
        try:
            await asyncio.sleep(0)  # Never re-enter a capture via an eager task.
            while self.pending:
                self.rows.extend(self.pending)
                self.pending.clear()
                self._prune()
                if not self.damaged:
                    try:
                        await self.store.async_save(
                            {
                                "schema": 1,
                                "incomplete": self.incomplete,
                                "events": deepcopy(self.rows),
                            }
                        )
                    except Exception:
                        self.incomplete = self.damaged = True
                        self.publish()
        finally:
            self.task = None
            self._schedule()

    def _schedule(self):
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.rows and not self.closed and not self.paused:
            expiry = min(
                dt_util.parse_datetime(r["observed_at"]) for r in self.rows
            ) + timedelta(days=30)
            self.cancel_timer = async_call_later(
                self.hass,
                max(1, (expiry - dt_util.utcnow()).total_seconds()),
                self._expire,
            )

    @callback
    def _expire(self, _now):
        self.cancel_timer = None
        self._prune()
        self._wake_prune()

    def _wake_prune(self):
        # A retention write, without inventing a journal event.
        async def save():
            try:
                if not self.damaged:
                    await self.store.async_save(
                        {
                            "schema": 1,
                            "incomplete": self.incomplete,
                            "events": deepcopy(self.rows),
                        }
                    )
            except Exception:
                self.incomplete = self.damaged = True
            finally:
                self.task = None
                self._schedule()
                self.publish()

        if self.task is None or self.task.done():
            task = self.entry.async_create_background_task(
                self.hass, save(), "AlarmMesh activity retention"
            )
            self.task = None if task.done() else task

    def _request(self, obj):
        key = id(obj)
        old = self.object_ids.get(key)
        if old is None or old[0] is not obj:
            self.object_ids[key] = (obj, uuid4().hex)
        return self.object_ids[key][1]

    def capture(self, panel):
        """Observe published transitions only; initial state is a quiet baseline."""
        if self.closed:
            return
        if self.paused:
            if self.previous and any(
                self.previous.get(("source", source), (None,))[0] != status.name
                for source, status in panel.runtime.source_statuses.items()
            ):
                self.incomplete = True
            return
        try:
            current = {}
            live_objects = set()

            def add(key, category, kind, result, **context):
                current[key] = (result, category, kind, context)

            for source, status in panel.runtime.source_statuses.items():
                groups = [
                    g["id"] for g in panel.groups.groups if source in g["members"]
                ]
                add(
                    ("source", source),
                    "alarm",
                    "source",
                    status.name,
                    source=source,
                    groups=groups,
                )
                identity = panel.reminders.identity(source)
                health = panel.linking.capabilities.details(source)["maintenance"]
                usable = status.name in {"SMOKE_REPORTED", "NO_SMOKE_REPORTED"}
                sample = {
                    "verified": identity is not None,
                    "usable": usable,
                    "battery": [health],
                    "fault": [health["fault"]],
                    "unavailable": [not usable],
                }
                for kind in ("battery", "fault", "unavailable"):
                    condition_key = (source, identity, kind)
                    issue = self.conditions.setdefault(
                        condition_key, {"active": False, "basis": []}
                    )
                    if not issue["active"]:
                        issue["basis"] = []
                    value = panel.maintenance._condition(kind, sample, issue)
                    if value is not None:
                        was_active = issue["active"]
                        issue["active"] = value
                        if self.previous is not None and value != was_active:
                            self.record(
                                "maintenance",
                                kind,
                                "problem" if value else "recovered",
                                source=source,
                                groups=groups,
                            )
                if "end_of_service" in health:
                    condition_key = (source, identity, "end_of_service")
                    issue = self.conditions.setdefault(condition_key, {"active": False})
                    value = (
                        health["end_of_service"]
                        if sample["verified"] and usable
                        else None
                    )
                    if value is not None:
                        old = issue["active"]
                        issue["active"] = value
                        if self.previous is not None and old != value:
                            self.record(
                                "maintenance",
                                "end_of_service",
                                "problem" if value else "recovered",
                                source=source,
                                groups=groups,
                            )
            for row in panel.linking.records.values():
                correlation = self._request(row)
                live_objects.add(id(row))
                groups = [
                    g["id"]
                    for g in panel.groups.groups
                    if any(
                        b["target"] == row["target"] for b in g["linking"]["bindings"]
                    )
                ]
                add(
                    ("sounder", correlation),
                    "alarm",
                    "sounder",
                    row["status"],
                    source=row["source"],
                    target=row["target"],
                    correlation=correlation,
                    groups=groups,
                )
            for group, episode in panel.effects.episodes.items():
                for key, row in episode["receipts"].items():
                    add(
                        (episode["id"], key, row["phase"], tuple(row["seen"])),
                        "alarm",
                        row["kind"],
                        row["status"],
                        target=row["target"],
                        groups=[] if group == "notifications" else [group],
                        correlation=episode["id"],
                    )
            for row in panel.effects.manual_results:
                add(
                    ("manual", row["request_id"]),
                    "configuration",
                    row["kind"],
                    row["status"],
                    target=row["target"],
                    correlation=row["request_id"],
                )
            if row := panel.selftests.record:
                add(
                    ("selftest", row["request_id"]),
                    "selftest",
                    "selftest",
                    row["status"],
                    source=row["source"],
                    correlation=row["request_id"],
                )
            for key, record in panel.maintenance.records.items():
                for kind, issue in record["issues"].items():
                    for target, receipt in issue["receipts"].items():
                        for phase, status in receipt.items():
                            add(
                                ("maintenance", key, kind, target, phase),
                                "maintenance",
                                "notification",
                                status,
                                source=record["sources"][0],
                                target=target,
                                correlation=key,
                            )
            add(
                ("configuration",),
                "configuration",
                "configuration",
                str(panel.groups.revision),
            )
            previous, self.previous = self.previous, current
            self.conditions = {
                k: v
                for k, v in self.conditions.items()
                if k[0] in panel.runtime.source_entity_ids
                and k[1] == panel.reminders.identity(k[0])
            }
            self.object_ids = {
                k: v for k, v in self.object_ids.items() if k in live_objects
            }
            if previous is None:
                self.source_incidents = {
                    s: uuid4().hex
                    for s, v in panel.runtime.source_statuses.items()
                    if v.name == "SMOKE_REPORTED"
                }
                self._schedule()
                return
            for key, (result, category, kind, context) in current.items():
                old = previous.get(key)
                if old and old[0] == result:
                    continue
                if kind == "source":
                    source = context["source"]
                    if old is None:
                        continue
                    if result == "SMOKE_REPORTED":
                        self.source_incidents.setdefault(source, uuid4().hex)
                    elif result == "NO_SMOKE_REPORTED":
                        if old[0] in {"UNKNOWN", "UNREACHABLE", "MISSING"}:
                            self.record(category, kind, "usable", **context)
                        if source not in self.source_incidents:
                            continue
                    context["correlation"] = self.source_incidents.get(source, "")
                    if result == "NO_SMOKE_REPORTED":
                        self.source_incidents.pop(source, None)
                elif kind == "configuration":
                    result = "changed"
                elif (
                    old is None
                    and kind in {"battery", "fault", "unavailable"}
                    and result == "recovered"
                ):
                    continue
                self.record(category, kind, result, **context)
        except Exception:
            self.incomplete = True

    def snapshot(self):
        self._prune()
        return {
            "events": deepcopy(
                list(reversed((self.rows + list(self.pending))[-LIMIT:]))
            ),
            "incomplete": self.incomplete,
            "retention_days": 30,
            "limit": LIMIT,
        }

    async def pause(self):
        self.paused = True
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.task:
            await self.task

    async def _stop(self, _event):
        self.stop_unsubscribe = None
        await self.close()

    async def close(self):
        self.closed = True
        await self.pause()
        if not self.damaged:
            try:
                await self.store.async_save(
                    {
                        "schema": 1,
                        "incomplete": self.incomplete,
                        "events": deepcopy(self.rows),
                    }
                )
            except Exception:
                self.incomplete = self.damaged = True
        if self.stop_unsubscribe:
            self.stop_unsubscribe()
            self.stop_unsubscribe = None
        self.previous = None
        self.object_ids.clear()
