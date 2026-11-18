"""Bounded user observations of exact manual requests, never delivery guarantees."""

import asyncio
import re
from copy import deepcopy
from datetime import timedelta

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .automation import AutomationError
from .notification_profiles import receiver_metadata, validate_profile

LIMIT = 100
DAYS = 30


class PhoneEvidence:
    """Separate optional evidence, without changing notification settings/history."""

    def __init__(self, hass, entry, effects, publish):
        self.hass, self.effects, self.publish = hass, effects, publish
        self.store = Store(
            hass, 1, f"alarmmesh.phone_evidence.{entry.entry_id}", atomic_writes=True
        )
        self.rows, self.revision = [], 0
        self.error = None
        self.closed = False
        self.lock = asyncio.Lock()

    def _kept(self, rows):
        cutoff = dt_util.utcnow() - timedelta(days=DAYS)
        return [r for r in rows if dt_util.parse_datetime(r["started"]) > cutoff][
            -LIMIT:
        ]

    async def load(self):
        try:
            value = await self.store.async_load()
            if value is None:
                return  # Existing installations start with no invented confirmations.
            if (
                not isinstance(value, dict)
                or set(value) != {"schema", "revision", "requests"}
                or type(value["schema"]) is not int
                or value["schema"] != 1
                or type(value["revision"]) is not int
                or value["revision"] < 0
                or not isinstance(value["requests"], list)
                or len(value["requests"]) > LIMIT
            ):
                raise ValueError
            ids = set()
            for row in value["requests"]:
                if (
                    not isinstance(row, dict)
                    or set(row)
                    != {
                        "request_id",
                        "target",
                        "started",
                        "profile",
                        "identity",
                        "status",
                        "attempted",
                        "observations",
                    }
                    or not isinstance(row["request_id"], str)
                    or not re.fullmatch(r"[a-f0-9]{32}", row["request_id"])
                    or row["request_id"] in ids
                    or not isinstance(row["target"], str)
                    or not re.fullmatch(r"mobile_app_[a-z0-9_]{1,240}", row["target"])
                    or not isinstance(row["identity"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", row["identity"])
                    or type(row["attempted"]) is not bool
                    or row["status"]
                    not in {"sending", "accepted", "failed", "outcome_unknown"}
                    or not isinstance(row["observations"], list)
                    or len(row["observations"]) > 5
                ):
                    raise ValueError
                ids.add(row["request_id"])
                if row["profile"] is not None:
                    validate_profile(row["profile"])
                for stamp in [
                    row["started"],
                    *[o.get("at") for o in row["observations"]],
                ]:
                    when = (
                        dt_util.parse_datetime(stamp)
                        if isinstance(stamp, str)
                        else None
                    )
                    if when is None or when.tzinfo is None:
                        raise ValueError
                for o in row["observations"]:
                    if (
                        set(o) != {"at", "received", "heard", "simulation"}
                        or any(
                            o[k] is not None and type(o[k]) is not bool
                            for k in ("received", "heard")
                        )
                        or type(o["simulation"]) is not bool
                    ):
                        raise ValueError
                if row["status"] == "sending":
                    row["status"] = "outcome_unknown"
            self.rows, self.revision = self._kept(value["requests"]), value["revision"]
            if len(self.rows) != len(value["requests"]):
                await self._save(self.rows)
        except Exception:
            self.error = "phone_evidence_storage"

    async def _save(self, rows):
        revision = self.revision + 1
        await self.store.async_save(
            {"schema": 1, "revision": revision, "requests": rows}
        )
        self.rows, self.revision = rows, revision

    async def register(self, request):
        """Ancillary evidence failure must not block the existing notification route."""
        async with self.lock:
            if self.closed or self.error:
                return
            metadata = receiver_metadata(self.hass, request["target"])
            row = {
                k: deepcopy(request[k])
                for k in ("request_id", "target", "started", "status")
            }
            row.update(
                profile=deepcopy(request.get("alarm_profile")),
                identity=metadata["identity"],
                attempted=False,
                observations=[],
            )
            try:
                await self._save(self._kept([*self.rows, row]))
            except Exception:
                self.error = "phone_evidence_storage"

    async def finish(self, request):
        async with self.lock:
            if self.closed or self.error:
                return
            rows = deepcopy(self.rows)
            row = next(
                (r for r in rows if r["request_id"] == request["request_id"]), None
            )
            if row is None:
                return
            row.update(
                status=request["status"], attempted=request.get("attempted", False)
            )
            try:
                await self._save(self._kept(rows))
            except Exception:
                self.error = "phone_evidence_storage"

    async def observe(
        self, request_id, revision, received, heard, simulation, authorized
    ):
        async with self.lock:
            if self.closed or not authorized():
                raise AutomationError("not_loaded")
            if self.error:
                raise AutomationError(self.error)
            if type(revision) is not int or revision != self.revision:
                raise AutomationError("conflict")
            if (
                any(v is not None and type(v) is not bool for v in (received, heard))
                or type(simulation) is not bool
            ):
                raise AutomationError("invalid_observation")
            rows = deepcopy(self._kept(self.rows))
            row = next((r for r in rows if r["request_id"] == request_id), None)
            if row is None or not row["attempted"] or row["status"] == "sending":
                raise AutomationError("phone_request_missing")
            value = {"received": received, "heard": heard, "simulation": simulation}
            if row["observations"] and all(
                row["observations"][-1][k] == v for k, v in value.items()
            ):
                return False
            row["observations"] = [
                *row["observations"],
                {"at": dt_util.utcnow().isoformat(), **value},
            ][-5:]
            await self._save(rows)
        self.publish()
        return True

    def snapshot(self):
        rows = deepcopy(self._kept(self.rows))
        stored = {r["service"]: r for r in self.effects.settings.value["recipients"]}
        for row in rows:
            target = row["target"]
            current = receiver_metadata(self.hass, target)
            reason = "phone_request_current"
            if self.error:
                reason = self.error
            elif not current["identity"]:
                reason = "recipient_unavailable"
            elif current["identity"] != row["identity"]:
                reason = "phone_identity_changed"
            elif (
                target not in stored or stored[target].get("profile") != row["profile"]
            ):
                reason = "phone_observation_old_profile"
            else:
                try:
                    self.effects.phone_plan(target, test=True)
                except AutomationError as err:
                    reason = str(err)
            row.update(current=reason == "phone_request_current", reason=reason)
        return {
            "revision": self.revision,
            "requests": list(reversed(rows)),
            "error": self.error,
            "retention_days": DAYS,
            "limit": LIMIT,
        }

    async def close(self):
        self.closed = True
        async with self.lock:
            pass
