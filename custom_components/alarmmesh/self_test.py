"""Reviewed built-in self-checks through existing HA entities, never raw Zigbee."""

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import partial

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import matter
from .automation import AutomationError
from .capabilities import Capabilities
from .status import SourceStatus


@dataclass(frozen=True)
class TestProfile:
    key: str
    domain: str = "button"
    option: str | None = None
    flag: str | None = "test"
    result: str | None = None
    source_url: str = ""


MQTT_TESTS = {
    "HS1SA-E-PLUS": TestProfile(
        "trigger_selftest",
        source_url="https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html",
    ),
    "JY-GZ-01AQ": TestProfile(
        "selftest", source_url="https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html"
    ),
    **{
        model: TestProfile(
            "test_cycle",
            "select",
            "start",
            "test_in_progress",
            "halo_test_result",
            "https://github.com/Koenkk/zigbee-herdsman-converters/blob/afdaa028a0972d801da762196ddfb2df631ea0cc/src/devices/halo_smart_labs.ts"
            if model == "HALO+"
            else "https://www.zigbee2mqtt.io/devices/HALO.html",
        )
        for model in ("HALO", "HALO+")
    },
}
ZHA_TEST = TestProfile(
    "self_test",
    flag=None,
    source_url="https://github.com/zigpy/zha/blob/2.4.3/zha/application/platforms/button/__init__.py",
)
RUNNING = {"sending", "request_sent", "test_active"}
RESULTS = {
    "success": "device_success",
    **{
        key: "device_failed"
        for key in (
            "fail_ion",
            "fail_photo",
            "fail_co",
            "fail_temperature",
            "fail_weather",
            "fail_other",
        )
    },
}


@dataclass(eq=False)
class TestRequest:
    """Task-local ownership, observation handles and a fixed acceptance deadline."""

    request_id: str
    record: dict
    control: dict
    deadline: datetime
    dispatched: bool = False
    seen_active: bool = False
    unsubscribe: Callable[[], None] | None = None
    cancel_timer: Callable[[], None] | None = None


class SelfTests:
    """One explicit request at a time; elapsed time can only mean unknown."""

    def __init__(self, hass, entry, linking, publish):
        self.hass, self.entry, self.linking, self.publish = (
            hass,
            entry,
            linking,
            publish,
        )
        self.cap = Capabilities(hass)
        self.store = Store(
            hass, 1, f"alarmmesh.selftest.{entry.entry_id}", atomic_writes=True
        )
        self.record = None
        self._request: TestRequest | None = None
        self.closed = False
        self.stopping = False
        self.lock = asyncio.Lock()
        self.tasks = set()
        self.requests = set()
        self.request_ids = set()
        self.separate_smoke = {}

    async def load(self):
        record = await self.store.async_load()
        if record is not None:
            if (
                not isinstance(record, dict)
                or set(record)
                != {"source", "profile", "identity", "status", "started", "request_id"}
                or any(not isinstance(v, str) or len(v) > 255 for v in record.values())
                or record["status"]
                not in RUNNING
                | {
                    "device_success",
                    "device_failed",
                    "failed",
                    "outcome_unknown",
                    "storage_error",
                }
                or dt_util.parse_datetime(record["started"]) is None
            ):
                raise AutomationError("invalid_storage")
            self.record = deepcopy(record)
            self.request_ids.add(record["request_id"])
            if self.record["status"] in RUNNING:
                self.record["status"] = "outcome_unknown"
                await self.store.async_save(self.record)

    def resolve(self, source, *, cache=True):
        if (
            source not in self.entry.runtime_data.source_entity_ids
            or self.cap.source_identity_changed(source)
        ):
            return None
        entity, device, origin, model, vendor, catalog = self.cap.metadata(source)
        if not entity or entity.disabled_by or not device:
            return None
        if origin == "zigbee2mqtt" and catalog:
            profile = MQTT_TESTS.get(catalog["model"])
        elif origin == "zha" and (vendor, model) == ("LUMI", "lumi.sensor_smoke.acn03"):
            profile = ZHA_TEST
        elif origin == "matter" and matter.origin_allowed(self.hass, source):
            profile = TestProfile(
                "self_test_request",
                flag=None,
                source_url=matter.HA_SOURCE + "button.py",
            )
        else:
            return None
        if (
            profile is None
            or origin != "matter"
            and str(device.sw_version) in {"21", "0021", "0.0.0_0021"}
        ):
            return None
        rows = [
            e
            for e in self.cap._property(source, origin, profile.key)
            if e.domain == profile.domain
        ]
        if len(rows) != 1:
            return None
        target = rows[0]
        state = self.hass.states.get(target.entity_id)
        service = "select_option" if profile.option else "press"
        if (
            not state
            or state.state == "unavailable"
            or not self.hass.services.has_service(profile.domain, service)
            or (
                profile.option
                and not {"start", "cancel"} <= set(state.attributes.get("options", []))
            )
        ):
            return None
        flags = (
            [
                e.entity_id
                for e in self.cap._property(source, origin, profile.flag)
                if e.domain == "binary_sensor"
            ]
            if profile.flag
            else []
        )
        if origin == "matter":
            flags = [
                e.entity_id
                for e in self.cap._property(source, origin, "test_in_progress")
                if e.domain == "binary_sensor"
            ]
            if len(flags) > 1:
                return None
        results = (
            [
                e.entity_id
                for e in self.cap._property(source, origin, profile.result)
                if e.domain == "sensor"
            ]
            if profile.result
            else []
        )
        if (profile.flag and len(flags) != 1) or (profile.result and len(results) != 1):
            return None
        # Cached contract evidence, not observed smoke or command ownership. Losing
        # the test control cannot make a genuine separate smoke value a test echo.
        if cache:
            self.separate_smoke[source] = (
                entity.id,
                entity.unique_id,
                device.id,
                origin,
                model,
                vendor,
            )
        sounders = [
            {k: c[k] for k in ("target", "identity", "idle_states")}
            for c in self.cap.describe(source)["controls"]
        ]
        identity = hashlib.sha256(
            json.dumps(
                [
                    entity.id,
                    entity.unique_id,
                    entity.device_id,
                    target.id,
                    target.unique_id,
                    origin,
                    model,
                    vendor,
                    device.sw_version,
                    asdict(profile),
                    sounders,
                    [
                        [e.id, e.unique_id, e.config_entry_id]
                        for e in self.cap.related(source)
                        if e.entity_id in flags + results
                    ],
                ]
            ).encode()
        ).hexdigest()
        return {
            "source": source,
            "target": target.entity_id,
            "identity": identity,
            "profile": f"{origin}_{profile.key}",
            "domain": profile.domain,
            "service": service,
            "option": profile.option,
            "flags": flags,
            "results": results,
            "documentation": profile.source_url,
            "has_explicit_result": bool(results),
            "sounders": sounders,
        }

    def independent_source(self, source, *, cache=True):
        # These contracts expose smoke separately from self-test/linkage status.
        if self.cap.metadata(source)[2] == "matter":
            return matter.origin_allowed(self.hass, source)
        if self.resolve(source, cache=cache) is not None:
            return True
        entity, device, origin, model, vendor, _ = self.cap.metadata(source)
        return bool(
            entity
            and device
            and not self.cap.source_identity_changed(source)
            and self.separate_smoke.get(source)
            == (entity.id, entity.unique_id, device.id, origin, model, vendor)
        )

    @callback
    def check_identity(self):
        request = self._request
        if request is None or not self._live(request):
            return
        control = self.resolve(request.record["source"])
        if control is None or control["identity"] != request.record["identity"]:
            self._status(request, "outcome_unknown")
            self._schedule_save(request, "AlarmMesh changed self-test identity")

    def describe(self, source):
        control = self.resolve(source)
        return {
            "available": control is not None,
            "reason": "selftest_supported" if control else "selftest_unsupported",
            "control": {
                k: control[k]
                for k in (
                    "source",
                    "identity",
                    "profile",
                    "documentation",
                    "has_explicit_result",
                )
            }
            if control
            else None,
            "record": deepcopy(self.record)
            if self.record and self.record["source"] == source
            else None,
        }

    @staticmethod
    def _clear_watch(request):
        for handle in (request.unsubscribe, request.cancel_timer):
            if handle:
                handle()
        request.unsubscribe = request.cancel_timer = None

    def _owns(self, request):
        return (
            request is self._request
            and self.record is request.record
            and request.request_id == request.record["request_id"]
        )

    def _live(self, request):
        return (
            not self.closed
            and not self.stopping
            and self._owns(request)
            and request.record["status"] in RUNNING
            and dt_util.utcnow() < request.deadline
        )

    def _status(self, request, status):
        if (
            self.closed
            or not self._owns(request)
            or request.record["status"] not in RUNNING
        ):
            return
        request.record["status"] = status
        if status not in RUNNING:
            self._clear_watch(request)
        self.publish()

    @callback
    def _observed(self, event, request):
        if not self._live(request):
            self._expired(None, request)
            return
        if not request.dispatched:
            return  # Another operation's feedback cannot claim a queued request.
        current = self.resolve(request.record["source"])
        if current is None or current["identity"] != request.record["identity"]:
            self._status(request, "outcome_unknown")
        else:
            new = event.data.get("new_state")
            key = event.data["entity_id"]
            if key in current["flags"] and new and new.state == "on":
                request.seen_active = True
                self._status(request, "test_active")
            elif key in current["results"] and new:
                if new.state == "running":
                    request.seen_active = True
                    self._status(request, "test_active")
                elif request.seen_active and new.state in RESULTS:
                    self._status(request, RESULTS[new.state])
            elif (
                key in current["flags"]
                and new
                and new.state == "off"
                and request.seen_active
                and not current["results"]
            ):
                self._status(request, "outcome_unknown")  # Finished is not success.
        self._schedule_save(request, "AlarmMesh self-test observation")

    def _schedule_save(self, request, name):
        if self.closed or not self._owns(request):
            return
        task = self.entry.async_create_background_task(
            self.hass, self._save(request), name
        )
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _save(self, request):
        async with self.lock:
            # A save queued by A must not overwrite B, even if it acquires the
            # storage lock only after B has installed its own durable intent.
            if not self.closed and self._owns(request):
                try:
                    await self.store.async_save(deepcopy(request.record))
                except Exception:
                    self._status(request, "storage_error")

    @callback
    def _expired(self, _now, request=None):
        # The optional default is the existing explicit simulation hook. Every
        # actual timer/observer is bound to its own request, never this default.
        request = request if request is not None else self._request
        if request is None or not self._owns(request):
            return
        if request.record["status"] in RUNNING:
            self._status(request, "outcome_unknown")
            self._schedule_save(request, "AlarmMesh self-test timeout")

    async def start(
        self, source, identity, confirmed, authorized=lambda: True, request_id=None
    ):
        if confirmed is not True:
            raise AutomationError("test_confirmation_required")
        task = asyncio.current_task()
        self.requests.add(task)
        request = None
        initialized = False
        try:
            async with self.lock:
                if not isinstance(request_id, str) or not re.fullmatch(
                    "[a-f0-9]{32}", request_id
                ):
                    raise AutomationError("invalid_request")
                if request_id in self.request_ids:
                    raise AutomationError("test_busy")
                if len(self.request_ids) >= 100:
                    raise AutomationError("test_limit")
                control = self.resolve(source)
                if self.closed or self.stopping or self.linking._paused:
                    raise AutomationError("not_loaded")
                if self.record and self.record["status"] in RUNNING:
                    raise AutomationError("test_busy")
                if control is None or control["identity"] != identity:
                    raise AutomationError("control_changed")
                if self._conflicts(control):
                    raise AutomationError("test_conflict")
                if self._request is not None:
                    self._clear_watch(self._request)
                now = dt_util.utcnow()
                record = {k: control[k] for k in ("source", "profile", "identity")}
                record.update(
                    status="sending", started=now.isoformat(), request_id=request_id
                )
                request = TestRequest(
                    request_id, record, control, now + timedelta(seconds=120)
                )
                self._request, self.record = request, record
                self.request_ids.add(request_id)
                # Disk-first intent; cancellation and callbacks keep this identity.
                await self.store.async_save(deepcopy(record))
                request.unsubscribe = async_track_state_change_event(
                    self.hass,
                    [source, control["target"], *control["flags"], *control["results"]],
                    partial(self._observed, request=request),
                )
                remaining = max(
                    0, (request.deadline - dt_util.utcnow()).total_seconds()
                )
                request.cancel_timer = async_call_later(
                    self.hass, remaining, partial(self._expired, request=request)
                )
                initialized = True
                self.publish()
            async with self.linking._semaphore, asyncio.timeout(10):
                if (
                    not self._live(request)
                    or self.linking._paused
                    or not authorized()
                    or self.resolve(source) != control
                    or self._conflicts(control)
                ):
                    self._status(request, "outcome_unknown")
                else:
                    data = {"entity_id": control["target"]}
                    if control["option"]:
                        data["option"] = control["option"]
                    request.dispatched = True
                    await self.hass.services.async_call(
                        control["domain"], control["service"], data, blocking=True
                    )
                    # Even a late service completion belongs only to this request.
                    if self._live(request) and record["status"] == "sending":
                        self._status(request, "request_sent")
                    elif not self._live(request):
                        self._status(request, "outcome_unknown")
        except asyncio.CancelledError:
            if request is not None:
                self._status(request, "outcome_unknown")
            raise
        except Exception:
            if request is None:
                raise
            status = "failed" if self._live(request) else "outcome_unknown"
            self._status(request, status if initialized else "storage_error")
            if not initialized:
                raise
        finally:
            try:
                if request is not None:
                    await self._save(request)
            finally:
                self.requests.discard(task)
        return deepcopy(record)

    def _conflicts(self, control):
        """Recheck after queueing; availability and external controls can change."""
        return bool(
            self.linking.active
            or any(
                s is not SourceStatus.NO_SMOKE_REPORTED
                for s in self.entry.runtime_data.source_statuses.values()
            )
            or any(
                self.cap.test_blocked(s)
                for s in self.entry.runtime_data.source_entity_ids
            )
            or any(not self.hass.states.is_state(f, "off") for f in control["flags"])
            or any(
                c["source"] == control["source"]
                and c["status"] in {"sending", "sent", "sent_no_auto_stop", "stopping"}
                for c in self.linking.records.values()
            )
            or any(
                (state := self.hass.states.get(candidate["target"])) is None
                or state.state not in candidate["idle_states"]
                for candidate in control["sounders"]
            )
        )

    async def pause(self):
        self.stopping = True
        current = self._request
        if current is not None:
            self._status(current, "outcome_unknown")
        for request in tuple(self.requests):
            request.cancel()
        if self.requests:
            await asyncio.gather(*tuple(self.requests), return_exceptions=True)
        if current is not None:
            self._clear_watch(current)
        for task in tuple(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        if current is not None:
            await self._save(current)

    async def close(self):
        await self.pause()
        self.closed = True
