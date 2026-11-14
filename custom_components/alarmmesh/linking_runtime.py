"""Entry-owned, bounded HA action execution. No MQTT/Zigbee/device access."""

import asyncio
from contextlib import suppress
from copy import deepcopy

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from .capabilities import Capabilities, Control
from .linking import Activation, plan_activations, update_incidents
from .status import SourceStatus


class LinkingRuntime:
    """One attempt per target/incident; errors never cause a retry storm."""

    def __init__(self, hass: HomeAssistant, entry, groups, publish):
        self.hass, self.entry, self.groups, self.publish = hass, entry, groups, publish
        self.runtime = entry.runtime_data
        self.capabilities = Capabilities(hass)
        self.active: set[str] = set()
        self.previous: dict[str, SourceStatus] = {}
        self.attempted: dict[str, set[str]] = {}
        self.owned: dict[str, Control] = {}
        self.records: dict[str, dict] = {}
        self._task: asyncio.Task | None = None
        self._paused = True
        self._closed = False
        self._dirty = False
        self._unsubscribe = None
        self._observation_unsub = None
        self._semaphore = asyncio.Semaphore(8)
        self._last_snapshot = self.snapshot()

    def start(self):
        self._paused = False
        self._observation_unsub = self.runtime.async_add_observer(self.changed)
        self.refresh_watch()
        self.changed()

    @callback
    def refresh_watch(self, *_args):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        if self._closed:
            return
        related = {
            e.entity_id
            for source in self.runtime.source_entity_ids
            for e in self.capabilities.related(source)
        } - set(self.runtime.source_entity_ids)
        if related:
            self._unsubscribe = async_track_state_change_event(
                self.hass, related, self._related_changed
            )
        self.changed()

    @callback
    def _related_changed(self, *_args):
        self.changed()
        if not self._closed and not self._paused:
            self.publish()

    def _publish(self):
        snapshot = self.snapshot()
        if snapshot != self._last_snapshot and not self._closed and not self._paused:
            self._last_snapshot = deepcopy(snapshot)
            self.publish()

    @callback
    def changed(self, *_args):
        if self._closed or self._paused:
            return
        # Keep the shared read-only calculation untouched. A known non-smoke
        # replacement cannot start or clear an execution incident. Missing
        # identity information still cannot release a previously latched origin.
        statuses = {
            source: SourceStatus.UNKNOWN
            if self.capabilities.source_identity_changed(source)
            else status
            for source, status in self.runtime.source_statuses.items()
        }
        tests = {
            source for source in statuses if self.capabilities.test_blocked(source)
        }
        was_active = bool(self.active)
        self.active = update_incidents(self.active, self.previous, statuses, tests)
        self.previous = dict(statuses)
        # Suppress each target only for its own continuous incident lifetime.
        # Joining/overlapping origins extend it; unrelated groups do not.
        for origins in self.attempted.values():
            origins.intersection_update(self.active)
        for group in self.groups.groups:
            if group["linking"]["enabled"]:
                origins = self.active.intersection(group["members"])
                for binding in group["linking"]["bindings"]:
                    if (attempted := self.attempted.get(binding["target"])) is not None:
                        attempted.update(origins)
        self.attempted = {
            target: origins for target, origins in self.attempted.items() if origins
        }
        if self.active and not was_active:
            self.records = {
                key: value for key, value in self.records.items() if key in self.owned
            }
        self._dirty = True
        if self._task is None or self._task.done():
            task = self.entry.async_create_background_task(
                self.hass, self._run(), "AlarmMesh linked sounding"
            )
            self._task = None if task.done() else task

    def _current(self, activation: Activation) -> Control | None:
        """Last gate immediately before dispatch, even after waiting for a slot."""
        if self._closed or self._paused:
            return None
        current = next(
            (a for a in self._plan() if a.binding == activation.binding), None
        )
        if current is None:
            return None
        source = activation.binding["source"]
        state = self.hass.states.get(source)
        if (
            not state
            or state.state != "off"
            or self.runtime.source_statuses.get(source)
            is not SourceStatus.NO_SMOKE_REPORTED
        ):
            return None
        if not any(
            not self.capabilities.test_blocked(origin)
            and not self.capabilities.source_identity_changed(origin)
            for origin in current.origins
        ):
            return None
        return self.capabilities.resolve(activation.binding)

    def _plan(self):
        selected = set(self.runtime.source_entity_ids)
        return plan_activations(
            self.active,
            [g for g in self.groups.groups if set(g["members"]) <= selected],
        )

    async def _activate(self, activation, slots):
        async with slots:
            target = activation.binding["target"]
            if target in self.attempted or self._closed or self._paused:
                return
            record = {
                "source": activation.binding["source"],
                "target": target,
                "origins": sorted(activation.origins),
                "status": "blocked",
                "profile": activation.binding["profile"],
            }
            self.records[target] = record
            if (control := self._current(activation)) is None:
                return
            current = next(a for a in self._plan() if a.binding == activation.binding)
            self.attempted[target] = set(current.origins)
            record["origins"] = sorted(current.origins)
            state = self.hass.states.get(target)
            if not state or state.state not in control.idle_states:
                record["status"] = "already_active"
                return  # An existing/manual action is never adopted as ours.
            data = {"entity_id": target}
            if control.option is not None:
                data["option"] = control.option
            if control.duration is not None:
                data["duration"] = control.duration
            if control.tone is not None:
                data["tone"] = control.tone
            record["status"] = "sending"
            self._publish()
            try:
                async with asyncio.timeout(10):
                    await self.hass.services.async_call(
                        control.domain, control.service, data, blocking=True
                    )
            except asyncio.CancelledError:
                record["status"] = "outcome_unknown"
                raise
            except HomeAssistantError, TimeoutError:
                record["status"] = "failed"
            except Exception:  # A broken provider must not prevent other targets.
                record["status"] = "failed"
            else:
                self.owned[target] = control
                record["status"] = "sent" if control.safe_stop else "sent_no_auto_stop"

    async def _stop(self, target, control):
        # No stop after disable/remap/reload; ownership is process-local only.
        bindings = [
            b
            for g in self.groups.groups
            if g.get("linking", {}).get("enabled")
            for b in g["linking"]["bindings"]
        ]
        if control.binding() not in bindings:
            self.records[target]["status"] = "not_stopped"
            self.owned.pop(target, None)
            return
        if not control.safe_stop:
            return
        target_state = self.hass.states.get(target)
        if not target_state or target_state.state != control.option:
            # A later manual tone/stop or lost feedback cannot remain our action.
            self.records[target]["status"] = "not_stopped"
            self.owned.pop(target, None)
            return
        state = self.hass.states.get(control.source)
        if (
            self._closed
            or self._paused
            or not state
            or state.state != "off"
            or self.capabilities.resolve(control.binding()) is None
            or self.runtime.source_statuses.get(control.source)
            is not SourceStatus.NO_SMOKE_REPORTED
        ):
            self.records[target]["status"] = "not_stopped"
            return
        # A source becoming unknown never clears its latched incident.
        if any(origin in self.active for origin in self.records[target]["origins"]):
            return
        self.records[target]["status"] = "stopping"
        self._publish()
        try:
            async with asyncio.timeout(10):
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": target, "option": "stop"},
                    blocking=True,
                )
        except asyncio.CancelledError:
            self.records[target]["status"] = "outcome_unknown"
            raise
        except Exception:
            self.records[target]["status"] = "stop_failed"
        else:
            self.records[target]["status"] = "stop_sent"
        self.owned.pop(target, None)  # No automatic stop retries, including failure.

    async def _run(self):
        try:
            while self._dirty and not self._closed and not self._paused:
                self._dirty = False
                for target, control in tuple(self.owned.items()):
                    state = self.hass.states.get(target)
                    if control.safe_stop and (
                        not state or state.state != control.option
                    ):
                        self.records[target]["status"] = "not_stopped"
                        self.owned.pop(target, None)
                desired = self._plan()
                for activation in desired:
                    if activation.binding["target"] in self.owned:
                        record = self.records[activation.binding["target"]]
                        record["origins"] = sorted(
                            set(record["origins"]) | activation.origins
                        )
                await asyncio.gather(
                    *(self._activate(action, self._semaphore) for action in desired)
                )
                desired_targets = {action.binding["target"] for action in desired}
                await asyncio.gather(
                    *(
                        self._stop(target, control)
                        for target, control in tuple(self.owned.items())
                        if target not in desired_targets
                    )
                )
                if not self._closed and not self._paused:
                    self._publish()
        finally:
            self._task = None

    def snapshot(self):
        return {
            "active_sources": sorted(self.active),
            "targets": list(self.records.values()),
            "physical_confirmed": False,
            "executor_state": "closed"
            if self._closed
            else "paused"
            if self._paused
            else "running",
        }

    async def pause(self):
        self._paused = True
        if self._task:
            task = self._task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def resume(self):
        if not self._closed:
            self._paused = False
            self.changed()

    async def close(self):
        self._closed = True
        await self.pause()
        if self._unsubscribe:
            self._unsubscribe()
        if self._observation_unsub:
            self._observation_unsub()
