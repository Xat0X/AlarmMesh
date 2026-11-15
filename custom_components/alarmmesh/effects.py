"""Notifications/scripts consume the existing incident engine, with durable receipts."""

import asyncio
import re
from contextlib import suppress
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .automation import (
    DEFAULT_ACTIONS,
    AutomationError,
    NotificationStore,
    notification_plan,
    recipients,
    script_receipt_key,
    script_target,
    scripts,
    send_notification,
)
from .status import SourceStatus


class IncidentEffects:
    """No second smoke calculation. Receipts prevent replay, not restore truth."""

    def __init__(self, hass, entry, linking, groups, publish):
        self.hass, self.entry, self.linking, self.groups, self.publish = (
            hass,
            entry,
            linking,
            groups,
            publish,
        )
        self.settings = NotificationStore(hass, entry.entry_id)
        self.store = Store(
            hass, 1, f"alarmmesh.receipts.{entry.entry_id}", atomic_writes=True
        )
        self.episodes = {}
        self.lock = asyncio.Lock()
        self._task = None
        self.manual_tasks = set()
        self.manual_ids = set()
        self.manual_results = []
        self.dirty = False
        self.closed = False
        self.fault = None
        self.prune_cancel = None

    async def load(self):
        await self.settings.load()
        if (data := await self.store.async_load()) is None:
            return
        if (
            not isinstance(data, dict)
            or set(data) != {"episodes"}
            or not isinstance(data["episodes"], dict)
            or len(data["episodes"]) > 101
        ):
            raise AutomationError("invalid_storage")
        for key, episode in data["episodes"].items():
            if (
                not isinstance(key, str)
                or len(key) > 32
                or not isinstance(episode, dict)
                or set(episode)
                != {
                    "id",
                    "started",
                    "updated",
                    "phase",
                    "origins",
                    "relevant",
                    "receipts",
                }
                or not isinstance(episode["id"], str)
                or not re.fullmatch("[a-f0-9]{32}", episode["id"])
                or episode["phase"] not in {"start", "recovery"}
                or any(
                    not isinstance(episode[t], str)
                    or dt_util.parse_datetime(episode[t]) is None
                    for t in ("started", "updated")
                )
                or not isinstance(episode["receipts"], dict)
                or len(episode["receipts"]) > 60
            ):
                raise AutomationError("invalid_storage")
            for field in ("origins", "relevant"):
                rows = episode[field]
                if (
                    not isinstance(rows, list)
                    or len(rows) > 256
                    or any(
                        not isinstance(s, str)
                        or not re.fullmatch(r"binary_sensor\.[a-z0-9_]+", s)
                        for s in rows
                    )
                ):
                    raise AutomationError("invalid_storage")
            for receipt in episode["receipts"].values():
                if (
                    not isinstance(receipt, dict)
                    or set(receipt)
                    != {"kind", "target", "identity", "phase", "seen", "status"}
                    or receipt["kind"] not in {"notification", "script"}
                    or receipt["phase"] not in {"start", "recovery"}
                    or receipt["status"]
                    not in {
                        "sending",
                        "accepted",
                        "failed",
                        "blocked",
                        "outcome_unknown",
                    }
                    or any(
                        not isinstance(receipt[f], str) or len(receipt[f]) > 255
                        for f in ("target", "identity")
                    )
                    or not isinstance(receipt["seen"], list)
                    or len(receipt["seen"]) > 256
                    or any(s not in episode["origins"] for s in receipt["seen"])
                ):
                    raise AutomationError("invalid_storage")
                if receipt["status"] == "sending":
                    receipt["status"] = "outcome_unknown"
        self.episodes = deepcopy(data["episodes"])
        self._prune()
        await self._persist()

    def _schedule_prune(self):
        if self.prune_cancel:
            self.prune_cancel()
            self.prune_cancel = None
        resolved = [
            dt_util.parse_datetime(e["updated"])
            for e in self.episodes.values()
            if e["phase"] == "recovery"
        ]
        if resolved and not self.closed and not self.linking._paused:
            seconds = max(
                1,
                (
                    min(resolved) + timedelta(hours=24) - dt_util.utcnow()
                ).total_seconds(),
            )
            self.prune_cancel = async_call_later(
                self.hass, seconds, lambda _: self.changed()
            )

    def _prune(self):
        cutoff = dt_util.utcnow() - timedelta(hours=24)
        keys = {g["id"] for g in self.groups.groups} | {"notifications"}
        self.episodes = {
            k: e
            for k, e in self.episodes.items()
            if k in keys
            and (
                e["phase"] != "recovery"
                or dt_util.parse_datetime(e["updated"]) >= cutoff
            )
        }

    def changed(self):
        if self.closed or self.fault or self.linking._paused:
            return
        if (
            not self.settings.value["enabled"]
            and not self.episodes
            and not any(
                g.get("actions", DEFAULT_ACTIONS)["enabled"] for g in self.groups.groups
            )
        ):
            return
        self.dirty = True
        if self._task is None or self._task.done():
            task = self.entry.async_create_background_task(
                self.hass, self._run(), "AlarmMesh incident delivery"
            )
            self._task = None if task.done() else task

    def _clear(self, episode):
        statuses = self.entry.runtime_data.source_statuses
        return bool(episode["relevant"]) and all(
            statuses.get(s) is SourceStatus.NO_SMOKE_REPORTED
            and not self.linking.capabilities.source_identity_changed(s)
            for s in episode["relevant"]
        )

    def _episode(self, key, relevant):
        active = self.linking.active.intersection(relevant)
        old = self.episodes.get(key)
        now = dt_util.utcnow().isoformat()
        if active and (old is None or old["phase"] == "recovery"):
            old = {
                "id": uuid4().hex,
                "started": now,
                "updated": now,
                "phase": "start",
                "origins": [],
                "relevant": [],
                "receipts": {},
            }
            self.episodes[key] = old
        if old is not None and old["phase"] == "start":
            old["origins"] = sorted(set(old["origins"]) | active)
            old["relevant"] = sorted(set(old["relevant"]) | set(relevant))
            if len(old["relevant"]) > 256:
                raise AutomationError("automation_source_limit")
            if not active and self._clear(old):
                old["phase"], old["updated"] = "recovery", now
        return old

    async def _persist(self):
        async with self.lock:
            await self.store.async_save({"episodes": deepcopy(self.episodes)})

    def _name(self, source):
        entity = er.async_get(self.hass).async_get(source)
        state = self.hass.states.get(source)
        device = (
            dr.async_get(self.hass).async_get(entity.device_id)
            if entity and entity.device_id
            else None
        )
        area = ar.async_get(self.hass).async_get_area(
            (entity.area_id if entity else None) or (device.area_id if device else "")
        )
        name = (
            (entity.name if entity else None)
            or (state.attributes.get("friendly_name") if state else None)
            or source
        )
        return f"{name} ({area.name})" if area else name

    def message(self, episode=None, *, test=False):
        nl = self.hass.config.language.startswith("nl")
        phase = episode["phase"] if episode else "start"
        title = "AlarmMesh · " + (
            ("Testmelding" if nl else "Test notification")
            if test
            else ("Rook gemeld" if nl else "Smoke reported")
            if phase == "start"
            else ("Geen rook meer gemeld" if nl else "Smoke reports cleared")
        )
        ids = (
            episode["origins"]
            if episode
            else list(self.entry.runtime_data.source_entity_ids)[:1]
        )
        if episode and phase == "start":
            ids = [
                s
                for s in ids
                if self.entry.runtime_data.source_statuses.get(s)
                is SourceStatus.SMOKE_REPORTED
            ]
        names = "; ".join(self._name(s) for s in ids[:12])
        groups = ", ".join(
            g["name"]
            for g in self.groups.groups
            if set(ids).intersection(g.get("origins", g["members"]))
        )
        problems = sum(
            r["status"]
            in {"failed", "blocked", "stop_failed", "outcome_unknown", "not_stopped"}
            for r in self.linking.records.values()
        )
        time = dt_util.as_local(dt_util.utcnow()).isoformat(timespec="seconds")
        body = f"{names}\n{('Groepen' if nl else 'Groups')}: {groups or '—'}\n{time}"
        body += f"\n{('Zoemerproblemen' if nl else 'Sounder problems')}: {problems}. "
        body += (
            "Fysieke uitvoering niet bevestigd."
            if nl
            else "Physical execution is not confirmed."
        )
        if test:
            body = (
                "Dit is uitsluitend een testmelding.\n"
                if nl
                else "This is only a test notification.\n"
            ) + body
        return {
            "title": title,
            "message": body[:1800],
            "data": {
                "url": f"/alarmmesh?incident={episode['id']}"
                if episode
                else "/alarmmesh?view=incidents",
                "clickAction": f"/alarmmesh?incident={episode['id']}"
                if episode
                else "/alarmmesh?view=incidents",
            },
        }

    def _allowed(self, key, episode, receipt):
        if self.closed or self.linking._paused or self.episodes.get(key) is not episode:
            return False
        if receipt["phase"] == "recovery":
            if episode["phase"] != "recovery" or not self._clear(episode):
                return False
        elif episode["phase"] != "start" or not self.linking.active.intersection(
            episode["origins"]
        ):
            return False
        if receipt["kind"] == "notification":
            cfg = self.settings.value
            return (
                cfg["enabled"]
                and (receipt["phase"] != "recovery" or cfg["recovery"])
                and any(
                    r["service"] == receipt["target"] and r["enabled"]
                    for r in cfg["recipients"]
                )
                and any(
                    r["service"] == receipt["target"] for r in recipients(self.hass)
                )
            )
        group = next((g for g in self.groups.groups if g["id"] == key), None)
        cfg = group.get("actions", DEFAULT_ACTIONS) if group else DEFAULT_ACTIONS
        if (
            group
            and receipt["phase"] == "start"
            and not self.linking.active.intersection(
                group.get("origins", group["members"])
            )
        ):
            return False
        current = script_target(self.hass, receipt["target"])
        return (
            cfg["enabled"]
            and {"entity_id": receipt["target"], "identity": receipt["identity"]}
            in cfg[receipt["phase"]]
            and current is not None
            and current["identity"] == receipt["identity"]
        )

    async def _send(self, key, episode, receipt):
        async with self.linking._semaphore:
            if not self._allowed(key, episode, receipt):
                receipt["status"] = "blocked"
                await self._persist()
                return
            # Persist intent before dispatch. Interrupted calls are never replayed.
            receipt["status"] = "sending"
            await self._persist()
            if not self._allowed(key, episode, receipt):
                receipt["status"] = "blocked"
                await self._persist()
                return
            self.publish()
            try:
                async with asyncio.timeout(10):
                    if receipt["kind"] == "notification":
                        await send_notification(
                            self.hass, receipt["target"], self.message(episode)
                        )
                    else:
                        # One script per call preserves configured start order. This
                        # API acknowledges start, not completion of its side effects.
                        await self.hass.services.async_call(
                            "script",
                            "turn_on",
                            {"entity_id": receipt["target"]},
                            blocking=True,
                        )
            except asyncio.CancelledError:
                receipt["status"] = "outcome_unknown"
                raise
            except Exception:
                receipt["status"] = "failed"
            else:
                receipt["status"] = "accepted"
            await self._persist()
            self.publish()

    async def _notifications(self, episode):
        cfg = self.settings.value
        if not cfg["enabled"] or (
            episode["phase"] == "recovery" and not cfg["recovery"]
        ):
            return
        tasks = []
        active = self.linking.active.intersection(episode["origins"])
        if episode["phase"] == "start" and not active:
            return
        for recipient in cfg["recipients"]:
            if not recipient["enabled"]:
                continue
            key = recipient["service"]
            old = episode["receipts"].get(key)
            if old and old["phase"] == "start":
                # Release suppression only on explicit off, never on unknown or
                # an empty newly loaded active set. A fresh independent origin
                # lifetime can therefore produce one meaningful update.
                _, old["seen"] = notification_plan(
                    old,
                    "start",
                    active,
                    episode["origins"],
                    lambda s: (
                        self.entry.runtime_data.source_statuses.get(s)
                        is SourceStatus.NO_SMOKE_REPORTED
                        and not self.linking.capabilities.source_identity_changed(s)
                    ),
                )
            needed, _ = notification_plan(
                old, episode["phase"], active, episode["origins"], lambda s: False
            )
            if not needed:
                continue  # Never send recovery to a recipient with no first attempt.
            row = {
                "kind": "notification",
                "target": key,
                "identity": "",
                "phase": episode["phase"],
                "seen": sorted(active)
                if episode["phase"] == "start"
                else list(episode["origins"]),
                "status": "sending",
            }
            episode["receipts"][key] = row
            tasks.append(self._send("notifications", episode, row))
        await asyncio.gather(*tasks)

    async def _scripts(self, group, episode):
        cfg = group.get("actions", DEFAULT_ACTIONS)
        if not cfg["enabled"]:
            return
        for binding in cfg[episode["phase"]]:
            key = script_receipt_key(episode["phase"], binding)
            if key in episode["receipts"]:
                continue
            row = {
                "kind": "script",
                "target": binding["entity_id"],
                "identity": binding["identity"],
                "phase": episode["phase"],
                "seen": list(episode["origins"]),
                "status": "sending",
            }
            episode["receipts"][key] = row
            await self._send(group["id"], episode, row)

    async def _run(self):
        try:
            while self.dirty and not self.closed and not self.linking._paused:
                self.dirty = False
                had_episodes = bool(self.episodes)
                self._prune()
                plans = []
                episode = (
                    self._episode(
                        "notifications", self.entry.runtime_data.source_entity_ids
                    )
                    if self.settings.value["enabled"]
                    or "notifications" in self.episodes
                    else None
                )
                if episode:
                    plans.append(self._notifications(episode))
                for group in self.groups.groups:
                    if (
                        not group.get("actions", DEFAULT_ACTIONS)["enabled"]
                        and group["id"] not in self.episodes
                    ):
                        continue
                    episode = self._episode(
                        group["id"], group.get("origins", group["members"])
                    )
                    if episode:
                        plans.append(self._scripts(group, episode))
                await asyncio.gather(*plans)
                if self.episodes or had_episodes:
                    await self._persist()
                self._schedule_prune()
                self.publish()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.fault = "automation_storage_error"
            self.publish()
        finally:
            self._task = None

    def snapshot(self):
        available = {r["service"] for r in recipients(self.hass)}
        return {
            "settings": {
                **deepcopy(self.settings.value),
                "revision": self.settings.revision,
            },
            "recipients": recipients(self.hass),
            "scripts": scripts(self.hass),
            "missing_recipients": [
                r["service"]
                for r in self.settings.value["recipients"]
                if r["service"] not in available
            ],
            "episodes": [
                {"group_id": key, **deepcopy(value)}
                for key, value in self.episodes.items()
            ],
            "preview": self.message(),
            "error": self.fault,
            "manual_results": deepcopy(self.manual_results),
        }

    async def manual(
        self, kind, target, identity, confirmed, request_id, authorized=lambda: True
    ):
        if confirmed is not True:
            raise AutomationError("test_confirmation_required")
        if not isinstance(request_id, str) or not re.fullmatch(
            "[a-f0-9]{32}", request_id
        ):
            raise AutomationError("invalid_request")
        if self.closed or self.linking._paused:
            raise AutomationError("not_loaded")
        if self.manual_tasks or request_id in self.manual_ids:
            raise AutomationError("test_busy")
        if kind == "notification":
            if target not in {r["service"] for r in recipients(self.hass)}:
                raise AutomationError("recipient_unavailable")
        elif kind == "script":
            current = script_target(self.hass, target)
            if current is None or current["identity"] != identity:
                raise AutomationError("script_changed")
        else:
            raise AutomationError("invalid_request")
        if len(self.manual_ids) >= 100:
            raise AutomationError("test_limit")
        self.manual_ids.add(request_id)
        row = {"kind": kind, "target": target, "status": "sending"}
        self.manual_results = [row]  # Only the last explicit test; no message contents.

        async def dispatch():
            async with self.linking._semaphore, asyncio.timeout(10):
                if self.closed or self.linking._paused or not authorized():
                    raise AutomationError("not_loaded")
                if kind == "notification":
                    if target not in {r["service"] for r in recipients(self.hass)}:
                        raise AutomationError("recipient_unavailable")
                    await send_notification(self.hass, target, self.message(test=True))
                else:
                    current = script_target(self.hass, target)
                    if current is None or current["identity"] != identity:
                        raise AutomationError("script_changed")
                    await self.hass.services.async_call(
                        "script", "turn_on", {"entity_id": target}, blocking=True
                    )

        task = self.entry.async_create_background_task(
            self.hass, dispatch(), "AlarmMesh explicit test"
        )
        self.manual_tasks.add(task)
        self.publish()
        try:
            await task
        except asyncio.CancelledError:
            row["status"] = "outcome_unknown"
            raise
        except Exception:
            row["status"] = "failed"
        else:
            row["status"] = "accepted"
        finally:
            self.manual_tasks.discard(task)
            if not self.closed:
                self.publish()
        return deepcopy(row)

    async def pause(self):
        if self.prune_cancel:
            self.prune_cancel()
            self.prune_cancel = None
        tasks = [t for t in (self._task, *self.manual_tasks) if t is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        # The persisted sending intent is sufficient to suppress replay on load.
        if self.episodes:
            await self._persist()

    async def close(self):
        self.closed = True
        await self.pause()
        await self.settings.close()
