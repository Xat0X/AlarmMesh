"""Notifications/scripts consume the existing incident engine, with durable receipts."""

import asyncio
import hashlib
import json
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
    notification_route,
    recipients,
    script_receipt_key,
    script_target,
    scripts,
    send_notification,
)
from .notification_profiles import (
    IOS_SOUNDS,
    ProfileError,
    build_plan,
    receiver_metadata,
)
from .runtime import valid_source_ref
from .status import SourceStatus

REQUEST_TIMEOUT = 10


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
        self.record_activity = None
        self.lock = asyncio.Lock()
        self._task = None
        self.manual_tasks = set()
        self.manual_ids = set()
        self.manual_results = []
        self.phone_evidence = None
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
                    or any(not valid_source_ref(s) for s in rows)
                ):
                    raise AutomationError("invalid_storage")
            for receipt in episode["receipts"].values():
                if (
                    not isinstance(receipt, dict)
                    or set(receipt)
                    not in (
                        {"kind", "target", "identity", "phase", "seen", "status"},
                        {
                            "kind",
                            "target",
                            "identity",
                            "phase",
                            "seen",
                            "status",
                            "error",
                        },
                    )
                    or receipt.get("error", "")
                    not in {
                        "",
                        "settings_saved_during_smoke",
                        "invalid_phone_profile",
                        "invalid_phone_sound",
                        "phone_identity_changed",
                        "phone_platform_changed",
                        "recipient_unavailable",
                    }
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

    async def prepare_settings(self, value):
        """Saving is not an alarm trigger. Persist suppression for existing smoke."""
        if value["enabled"] and self.linking.active:
            episode = self._episode(
                "notifications", self.entry.runtime_data.source_entity_ids
            )
            if episode and episode["phase"] == "start":
                for recipient in value["recipients"]:
                    if not recipient["enabled"]:
                        continue
                    target = recipient["service"]
                    old = episode["receipts"].get(target)
                    if old is None:
                        if len(episode["receipts"]) >= 60:
                            raise AutomationError("automation_source_limit")
                        episode["receipts"][target] = {
                            "kind": "notification",
                            "target": target,
                            "identity": "",
                            "phase": "start",
                            "seen": list(episode["origins"]),
                            "status": "blocked",
                            "error": "settings_saved_during_smoke",
                        }
                await self._persist()

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
            if key == "notifications" and self.record_activity:
                for source in sorted(active.difference(old["origins"])):
                    self.record_activity(
                        "alarm",
                        "incident_origin",
                        "SMOKE_REPORTED",
                        source=source,
                        correlation=old["id"],
                        observed_at=now,
                    )
            old["origins"] = sorted(set(old["origins"]) | active)
            old["relevant"] = sorted(set(old["relevant"]) | set(relevant))
            if len(old["relevant"]) > 256:
                raise AutomationError("automation_source_limit")
            if not active and self._clear(old):
                old["phase"], old["updated"] = "recovery", now
                if key == "notifications" and self.record_activity:
                    self.record_activity(
                        "alarm",
                        "incident_clear",
                        "NO_SMOKE_REPORTED",
                        correlation=old["id"],
                    )
        return old

    async def _persist(self):
        async with self.lock:
            await self.store.async_save({"episodes": deepcopy(self.episodes)})

    def _source_label(self, source):
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
            or (entity.original_name if entity else None)
            or source
        )
        if not isinstance(name, str) or not name.strip():
            name = source
        return name, area.name if area else None

    def message(self, episode=None, *, test=False, example=False, include_time=True):
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
        if episode and phase == "start" and not example:
            ids = [
                s
                for s in ids
                if self.entry.runtime_data.source_statuses.get(s)
                is SourceStatus.SMOKE_REPORTED
            ]
        labels = [self._source_label(s) for s in ids[:12]]
        names = "; ".join(f"{name} ({area})" if area else name for name, area in labels)
        smoke_alert = phase == "start" and not test
        if smoke_alert and labels:
            name = " ".join(labels[0][0].split())
            if len(name) > 64:
                name = name[:63].rstrip() + "…"
            title = ("Rookmelding · " if nl else "Smoke alert · ") + name
            if len(ids) > 1:
                title += f" (+{len(ids) - 1})"
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
        body = names
        if groups or not smoke_alert:
            body += f"\n{('Groepen' if nl else 'Groups')}: {groups or '—'}"
        if include_time:
            body += f"\n{time}"
        if problems or not smoke_alert:
            body += (
                f"\n{('Zoemerproblemen' if nl else 'Sounder problems')}: {problems}."
            )
        if not smoke_alert:
            body += " " + (
                "Fysieke uitvoering niet bevestigd."
                if nl
                else "Physical execution is not confirmed."
            )
        elif episode:
            body += "\n" + (
                "Tik om het rookincident te bekijken."
                if nl
                else "Tap to view the smoke incident."
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
            return notification_route(
                self.hass,
                cfg,
                receipt["target"],
                phase=receipt["phase"],
                fault=self.fault,
            )["eligible"]
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

    async def _send(self, key, episode, receipt, *, new_sources=()):
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
            deadline = asyncio.timeout(REQUEST_TIMEOUT)
            try:
                async with deadline:
                    if receipt["kind"] == "notification":
                        # A follow-up alert leads with the newly reporting detector.
                        message_episode = episode
                        if new_sources:
                            message_episode = {
                                **episode,
                                "origins": sorted(
                                    episode["origins"],
                                    key=lambda source: source not in new_sources,
                                ),
                            }
                        await send_notification(
                            self.hass,
                            receipt["target"],
                            self.phone_plan(receipt["target"], message_episode)[
                                "message"
                            ],
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
            except TimeoutError:
                receipt["status"] = (
                    "outcome_unknown" if deadline.expired() else "failed"
                )
            except AutomationError as err:
                receipt["status"] = "blocked"
                receipt["error"] = str(err)
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
            if (
                episode["phase"] == "recovery"
                and old
                and old.get("error") == "settings_saved_during_smoke"
            ):
                continue
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
            new_sources = (
                active.difference(old["seen"])
                if old and episode["phase"] == "start"
                else ()
            )
            tasks.append(
                self._send("notifications", episode, row, new_sources=new_sources)
            )
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

    def phone_profile(self, target):
        row = next(
            (r for r in self.settings.value["recipients"] if r["service"] == target), {}
        )
        return row.get("profile")

    def phone_plan(self, target, episode=None, *, test=False, include_time=True):
        profile = self.phone_profile(target)
        if profile is None and any(
            r["service"] == target and "profile" in r
            for r in self.settings.value["recipients"]
        ):
            raise AutomationError("invalid_phone_profile")
        try:
            message = build_plan(
                self.hass,
                target,
                profile,
                self.message(episode, test=test, include_time=include_time),
                smoke=test or not episode or episode["phase"] == "start",
            )
        except ProfileError as err:
            raise AutomationError(str(err)) from err
        return {
            "message": message,
            "profile": deepcopy(profile),
            "phone_confirmed": False,
        }

    def confirmation(self, target, request_id=None):
        """Bind a browser acknowledgement to current recipient and message context."""
        service = self.hass.services.async_services().get("notify", {}).get(target)
        if service is None or target not in {
            r["service"] for r in recipients(self.hass)
        }:
            return ""
        try:
            message = self.phone_plan(target, test=True, include_time=False)
        except AutomationError:
            return ""
        # The time of dispatch changes naturally; substantive content must not.
        return hashlib.sha256(
            json.dumps(
                [target, id(service), self.settings.revision, message, request_id]
            ).encode()
        ).hexdigest()

    def snapshot(self):
        available = {r["service"] for r in recipients(self.hass)}
        plans = {}
        for target in available | {
            r["service"] for r in self.settings.value["recipients"]
        }:
            try:
                plans[target] = self.phone_plan(target, test=True)
            except AutomationError as err:
                plans[target] = {"error": str(err), "phone_confirmed": False}
        return {
            "profile_support": True,
            "phone_metadata": {
                target: receiver_metadata(self.hass, target) for target in available
            },
            "phone_plans": plans,
            "ios_sounds": IOS_SOUNDS,
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
            "test_preview": self.message(test=True),
            "confirmations": {
                target: self.confirmation(target) for target in available
            },
            "notification_routes": [
                notification_route(
                    self.hass,
                    self.settings.value,
                    target,
                    paused=self.closed or self.linking._paused,
                    fault=self.fault,
                )
                for target in sorted(
                    available
                    | {r["service"] for r in self.settings.value["recipients"]}
                )
            ],
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
        if (
            self.manual_tasks
            or request_id in self.manual_ids
            or (
                kind == "notification"
                and self.phone_evidence is not None
                and any(
                    row["request_id"] == request_id for row in self.phone_evidence.rows
                )
            )
        ):
            raise AutomationError("test_busy")
        if kind == "notification":
            if self.phone_profile(target) is not None and not identity:
                raise AutomationError("notification_confirmation_stale")
            if target not in {r["service"] for r in recipients(self.hass)}:
                raise AutomationError("recipient_unavailable")
            if (
                identity
                and identity != self.confirmation(target, request_id)
                and (
                    self.phone_profile(target) is not None
                    or identity != self.confirmation(target)
                )
            ):
                raise AutomationError("notification_confirmation_stale")
        elif kind == "script":
            current = script_target(self.hass, target)
            if current is None or current["identity"] != identity:
                raise AutomationError("script_changed")
        else:
            raise AutomationError("invalid_request")
        if len(self.manual_ids) >= 100:
            raise AutomationError("test_limit")
        self.manual_ids.add(request_id)
        row = {
            "kind": kind,
            "target": target,
            "status": "sending",
            "request_id": request_id,
            "started": dt_util.utcnow().isoformat(),
        }
        if kind == "notification":
            row["alarm_profile"] = deepcopy(self.phone_profile(target))
        # One latest receipt per target, bounded and without message contents.
        self.manual_results = [row] + [
            r for r in self.manual_results if (r["kind"], r["target"]) != (kind, target)
        ][:19]

        deadline = asyncio.timeout(REQUEST_TIMEOUT)

        async def dispatch():
            async with self.linking._semaphore, deadline:
                if self.closed or self.linking._paused or not authorized():
                    raise AutomationError("not_loaded")
                if kind == "notification":
                    if target not in {r["service"] for r in recipients(self.hass)}:
                        raise AutomationError("recipient_unavailable")
                    if (
                        identity
                        and identity != self.confirmation(target, request_id)
                        and (
                            self.phone_profile(target) is not None
                            or identity != self.confirmation(target)
                        )
                    ):
                        raise AutomationError("notification_confirmation_stale")
                    if self.phone_evidence:
                        await self.phone_evidence.register(row)
                    if self.closed or self.linking._paused or not authorized():
                        raise AutomationError("not_loaded")
                    if identity and identity not in {
                        self.confirmation(target, request_id),
                        self.confirmation(target)
                        if self.phone_profile(target) is None
                        else "",
                    }:
                        raise AutomationError("notification_confirmation_stale")
                    message = self.phone_plan(target, test=True)["message"]
                    row["attempted"] = True
                    await send_notification(self.hass, target, message)
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
        except TimeoutError:
            row["status"] = "outcome_unknown" if deadline.expired() else "failed"
        except AutomationError as err:
            row["status"] = "failed"
            row["error"] = str(err)
        except Exception:
            row["status"] = "failed"
        else:
            row["status"] = "accepted"
        finally:
            self.manual_tasks.discard(task)
            if kind == "notification" and self.phone_evidence:
                await self.phone_evidence.finish(row)
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
