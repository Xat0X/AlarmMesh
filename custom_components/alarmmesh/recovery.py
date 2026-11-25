"""Guided group-only recovery; options remain a separate explicit HA flow."""

import hashlib
import json
from copy import deepcopy

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .automation import AutomationError
from .config_flow import _validate_sources
from .runtime import current_source_status
from .status import SourceStatus


def recovery_plan(panel, source):
    snapshot = panel.snapshot()
    refs = [g for g in panel.groups.groups if source in g["members"]]
    if source not in panel.runtime.source_entity_ids and not refs:
        raise AutomationError("not_found")

    def identity(eid):
        e = er.async_get(panel.hass).async_get(eid)
        d = (
            dr.async_get(panel.hass).async_get(e.device_id)
            if e and e.device_id
            else None
        )
        return [
            eid,
            e.id if e else None,
            e.unique_id if e else None,
            e.config_entry_id if e else None,
            e.device_id if e else None,
            sorted(d.identifiers) if d else None,
            [d.manufacturer, d.model, d.model_id, d.sw_version] if d else None,
            [e.original_device_class, e.device_class] if e else None,
        ]

    candidates = [
        s
        for s in snapshot["sources"]
        if s["entity_id"] != source
        and not _validate_sources(panel.hass, [s["entity_id"]])
        and not s["identity_changed"]
    ]
    token = hashlib.sha256(
        json.dumps(
            [
                panel.groups.revision,
                dict(panel.entry.options),
                [identity(s) for s in panel.runtime.source_entity_ids],
                identity(source),
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    affected = set().union(*(set(g["members"]) for g in refs)) | {source}
    blocked = bool(panel.linking.active & affected) or any(
        current_source_status(panel.hass, s) is SourceStatus.SMOKE_REPORTED
        for s in affected
    )
    blocked |= panel.selftests._request is not None
    enabled = panel.effects.settings.value["enabled"] or any(
        g["linking"]["enabled"] or g.get("actions", {}).get("enabled") for g in refs
    )
    return {
        "token": token,
        "revision": panel.groups.revision,
        "source": source,
        "groups": [g["id"] for g in refs],
        "candidates": [
            {
                "entity_id": s["entity_id"],
                "name": s["name"],
                "area_name": s["area_name"],
            }
            for s in candidates
        ],
        "blocked": bool(blocked),
        "outputs_enabled": bool(enabled),
        "selected": source in panel.runtime.source_entity_ids,
    }


async def recover_groups(panel, source, target, groups, token):
    """One atomic group save, no options/history/authority transfer."""
    async with panel.groups._lock:
        if panel.groups._closed or panel.linking._paused:
            raise AutomationError("not_loaded")
        plan = recovery_plan(panel, source)
        if token != plan["token"]:
            raise AutomationError("conflict")
        if plan["blocked"]:
            raise AutomationError("recovery_busy")
        if plan["outputs_enabled"]:
            raise AutomationError("recovery_disable")
        if (
            target not in {c["entity_id"] for c in plan["candidates"]}
            or current_source_status(panel.hass, target)
            is not SourceStatus.NO_SMOKE_REPORTED
        ):
            raise AutomationError("recovery_candidate")
        if (
            not isinstance(groups, list)
            or len(set(groups)) != len(groups)
            or not set(groups) <= set(plan["groups"])
        ):
            raise AutomationError("invalid_members")
        updated = deepcopy(panel.groups.groups)
        for group in updated:
            if group["id"] not in groups:
                continue
            group["members"] = list(
                dict.fromkeys(target if s == source else s for s in group["members"])
            )
            # Organizational membership only. New source is not an incident origin.
            group["origins"] = [
                s
                for s in group.get("origins", group["members"])
                if s not in {source, target}
            ]
            group["linking"]["bindings"] = [
                b
                for b in group["linking"]["bindings"]
                if b["source"] not in {source, target}
            ]
        if updated == panel.groups.groups:
            raise AutomationError("conflict")
        revision = panel.groups.revision + 1
        await panel.groups.store.async_save(
            {"schema": 3, "revision": revision, "groups": updated}
        )
        panel.groups.groups, panel.groups.revision = updated, revision
