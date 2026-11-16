"""Read-only hypothetical analysis. No writes, incident updates or HA actions."""

from . import matter
from .automation import (
    DEFAULT_ACTIONS,
    AutomationError,
    notification_plan,
    recipients,
    script_receipt_key,
    script_target,
)
from .linking import Activation
from .status import SourceStatus


def group_preview(panel, group_id: str | None, source: str) -> dict:
    group = next((g for g in panel.groups.groups if g["id"] == group_id), None)
    if (group_id is not None and group is None) or source not in (
        group["members"] if group else panel.runtime.source_entity_ids
    ):
        raise AutomationError("invalid_preview")
    group = group or {
        "id": None,
        "members": [],
        "origins": [],
        "linking": {"enabled": False, "bindings": []},
    }
    engine = panel.linking

    def independent(origin):
        return panel.selftests.independent_source(origin, cache=False)

    selected = set(engine.runtime.source_entity_ids)
    source_ok = (
        source in selected
        and not engine.capabilities.source_identity_changed(source)
        and (
            engine.capabilities.metadata(source)[2] != "matter"
            or matter.origin_allowed(panel.hass, source)
        )
        and (not engine.capabilities.test_blocked(source) or independent(source))
    )
    active = engine.active | {source} if source_ok else set(engine.active)
    can_start = source_ok and source in group.get("origins", group["members"])
    targets = []
    for binding in group["linking"]["bindings"]:
        activation = Activation(
            binding,
            frozenset(active.intersection(group.get("origins", group["members"]))),
        )
        control, reason = engine.assess(activation, active, independent=independent)
        if not group["linking"]["enabled"]:
            reason = "disabled"
        elif not can_start:
            reason = "preview_origin_blocked"
        elif not set(group["members"]) <= selected:
            reason = "storedSourceMissing"
        elif binding["source"] in active:
            reason = "preview_target_smoke"
        elif binding["target"] in engine.attempted:
            reason = "preview_already_attempted"
        elif control is not None and not engine.capabilities.is_idle(control):
            reason = "already_active"
        eligible = reason == "preview_eligible"
        targets.append(
            {
                "source": binding["source"],
                "target": binding["target"],
                "eligible": eligible,
                "reason": reason,
                "safe_stop": bool(control and control.safe_stop),
            }
        )
    settings = panel.effects.settings.value
    available = {row["service"] for row in recipients(panel.hass)}
    phones = [
        {
            "target": row["service"],
            "eligible": source_ok
            and settings["enabled"]
            and row["enabled"]
            and row["service"] in available
            and not panel.effects.fault,
            "reason": "disabled"
            if not settings["enabled"] or not row["enabled"]
            else "recipient_unavailable"
            if row["service"] not in available
            else "preview_origin_blocked"
            if not source_ok
            else panel.effects.fault or "preview_eligible",
        }
        for row in settings["recipients"]
    ]
    notification_episode = panel.effects.episodes.get("notifications")
    if notification_episode and notification_episode["phase"] == "start":
        for row in phones:
            old = notification_episode["receipts"].get(row["target"])
            needed, _ = notification_plan(
                old,
                "start",
                active,
                notification_episode["origins"],
                lambda s: (
                    engine.runtime.source_statuses.get(s)
                    is SourceStatus.NO_SMOKE_REPORTED
                    and not engine.capabilities.source_identity_changed(s)
                ),
            )
            if row["eligible"] and not needed:
                row.update(eligible=False, reason="preview_already_attempted")
    scripts = []
    actions = group.get("actions", DEFAULT_ACTIONS)
    for phase in ("start", "recovery"):
        for index, binding in enumerate(actions[phase]):
            current = script_target(panel.hass, binding["entity_id"])
            valid = current is not None and current["identity"] == binding["identity"]
            reason = (
                "disabled"
                if not actions["enabled"]
                else "script_changed"
                if not valid
                else "preview_origin_blocked"
                if not can_start
                else panel.effects.fault or "preview_eligible"
            )
            episode = panel.effects.episodes.get(group_id)
            if (
                reason == "preview_eligible"
                and episode
                and episode["phase"] == "start"
                and script_receipt_key(phase, binding) in episode["receipts"]
            ):
                reason = "preview_already_attempted"
            elif reason == "preview_eligible" and phase == "recovery":
                reason = "preview_after_recovery"
            scripts.append(
                {
                    "target": binding["entity_id"],
                    "name": current["name"] if current else binding["entity_id"],
                    "phase": phase,
                    "order": index + 1,
                    "eligible": reason
                    in {"preview_eligible", "preview_after_recovery"},
                    "reason": reason,
                }
            )
    paused = engine._paused or engine._closed or panel.effects.closed
    if paused:
        for row in phones + scripts:
            row.update(eligible=False, reason="execution_paused")
    return {
        "paused": paused,
        "readonly": True,
        "revision": panel.groups.revision,
        "source": source,
        "group": group_id,
        "can_start": can_start,
        "groups": [
            {
                "id": g["id"],
                "can_start": source_ok and source in g.get("origins", g["members"]),
            }
            for g in panel.groups.groups
            if source in g["members"]
        ],
        "targets": targets,
        "phones": phones,
        "scripts": scripts,
        "linking_enabled": group["linking"]["enabled"],
        "notifications_enabled": settings["enabled"],
        "actions_enabled": actions["enabled"],
        "notification_recovery": settings["recovery"],
        "recovery_sources": group.get("origins", group["members"]),
        "notification_recovery_sources": list(engine.runtime.source_entity_ids),
        "physical_confirmed": False,
        "existing_incident": bool(engine.active),
    }


def source_preview(panel, source: str) -> dict:
    """Aggregate the same group assessment; phones are global, scripts per group."""
    base = group_preview(panel, None, source)
    groups = [
        group_preview(panel, g["id"], source)
        for g in panel.groups.groups
        if source in g["members"]
    ]
    targets = {}
    for group in groups:
        for row in group["targets"]:
            target = targets.setdefault(
                row["target"],
                {
                    "target": row["target"],
                    "source": row["source"],
                    "eligible": False,
                    "via": [],
                },
            )
            target["eligible"] |= row["eligible"]
            target["via"].append(
                {
                    "group": group["group"],
                    "reason": row["reason"],
                    "eligible": row["eligible"],
                }
            )
    return {**base, "groups": groups, "targets": list(targets.values())}
