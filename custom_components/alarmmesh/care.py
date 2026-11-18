"""Bounded, identity-bound journal of maintenance reported by a person."""

import asyncio
import re
from datetime import date

from homeassistant.helpers.storage import Store

from .automation import AutomationError


class CareJournal:
    def __init__(self, hass, entry):
        self.store = Store(
            hass, 1, f"alarmmesh.care.{entry.entry_id}", atomic_writes=True
        )
        self.rows = []
        self.lock = asyncio.Lock()
        self.damaged = False
        self.closed = False

    @staticmethod
    def validate(row):
        if set(row) != {"id", "identity", "date", "kind", "note"}:
            raise ValueError
        if not re.fullmatch("[0-9a-f]{32}", row["id"]) or not re.fullmatch(
            "[0-9a-f]{64}", row["identity"]
        ):
            raise ValueError
        if date.fromisoformat(row["date"]).isoformat() != row["date"]:
            raise ValueError
        if (
            row["kind"] not in {"battery", "clean", "note"}
            or not isinstance(row["note"], str)
            or len(row["note"]) > 200
        ):
            raise ValueError
        if row["kind"] == "note" and not row["note"].strip():
            raise ValueError

    async def load(self):
        try:
            rows = await self.store.async_load()
            if rows is None:
                return
            if not isinstance(rows, list) or len(rows) > 500:
                raise ValueError
            for row in rows:
                self.validate(row)
            if len({row["id"] for row in rows}) != len(rows):
                raise ValueError
            self.rows = rows
        except Exception:
            self.damaged = True

    async def append(self, row, allowed):
        async with self.lock:
            if self.damaged or self.closed or not allowed():
                raise AutomationError("control_changed")
            try:
                self.validate(row)
            except TypeError, ValueError:
                raise AutomationError("invalid_note") from None
            prior = next((r for r in self.rows if r["id"] == row["id"]), None)
            if prior is not None:
                if prior != row:
                    raise AutomationError("conflict")
                return
            rows = [*self.rows, dict(row)][-500:]
            await self.store.async_save(rows)
            self.rows = rows

    async def close(self):
        self.closed = True
        async with self.lock:
            pass  # Let an accepted atomic save finish before loading the next runtime.
