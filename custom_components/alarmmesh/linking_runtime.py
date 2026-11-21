"""Entry-owned, bounded HA action execution. No MQTT/Zigbee/device access."""

import asyncio
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass

from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from . import matter
from .capabilities import Capabilities, Control
from .linking import Activation, plan_activations, update_incidents
from .status import SourceStatus


@dataclass(frozen=True)
class PendingStart:
    control: Control
    before: State
    context_id: str
    expiry: asyncio.TimerHandle
    record: dict


@dataclass
class UnconfirmedFeedback:
    """Observation only, for the remainder of this continuous incident."""

    control: Control
    context_id: str
    awaiting_idle: bool = False


def _reports_linked_tone(state: State | None, control: Control) -> bool:
    return bool(
        state
        and state.state == control.option
        and not state.attributes.get("assumed_state")
    )


def _tone_loss_reason(state: State | None) -> str:
    if (
        not state
        or state.attributes.get("assumed_state")
        or state.state in {"unknown", "unavailable"}
    ):
        return "feedback_unavailable"
    return "feedback_idle" if state.state == "stop" else "feedback_other_tone"


class LinkingRuntime:
    """One attempt per target/incident; errors never cause a retry storm."""

    def __init__(self, hass: HomeAssistant, entry, groups, publish, observe_sounder):
        self.hass, self.entry, self.groups, self.publish = hass, entry, groups, publish
        self.observe_sounder = observe_sounder
        self.runtime = entry.runtime_data
        self.capabilities = Capabilities(hass)
        self.active: set[str] = set()
        self.previous: dict[str, SourceStatus] = {}
        self.attempted: dict[str, set[str]] = {}
        self.owned: dict[str, Control] = {}
        self.records: dict[str, dict] = {}
        self._pending_starts: dict[str, PendingStart] = {}
        self._unconfirmed: dict[str, UnconfirmedFeedback] = {}
        self._stopping: set[str] = set()
        self._task: asyncio.Task | None = None
        self._paused = True
        self._closed = False
        self._dirty = False
        self._unsubscribe = None
        self._observation_unsub = None
        self._semaphore = asyncio.Semaphore(8)
        self._last_snapshot = self.snapshot()
        self.effects_changed = lambda: None
        self.independent_test_source = lambda source: False

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
    def _related_changed(self, event):
        target = event.data["entity_id"]
        state = event.data["new_state"]
        observed_at = (state.last_updated if state else event.time_fired).isoformat()
        owned = self.owned.get(target)
        if owned and owned.safe_stop and not _reports_linked_tone(state, owned):
            # A manual stop followed by a rapid new sound can fit in one HA
            # loop iteration. The later sound no longer belongs to AlarmMesh.
            self.owned.pop(target)
            if self.records[target]["status"] != "stopping":
                self._no_stop(
                    self.records[target], _tone_loss_reason(state), observed_at
                )
        if pending := self._pending_starts.get(target):
            self._pending_starts.pop(target)
            pending.expiry.cancel()
            if self.records.get(target) is pending.record:
                if event.data["old_state"] is pending.before:
                    self._confirm_start(
                        pending.record,
                        pending.control,
                        state,
                        pending.context_id,
                        observed_at,
                    )
                else:
                    self._unconfirmed[target] = UnconfirmedFeedback(
                        pending.control,
                        pending.context_id,
                        _reports_linked_tone(state, pending.control),
                    )
                    self._no_stop(pending.record, "feedback_intervening", observed_at)
        elif followup := self._unconfirmed.get(target):
            self._observe_followup(followup, state, observed_at)
        self.changed()
        if not self._closed and not self._paused:
            self.publish()

    def _publish(self):
        snapshot = self.snapshot()
        if snapshot != self._last_snapshot and not self._closed and not self._paused:
            self._last_snapshot = deepcopy(snapshot)
            self.publish()
            self.effects_changed()

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
            or (
                self.capabilities.metadata(source)[2] == "matter"
                and not matter.origin_allowed(self.hass, source)
            )
            else status
            for source, status in self.runtime.source_statuses.items()
        }
        tests = {
            source
            for source in statuses
            if self.capabilities.test_blocked(source)
            and not self.independent_test_source(source)
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
                origins = self.active.intersection(
                    group.get("origins", group["members"])
                )
                for binding in group["linking"]["bindings"]:
                    if (attempted := self.attempted.get(binding["target"])) is not None:
                        attempted.update(origins)
                        if (record := self.records.get(binding["target"])) and record[
                            "source"
                        ] == binding["source"]:
                            record["origins"] = sorted(
                                set(record["origins"]) | (origins - {binding["source"]})
                            )
        self.attempted = {
            target: origins for target, origins in self.attempted.items() if origins
        }
        if self._pending_starts or self._unconfirmed:
            selected = set(self.runtime.source_entity_ids)
            bindings = [
                binding
                for group in self.groups.groups
                if group["linking"]["enabled"] and set(group["members"]) <= selected
                for binding in group["linking"]["bindings"]
            ]
            for target, pending in tuple(self._pending_starts.items()):
                if pending.control.binding() not in bindings:
                    self._forget_pending(target, "stop_binding_changed")
            for target, followup in tuple(self._unconfirmed.items()):
                if (
                    target not in self.attempted
                    or followup.control.binding() not in bindings
                ):
                    self._unconfirmed.pop(target)
        if self.active and not was_active:
            self.records = {
                key: value
                for key, value in self.records.items()
                if key in self.owned or key in self._pending_starts
            }
        self._dirty = True
        if self._task is None or self._task.done():
            task = self.entry.async_create_background_task(
                self.hass, self._run(), "AlarmMesh linked sounding"
            )
            self._task = None if task.done() else task
        self.effects_changed()

    def _current(self, activation: Activation) -> Control | None:
        """Last gate immediately before dispatch, even after waiting for a slot."""
        return self.assess(activation)[0]

    def assess(
        self, activation: Activation, active=None, *, independent=None
    ) -> tuple[Control | None, str]:
        """Read-only gates shared by dispatch and hypothetical configuration review."""
        if self._closed or self._paused:
            return None, "execution_paused"
        current = next(
            (a for a in self._plan(active) if a.binding == activation.binding), None
        )
        if current is None:
            return None, "preview_not_planned"
        source = activation.binding["source"]
        state = self.hass.states.get(source)
        if (
            not state
            or state.state != "off"
            or self.runtime.source_statuses.get(source)
            is not SourceStatus.NO_SMOKE_REPORTED
        ):
            return None, "preview_source_not_clear"
        if not any(
            (
                not self.capabilities.test_blocked(origin)
                or (independent or self.independent_test_source)(origin)
            )
            and not self.capabilities.source_identity_changed(origin)
            for origin in current.origins
        ):
            return None, "preview_origin_blocked"
        control = self.capabilities.resolve(activation.binding)
        reason = (
            self.capabilities.describe(source)["reason"]
            if control is None
            else "preview_eligible"
        )
        return control, reason if control is None and reason not in {
            "no_safe_stop",
            "automation_stop_separate",
        } else "control_changed" if control is None else reason

    def _plan(self, active=None):
        selected = set(self.runtime.source_entity_ids)
        return plan_activations(
            self.active if active is None else active,
            [g for g in self.groups.groups if set(g["members"]) <= selected],
        )

    @callback
    def _no_stop(self, record, reason, observed_at=None):
        if record.get("stop_reason") != reason:
            self.observe_sounder(
                record, reason, self.groups.groups, observed_at=observed_at
            )
        record["stop_reason"] = reason
        record["status"] = "not_stopped"

    def _observe_followup(self, followup, state, observed_at):
        if not state or state.attributes.get("assumed_state"):
            return
        target = followup.control.target
        record = self.records[target]
        if followup.awaiting_idle:
            if state.state != "stop":
                return
            result = "feedback_idle_observed"
            self._unconfirmed.pop(target)
        else:
            if state.state != followup.control.option:
                return
            followup.awaiting_idle = True
            if record["stop_reason"] == "feedback_window_expired":
                result = (
                    "feedback_late_matched"
                    if followup.context_id
                    in {state.context.id, state.context.parent_id}
                    else "feedback_late_unmatched"
                )
            else:
                result = "feedback_after_rejection"
        self.observe_sounder(
            record, result, self.groups.groups, observed_at=observed_at
        )

    def _confirm_start(self, record, control, state, context_id, observed_at):
        if not _reports_linked_tone(state, control):
            reason = _tone_loss_reason(state)
        elif context_id not in {state.context.id, state.context.parent_id}:
            reason = "feedback_context_missing"
        elif (
            not (resolved := self.capabilities.resolve(control.binding()))
            or not resolved.safe_stop
        ):
            reason = "feedback_binding_changed"
        else:
            self.owned[control.target] = control
            record["status"] = "sent"
            self.observe_sounder(
                record, "feedback_linked", self.groups.groups, observed_at=observed_at
            )
            return
        if reason != "feedback_binding_changed":
            self._unconfirmed[control.target] = UnconfirmedFeedback(
                control, context_id, _reports_linked_tone(state, control)
            )
        self._no_stop(record, reason, observed_at)

    @callback
    def _forget_pending(self, target, reason):
        pending = self._pending_starts.pop(target, None)
        if pending:
            pending.expiry.cancel()
            if self.records.get(target) is pending.record:
                if reason == "feedback_window_expired":
                    self._unconfirmed[target] = UnconfirmedFeedback(
                        pending.control, pending.context_id
                    )
                self._no_stop(pending.record, reason)

    @callback
    def _expire_pending(self, target):
        self._forget_pending(target, "feedback_window_expired")
        self._publish()

    async def _activate(self, activation, slots):
        async with slots:
            target = activation.binding["target"]
            if (
                target in self.attempted
                or target in self._stopping
                or self._closed
                or self._paused
                or (target in self.owned and self.owned[target].safe_stop)
            ):
                return
            record = {
                "source": activation.binding["source"],
                "target": target,
                "origins": sorted(activation.origins),
                "status": "blocked",
                "profile": activation.binding["profile"],
            }
            self._forget_pending(target, "feedback_intervening")
            self._unconfirmed.pop(target, None)
            self.records[target] = record
            if (control := self._current(activation)) is None:
                return
            current = next(a for a in self._plan() if a.binding == activation.binding)
            self.attempted[target] = set(current.origins)
            record["origins"] = sorted(current.origins)
            if not self.capabilities.is_idle(control):
                record["status"] = "already_active"
                return  # An existing/manual action is never adopted as ours.
            data = {"entity_id": target}
            if control.option is not None:
                data["option"] = control.option
            if control.duration is not None:
                data["duration"] = control.duration
            if control.tone is not None:
                data["tone"] = control.tone
            context = Context()
            if control.safe_stop:
                record["start_group"] = self._sole_sounding_group(control)
                record["start_id"] = context.id
            before = self.hass.states.get(target)
            record["status"] = "sending"
            self._publish()
            try:
                async with asyncio.timeout(10):
                    self.observe_sounder(record, "start_requested", self.groups.groups)
                    await self.hass.services.async_call(
                        control.domain,
                        control.service,
                        data,
                        blocking=True,
                        context=context,
                    )
            except asyncio.CancelledError:
                record["status"] = "outcome_unknown"
                raise
            except HomeAssistantError, TimeoutError:
                record["status"] = "failed"
            except Exception:  # A broken provider must not prevent other targets.
                record["status"] = "failed"
            else:
                if control.safe_stop:
                    state = self.hass.states.get(target)
                    if state is before:
                        # An accepted call can finish before the state arrives.
                        # Observe for two seconds without holding a dispatch slot.
                        expiry = self.hass.loop.call_later(
                            2, self._expire_pending, target
                        )
                        self._pending_starts[target] = PendingStart(
                            control,
                            before,
                            context.id,
                            expiry,
                            record,
                        )
                        record["status"] = "sent"
                        return
                    self._confirm_start(
                        record,
                        control,
                        state,
                        context.id,
                        state.last_updated.isoformat() if state else None,
                    )
                    return
                self.owned[target] = control
                record["status"] = "sent" if control.safe_stop else "sent_no_auto_stop"

    def _reports_clear(self, source: str) -> bool:
        state = self.hass.states.get(source)
        return bool(
            state
            and state.state == "off"
            and not state.attributes.get("assumed_state")
            and self.runtime.source_statuses.get(source)
            is SourceStatus.NO_SMOKE_REPORTED
            and not self.capabilities.source_identity_changed(source)
            and (
                self.capabilities.metadata(source)[2] != "matter"
                or matter.origin_allowed(self.hass, source)
            )
        )

    def _sole_sounding_group(self, control):
        """A shared sound cannot be stopped on behalf of just one active group."""
        matches = []
        for group in self.groups.groups:
            if (
                group["linking"]["enabled"]
                and control.binding() in group["linking"]["bindings"]
                and any(
                    origin != control.source
                    and (
                        origin in self.active or self.hass.states.is_state(origin, "on")
                    )
                    for origin in group.get("origins", group["members"])
                )
            ):
                matches.append(group["id"])
        return matches[0] if len(matches) == 1 else None

    def _can_stop_for_group(self, group, control):
        record = self.records[control.target]
        feedback = self.hass.states.get(control.target)
        return (
            not self._closed
            and not self._paused
            and control.safe_stop
            and self.owned.get(control.target) is control
            and control.target not in self._stopping
            and record.get("start_group") == group["id"]
            and group["linking"]["enabled"]
            and set(group["members"]) <= set(self.runtime.source_entity_ids)
            and control.source in group["members"]
            and self._reports_clear(control.source)
            and not self.capabilities.test_blocked(control.source)
            and _reports_linked_tone(feedback, control)
            and record["start_id"] in {feedback.context.id, feedback.context.parent_id}
            and self._sole_sounding_group(control) == group["id"]
            and self.capabilities.resolve(control.binding()) == control
        )

    def group_stop_choices(self, group):
        return [
            {"source": control.source, "start_id": self.records[target]["start_id"]}
            for target, control in self.owned.items()
            if self._can_stop_for_group(group, control)
        ]

    async def stop_group(self, group_id, revision, start_ids):
        """Only act on the individual starts that were displayed to this admin."""

        async def stop_one(target, control):
            current = next((g for g in self.groups.groups if g["id"] == group_id), None)
            if (
                self.groups.revision != revision
                or current is None
                or self.records.get(target, {}).get("start_id") not in start_ids
                or not self._can_stop_for_group(current, control)
            ):
                return False
            return await self._send_stop(target, "group_stop_requested")

        outcomes = await asyncio.gather(
            *(
                stop_one(target, control)
                for target, control in tuple(self.owned.items())
                if self.records[target].get("start_id") in start_ids
            )
        )
        self._publish()
        return {"accepted": sum(outcomes), "requested": len(start_ids)}

    async def _stop(self, target, control):
        # No stop after disable/remap/reload; ownership is process-local only.
        if self.owned.get(target) is not control or target in self._stopping:
            return
        bindings = [
            b
            for g in self.groups.groups
            if g.get("linking", {}).get("enabled")
            for b in g["linking"]["bindings"]
        ]
        if control.binding() not in bindings:
            if control.safe_stop:
                self._no_stop(self.records[target], "stop_binding_changed")
            else:
                self.records[target]["status"] = "not_stopped"
            self.owned.pop(target, None)
            return
        if not control.safe_stop:
            return
        target_state = self.hass.states.get(target)
        if not _reports_linked_tone(target_state, control):
            # A later manual tone/stop or lost feedback cannot remain our action.
            self._no_stop(self.records[target], _tone_loss_reason(target_state))
            self.owned.pop(target, None)
            return
        resolved = self.capabilities.resolve(control.binding())
        if self._closed or self._paused:
            self._no_stop(self.records[target], "stop_monitor_paused")
            return
        if not resolved or not resolved.safe_stop:
            self._no_stop(self.records[target], "stop_binding_changed")
            return
        if not self._reports_clear(control.source):
            reason = (
                "stop_target_smoke"
                if self.runtime.source_statuses.get(control.source)
                is SourceStatus.SMOKE_REPORTED
                else "stop_target_not_clear"
            )
            self._no_stop(self.records[target], reason)
            return
        if any(
            not self._reports_clear(source)
            for source in self.records[target]["origins"]
        ):
            self._no_stop(self.records[target], "stop_origins_not_clear")
            return
        # A new origin may have joined while another target's request was in flight.
        if any(action.binding == control.binding() for action in self._plan()):
            return
        # A source becoming unknown never clears its latched incident.
        if any(origin in self.active for origin in self.records[target]["origins"]):
            return
        await self._send_stop(target, "stop_requested")

    async def _send_stop(self, target, event):
        # Claim the target before handing control back to the HA event loop.
        self._stopping.add(target)
        record = self.records[target]
        record["status"] = "stopping"
        self._publish()
        try:
            async with asyncio.timeout(10):
                self.observe_sounder(record, event, self.groups.groups)
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": target, "option": "stop"},
                    blocking=True,
                )
        except asyncio.CancelledError:
            record["status"] = "outcome_unknown"
            raise
        except Exception:
            record["status"] = "stop_failed"
        else:
            record["status"] = "stop_sent"
        finally:
            self.owned.pop(target, None)
            self._stopping.discard(target)
            self.changed()
        return record["status"] == "stop_sent"

    async def _run(self):
        try:
            while self._dirty and not self._closed and not self._paused:
                self._dirty = False
                for target, control in tuple(self.owned.items()):
                    if target in self._stopping:
                        continue
                    state = self.hass.states.get(target)
                    if control.safe_stop and not _reports_linked_tone(state, control):
                        self._no_stop(self.records[target], _tone_loss_reason(state))
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
        self._unconfirmed.clear()
        for target in tuple(self._pending_starts):
            self._forget_pending(target, "stop_monitor_paused")
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
