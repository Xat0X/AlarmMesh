"""Opt-in maintenance delivery. Never changes smoke, incidents or device states."""

import asyncio
import hashlib
import json
from contextlib import suppress
from copy import deepcopy
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .automation import (
    AutomationError,
    recipients,
    send_notification,
    validate_notifications,
)
from .runtime import valid_source_ref
from .status import SourceStatus

KINDS = ("battery", "fault", "unavailable")
DELAYS = (5, 15, 30, 60)
DEFAULT = {
    "enabled": False,
    "recovery": False,
    "recipients": [],
    "battery": True,
    "fault": True,
    "unavailable": True,
    "delay": 15,
}
STATUSES = {"sending", "accepted", "failed", "blocked", "outcome_unknown"}
MAX_DEVICES = 256


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise AutomationError("invalid_maintenance")
    validate_notifications({k: value[k] for k in ("enabled", "recovery", "recipients")})
    if (
        any(type(value[k]) is not bool for k in KINDS)
        or type(value["delay"]) is not int
        or value["delay"] not in DELAYS
    ):
        raise AutomationError("invalid_maintenance")
    if value["enabled"] and (
        not any(value[k] for k in KINDS)
        or not any(r["enabled"] for r in value["recipients"])
    ):
        raise AutomationError("invalid_maintenance")


def new_issue():
    return {"active": False, "baseline": False, "basis": [], "receipts": {}}


class Maintenance:
    """Bounded ledger per device/problem/recipient, one delivery task and timer."""

    def __init__(self, hass, entry, linking, publish):
        self.hass, self.entry, self.linking, self.publish = (
            hass,
            entry,
            linking,
            publish,
        )
        self.store = Store(
            hass, 1, f"alarmmesh.maintenance.{entry.entry_id}", atomic_writes=True
        )
        self.value, self.revision, self.records = deepcopy(DEFAULT), 0, {}
        self.lock = asyncio.Lock()
        self.closed, self.paused, self.fault = False, True, None
        self.task, self.cancel_timer = None, None
        self.since, self.samples = {}, {}
        self.dirty = False
        self.startup_unsubscribe = None

    def _payload(self, value=None, revision=None):
        return {
            "schema": 1,
            "revision": self.revision if revision is None else revision,
            "settings": deepcopy(self.value if value is None else value),
            "records": deepcopy(self.records),
        }

    async def _persist(self):
        try:
            async with self.lock:
                await self.store.async_save(self._payload())
        except Exception:
            self.fault = "maintenance_storage_error"
            raise

    async def load(self):
        try:
            data = await self.store.async_load()
            if data is None:
                return
            if (
                not isinstance(data, dict)
                or set(data) != {"schema", "revision", "settings", "records"}
                or type(data["schema"]) is not int
                or data["schema"] != 1
                or type(data["revision"]) is not int
                or data["revision"] < 0
                or not isinstance(data["records"], dict)
                or len(data["records"]) > MAX_DEVICES
            ):
                raise ValueError
            validate_settings(data["settings"])
            for key, record in data["records"].items():
                if (
                    not isinstance(key, str)
                    or len(key) != 64
                    or not isinstance(record, dict)
                    or set(record) != {"identity", "sources", "issues"}
                    or not isinstance(record["identity"], str)
                    or len(record["identity"]) != 64
                    or not isinstance(record["sources"], list)
                    or not 1 <= len(record["sources"]) <= 256
                    or any(not valid_source_ref(s) for s in record["sources"])
                    or not isinstance(record["issues"], dict)
                    or set(record["issues"]) != set(KINDS)
                ):
                    raise ValueError
                for issue in record["issues"].values():
                    if (
                        not isinstance(issue, dict)
                        or set(issue) != {"active", "baseline", "basis", "receipts"}
                        or type(issue["active"]) is not bool
                        or type(issue["baseline"]) is not bool
                        or not isinstance(issue["basis"], list)
                        or not set(issue["basis"]) <= {"percent", "binary"}
                        or not isinstance(issue["receipts"], dict)
                        or len(issue["receipts"]) > 20
                    ):
                        raise ValueError
                    validate_notifications(
                        {
                            "enabled": False,
                            "recovery": False,
                            "recipients": [
                                {"service": service, "enabled": False}
                                for service in issue["receipts"]
                            ],
                        }
                    )
                    for receipt in issue["receipts"].values():
                        if (
                            not isinstance(receipt, dict)
                            or not set(receipt) <= {"problem", "recovery"}
                            or any(
                                status not in STATUSES for status in receipt.values()
                            )
                        ):
                            raise ValueError
                        for phase, status in receipt.items():
                            if status == "sending":
                                receipt[phase] = "outcome_unknown"
            self.value, self.revision, self.records = (
                data["settings"],
                data["revision"],
                data["records"],
            )
        except Exception:
            # This optional feature fails closed; never overwrite damaged storage
            # or prevent read-only smoke monitoring from loading.
            self.fault = "maintenance_storage_error"

    async def save(self, value, revision, confirmed):
        if self.closed or self.paused or self.fault:
            raise AutomationError(self.fault or "not_loaded")
        validate_settings(value)
        available = {r["service"] for r in recipients(self.hass)}
        old = {r["service"] for r in self.value["recipients"]}
        if any(r["service"] not in available | old for r in value["recipients"]):
            raise AutomationError("recipient_unavailable")
        if value["enabled"] and confirmed is not True:
            raise AutomationError("automation_confirmation_required")
        async with self.lock:
            if type(revision) is not int or revision != self.revision:
                raise AutomationError("conflict")
            await self.store.async_save(self._payload(value, self.revision + 1))
            old_delay = self.value["delay"]
            was_enabled = self.value["enabled"]
            self.value, self.revision = deepcopy(value), self.revision + 1
            if old_delay != value["delay"] or not was_enabled:
                self.since.clear()
        if not self.value["enabled"]:
            self.since.clear()
            if self.cancel_timer:
                self.cancel_timer()
                self.cancel_timer = None
            if self.task:
                task = self.task
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await self._persist()
            self.publish()
            return
        self.changed()

    def _sample(self):
        cap = self.linking.capabilities
        samples, missing = {}, []
        for source in self.entry.runtime_data.source_entity_ids:
            entity, device, origin, model, vendor, _ = cap.metadata(source)
            if entity is None:
                missing.append(source)
                continue
            key = digest(
                [device.id if device else entity.id, entity.config_entry_id, origin]
            )
            row = samples.setdefault(
                key,
                {
                    "sources": [],
                    "identities": [],
                    "battery": [],
                    "fault": [],
                    "unavailable": [],
                    "verified": True,
                    "usable": True,
                },
            )
            row["sources"].append(source)
            row["identities"].append(
                [entity.id, entity.unique_id, entity.config_entry_id, model, vendor]
            )
            valid = not cap.source_identity_changed(source)
            row["verified"] &= valid
            row["usable"] &= self.entry.runtime_data.source_statuses.get(source) in {
                SourceStatus.SMOKE_REPORTED,
                SourceStatus.NO_SMOKE_REPORTED,
            }
            health = cap.details(source)["maintenance"]
            row["battery"].append(health)
            row["fault"].append(health["fault"])
            row["unavailable"].append(
                self.entry.runtime_data.source_statuses.get(source)
                not in {SourceStatus.SMOKE_REPORTED, SourceStatus.NO_SMOKE_REPORTED}
                if valid
                else None
            )
        for source in missing:
            old = next(
                (k for k, r in self.records.items() if source in r["sources"]),
                digest(["missing", source]),
            )
            row = samples.setdefault(
                old,
                {
                    "sources": [],
                    "identities": [],
                    "battery": [],
                    "fault": [],
                    "unavailable": [],
                    "verified": False,
                    "usable": False,
                },
            )
            row["sources"].append(source)
            row["unavailable"].append(True)
            row["verified"] = False
            row["usable"] = False
        for row in samples.values():
            row["identity"] = (
                digest(sorted(row.pop("identities"))) if row["verified"] else None
            )
        return samples

    def _condition(self, kind, sample, issue):
        if kind == "unavailable":
            return (
                True
                if True in sample["unavailable"]
                else False
                if sample["verified"]
                and sample["unavailable"]
                and all(v is False for v in sample["unavailable"])
                else None
            )
        if not sample["verified"] or not sample["usable"]:
            return None
        if kind == "fault":
            return (
                True
                if True in sample["fault"]
                else False
                if sample["fault"] and all(v is False for v in sample["fault"])
                else None
            )
        values = sample["battery"]
        percent = min(
            (v["battery_percent"] for v in values if v["battery_percent"] is not None),
            default=None,
        )
        binary = (
            True
            if any(v["battery_low"] is True for v in values)
            else False
            if values and all(v["battery_low"] is False for v in values)
            else None
        )
        evidence = {
            "percent": None if percent is None else percent <= 20,
            "binary": binary,
        }
        positives = [key for key, value in evidence.items() if value is True]
        if positives:
            issue["basis"] = sorted(set(issue["basis"]) | set(positives))
            return True
        basis = issue["basis"] or [
            key for key, value in evidence.items() if value is not None
        ]
        return False if basis and all(evidence[key] is False for key in basis) else None

    def _observe(self, startup=False):
        self.samples = self._sample()
        if len(self.samples) > MAX_DEVICES:
            self.fault = "maintenance_source_limit"
            return
        self.records = {k: r for k, r in self.records.items() if k in self.samples}
        now = dt_util.utcnow()
        for key, sample in self.samples.items():
            record = self.records.get(key)
            if (
                record is None
                or sample["identity"] is not None
                and record["identity"] != sample["identity"]
            ):
                # A replacement starts a new identity, never recovery of the old one.
                record = {
                    "identity": sample["identity"]
                    or digest(["missing", sample["sources"]]),
                    "sources": sample["sources"],
                    "issues": {kind: new_issue() for kind in KINDS},
                }
                self.records[key] = record
            record["sources"] = sample["sources"]
            for kind, issue in record["issues"].items():
                probe = deepcopy(issue)
                if not issue["active"]:
                    probe["basis"] = []
                value = self._condition(kind, sample, probe)
                if value is True and not issue["active"]:
                    basis = probe["basis"]
                    issue = new_issue()
                    issue.update(
                        active=True,
                        baseline=startup and kind != "unavailable",
                        basis=basis,
                    )
                    record["issues"][kind] = issue
                elif value is False and issue["active"]:
                    issue["active"] = False
                    issue["baseline"] = startup
                elif value is True:
                    issue["basis"] = probe["basis"]
                if startup and value is True and kind != "unavailable":
                    issue["baseline"] = True
                if kind == "unavailable":
                    if value is True:
                        self.since.setdefault(key, now)
                    else:
                        self.since.pop(key, None)
        self.since = {k: v for k, v in self.since.items() if k in self.samples}

    def start(self):
        if (
            self.value["enabled"]
            and not self.fault
            and self.hass.state is not CoreState.running
        ):
            self.startup_unsubscribe = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._started
            )
            return
        self._started()

    @callback
    def _started(self, *_args):
        self.startup_unsubscribe = None
        if self.closed:
            return
        self.paused = False
        if self.value["enabled"] and not self.fault:
            self._observe(startup=True)
        self.changed()

    @callback
    def changed(self, *_args):
        if self.closed or self.paused or self.fault or not self.value["enabled"]:
            return
        self._observe()
        self.dirty = True
        if self.task is None or self.task.done():
            task = self.entry.async_create_background_task(
                self.hass, self._run(), "AlarmMesh maintenance"
            )
            self.task = None if task.done() else task

    def _smoke(self):
        return (
            bool(self.linking.active)
            or SourceStatus.SMOKE_REPORTED
            in self.entry.runtime_data.source_statuses.values()
        )

    def _allowed(self, key, kind, issue, target, phase):
        if (
            self.closed
            or self.paused
            or self.linking._paused
            or self.fault
            or self._smoke()
            or not self.value["enabled"]
            or not self.value[kind]
            or not any(
                r["service"] == target and r["enabled"]
                for r in self.value["recipients"]
            )
        ):
            return False
        record = self.records.get(key)
        sample = self._sample().get(key)
        if (
            not record
            or record["issues"][kind] is not issue
            or not sample
            or sample["identity"] is not None
            and sample["identity"] != record["identity"]
        ):
            return False
        condition = self._condition(kind, sample, deepcopy(issue))
        if phase == "recovery":
            return (
                self.value["recovery"]
                and not issue["baseline"]
                and not issue["active"]
                and condition is False
            )
        return (
            issue["active"]
            and not issue["baseline"]
            and condition is True
            and (
                kind != "unavailable"
                or key in self.since
                and dt_util.utcnow()
                >= self.since[key] + timedelta(minutes=self.value["delay"])
            )
        )

    def message(self, record, kind, phase):
        nl = self.hass.config.language.startswith("nl")
        source = record["sources"][0]
        state = self.hass.states.get(source)
        name = state.attributes.get("friendly_name", source) if state else source
        name = str(name)[:160]
        label = {
            "battery": "Lage batterij" if nl else "Low battery",
            "fault": "Apparaatstoring" if nl else "Device problem",
            "unavailable": "Broninformatie onbeschikbaar"
            if nl
            else "Source information unavailable",
        }[kind]
        return {
            "title": "AlarmMesh · " + ("Onderhoud" if nl else "Maintenance"),
            "message": f"{name}: {label}. "
            + (
                (
                    "Herstel van de beschikbare waarde gemeld. "
                    if nl
                    else "Available value reports recovery. "
                )
                if phase == "recovery"
                else ""
            )
            + (
                "Geen rookmelding of gezondheidsbewijs. Bezorging niet bevestigd."
                if nl
                else "Not smoke or health proof. Phone delivery is unconfirmed."
            ),
            "data": {
                "url": "/alarmmesh?view=maintenance",
                "clickAction": "/alarmmesh?view=maintenance",
            },
        }

    async def _deliver(self, key, kind, issue, target, phase):
        if not self._allowed(key, kind, issue, target, phase):
            return
        receipt = issue["receipts"].setdefault(target, {})
        if phase in receipt:
            return
        if len(issue["receipts"]) > 20:
            issue["receipts"].pop(target, None)
            return
        receipt[phase] = "sending"
        await self._persist()
        self.publish()  # Observe the persisted request separately from its outcome.
        if not self._allowed(key, kind, issue, target, phase):
            receipt[phase] = "blocked"
            await self._persist()
            return
        try:
            # Separate single-worker lane reserves all incident executor slots.
            async with asyncio.timeout(10):
                await send_notification(
                    self.hass, target, self.message(self.records[key], kind, phase)
                )
        except asyncio.CancelledError:
            receipt[phase] = "outcome_unknown"
            self.publish()
            raise
        except Exception:
            receipt[phase] = "failed"
        else:
            receipt[phase] = "accepted"
        await self._persist()

    def _schedule(self):
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if (
            self.closed
            or self.paused
            or self.fault
            or not self.value["enabled"]
            or not self.value["unavailable"]
            or self._smoke()
        ):
            return
        now = dt_util.utcnow()
        due = [
            start + timedelta(minutes=self.value["delay"])
            for key, start in self.since.items()
            if start + timedelta(minutes=self.value["delay"]) > now
            and self.records[key]["issues"]["unavailable"]["active"]
        ]
        if due:
            self.cancel_timer = async_call_later(
                self.hass, (min(due) - now).total_seconds(), self.changed
            )

    async def _run(self):
        try:
            while self.dirty and not self.closed and not self.paused and not self.fault:
                self.dirty = False
                await self._persist()
                for key, record in tuple(self.records.items()):
                    for kind, issue in tuple(record["issues"].items()):
                        phase = "problem" if issue["active"] else "recovery"
                        for recipient in self.value["recipients"]:
                            if (
                                phase == "recovery"
                                and issue["receipts"]
                                .get(recipient["service"], {})
                                .get("problem")
                                != "accepted"
                            ):
                                continue
                            await self._deliver(
                                key, kind, issue, recipient["service"], phase
                            )
                self.publish()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.fault = "maintenance_storage_error"
            self.publish()
        finally:
            self.task = None
            self._schedule()

    def snapshot(self):
        rows = []
        for key, record in self.records.items():
            for kind, issue in record["issues"].items():
                if not issue["active"] and not issue["receipts"]:
                    continue
                reason = (
                    "disabled"
                    if not self.value["enabled"] or not self.value[kind]
                    else "maintenance_baseline"
                    if issue["baseline"]
                    else "maintenance_smoke_priority"
                    if self._smoke()
                    else "maintenance_waiting"
                    if kind == "unavailable"
                    and key in self.since
                    and dt_util.utcnow()
                    < self.since[key] + timedelta(minutes=self.value["delay"])
                    else "maintenance_current"
                )
                sample = self.samples.get(key)
                condition = (
                    self._condition(kind, sample, deepcopy(issue)) if sample else None
                )
                if issue["baseline"] and not issue["active"]:
                    reason = "maintenance_startup_recovery"
                if self.startup_unsubscribe:
                    reason = "maintenance_starting"
                elif self.paused:
                    reason = "execution_paused"
                elif condition is None and reason == "maintenance_current":
                    reason = "maintenance_unknown"
                elif len(issue["receipts"]) >= 20 and any(
                    r["enabled"] and r["service"] not in issue["receipts"]
                    for r in self.value["recipients"]
                ):
                    reason = "maintenance_recipient_limit"
                elif (
                    not issue["active"]
                    and not self.value["recovery"]
                    and reason == "maintenance_current"
                ):
                    reason = "maintenance_recovery_off"
                rows.append(
                    {
                        "sources": record["sources"],
                        "kind": kind,
                        "active": issue["active"],
                        "reason": reason,
                        "receipts": deepcopy(issue["receipts"]),
                    }
                )
        available = {r["service"] for r in recipients(self.hass)}
        return {
            "settings": {**deepcopy(self.value), "revision": self.revision},
            "issues": rows,
            "missing_recipients": [
                r["service"]
                for r in self.value["recipients"]
                if r["service"] not in available
            ],
            "error": self.fault,
            "paused": self.paused,
        }

    async def pause(self):
        self.paused = True
        if self.startup_unsubscribe:
            self.startup_unsubscribe()
            self.startup_unsubscribe = None
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.task:
            task = self.task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self.records and not self.fault:
            await self._persist()

    async def close(self):
        self.closed = True
        await self.pause()
