"""Explicit support allowlist. Never export names, raw IDs or provider payloads."""

import re

from .catalog import CATALOG

PROVIDERS = {"zigbee2mqtt", "mqtt", "zha", "matter", "zwave_js", "unknown_origin"}
ASSESSMENTS = {"linkable", "detection_only", "not_confirmed", "setting_needed"}
REASONS = {
    "zwave_observation_only",
    "matter_identity_changed",
    "matter_identity_storage_error",
    "matter_no_sounder_route",
    "matter_interconnect_origin",
    "matter_origin_unknown",
    "matter_interconnect_unseparated",
    "no_verified_profile",
    "source_identity_changed",
    "ambiguous_control",
    "control_missing",
    "control_unavailable",
    "control_changed",
    "invalid_control_options",
    "service_missing",
    "siren_features_missing",
    "siren_tone_missing",
    "bosch_broadcast_must_be_off",
    "aqara_linkage_required",
    "aqara_firmware_21",
    "remote_permission_required",
    "no_safe_stop",
    "automation_stop_separate",
    "storedSourceMissing",
    "script_changed",
    "recipient_unavailable",
    "noRoom",
    "setupNoSources",
    "checkSourceUnavailable",
    "maintenance_storage_error",
    "maintenance_source_limit",
    "automation_storage_error",
    "reminder_storage_error",
    "reminder_identity_changed",
    "activityIncomplete",
}
RESULTS = {
    "SMOKE_REPORTED",
    "NO_SMOKE_REPORTED",
    "INDETERMINATE",
    "COMPLETE",
    "INCOMPLETE",
    "NOT_CONFIGURED",
    "UNKNOWN",
    "UNREACHABLE",
    "MISSING",
}
FAILURES = {"failed", "blocked", "stop_failed", "outcome_unknown", "not_stopped"}


def known(value, allowed):
    return value if isinstance(value, str) and value in allowed else "unknown"


def version(value):
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-.][a-zA-Z0-9.]+)?", value)
        else "unknown"
    )


def support_report(snapshot: dict, alarmmesh_version: str, ha_version: str) -> dict:
    """Construct from scratch; default anonymization cannot be disabled by a client."""
    aliases = {}

    def alias(kind, raw):
        key = (kind, str(raw))
        if key not in aliases:
            aliases[key] = f"{kind} {1 + sum(k[0] == kind for k in aliases)}"
        return aliases[key]

    sources = []
    models = {
        entry["id"]: entry["model"]
        for entry in [*CATALOG["entries"], *CATALOG.get("matter_entries", [])]
    }
    for source in snapshot["sources"]:
        cap = source.get("capability", {})
        health = cap.get("details", {}).get("maintenance", {})
        percent = health.get("battery_percent")
        sources.append(
            {
                "alias": alias("Detector", source["entity_id"]),
                "room": alias("Room", source["area_id"])
                if source.get("area_id")
                else "unknown",
                "source_status": known(source.get("status"), RESULTS),
                "provider": known(cap.get("origin"), PROVIDERS),
                "transport": known(
                    cap.get("matter", {}).get("transport"),
                    {"thread", "wifi", "bridge", "unknown"},
                ),
                "source_kind": known(
                    cap.get("matter", {}).get("source_kind"),
                    {"local_smoke", "interconnect_smoke", "unknown"},
                ),
                "model": models.get(cap.get("catalog_id"), "unknown")
                if isinstance(cap.get("catalog_id"), str)
                else "unknown",
                "assessment": known(cap.get("status"), ASSESSMENTS),
                "reason": known(cap.get("reason"), REASONS),
                "battery_percent": percent
                if type(percent) in {int, float} and 0 <= percent <= 100
                else None,
                "battery_low": health.get("battery_low")
                if type(health.get("battery_low")) is bool
                else None,
                "fault": health.get("fault")
                if type(health.get("fault")) is bool
                else None,
                "end_of_service": health.get("end_of_service")
                if type(health.get("end_of_service")) is bool
                else None,
            }
        )
    assignments = []
    for group in snapshot["groups"]:
        group_alias = alias("Group", group["id"])
        for row in group.get("binding_checks", []):
            assignments.append(
                {
                    "group": group_alias,
                    "kind": "sounder",
                    "target": alias("Target", row["target"]),
                    "source": alias("Detector", row["source"]),
                    "valid": row.get("valid") is True,
                    "reason": known(row.get("reason"), REASONS)
                    if not row.get("valid")
                    else "configured",
                }
            )
        for row in group.get("script_checks", []):
            assignments.append(
                {
                    "group": group_alias,
                    "kind": "script",
                    "target": alias("Script", row["entity_id"]),
                    "phase": known(row.get("phase"), {"start", "recovery"}),
                    "valid": row.get("valid") is True,
                    "reason": "configured" if row.get("valid") else "script_changed",
                }
            )
    problems = []
    if snapshot.get("activity", {}).get("incomplete"):
        problems.append({"reason": "activityIncomplete", "setting": "maintenance"})
    if snapshot.get("reminders", {}).get("error"):
        problems.append({"reason": "reminder_storage_error", "setting": "maintenance"})
    for row in snapshot.get("reminders", {}).get("items", []):
        if row.get("attention") in {
            "reminder_identity_changed",
            "recipient_unavailable",
        }:
            problems.append(
                {
                    "reason": row["attention"],
                    "setting": "maintenance",
                    "source": alias("Detector", row["source"]),
                }
            )
    if snapshot.get("incident", {}).get("executor_state") in ("paused", "closed"):
        problems.append({"reason": "execution_paused", "setting": "integration"})
    for issue in snapshot.get("review", {}).get("issues", []):
        row = {
            "reason": known(issue.get("code"), REASONS),
            "setting": "maintenance"
            if issue.get("purpose") == "maintenance"
            else "groups"
            if issue.get("group")
            else "notifications"
            if issue.get("code") == "recipient_unavailable"
            else "sources",
        }
        if issue.get("source"):
            row["source"] = alias("Detector", issue["source"])
        if issue.get("group"):
            row["group"] = alias("Group", issue["group"])
        problems.append(row)
    phones = []
    for section in ("automation", "maintenance"):
        cfg = snapshot.get(section, {})
        missing = cfg.get("missing_recipients", [])
        for recipient in cfg.get("settings", {}).get("recipients", []):
            phones.append(
                {
                    "alias": alias("Recipient", recipient["service"]),
                    "purpose": section,
                    "enabled": recipient.get("enabled") is True,
                    "available": recipient["service"] not in missing,
                }
            )
    errors = []

    def failure(kind, target, status):
        if isinstance(status, str) and status in FAILURES and len(errors) < 60:
            errors.append(
                {
                    "kind": kind,
                    "target": alias(
                        "Script"
                        if kind == "script"
                        else "Recipient"
                        if kind in {"notification", "maintenance"}
                        else "Target",
                        target,
                    ),
                    "status": status,
                }
            )

    for target in snapshot.get("incident", {}).get("targets", []):
        failure("sounder", target["target"], target.get("status"))
    for episode in snapshot.get("automation", {}).get("episodes", []):
        for receipt in episode.get("receipts", {}).values():
            failure(
                "script" if receipt.get("kind") == "script" else "notification",
                receipt["target"],
                receipt.get("status"),
            )
    for row in snapshot.get("maintenance", {}).get("issues", []):
        for target, receipt in row.get("receipts", {}).items():
            for status in receipt.values():
                failure("maintenance", target, status)
    return {
        "schema": 1,
        "versions": {
            "alarmmesh": version(alarmmesh_version),
            "home_assistant": version(ha_version),
        },
        "result": {
            key: known(snapshot.get("result", {}).get(key), RESULTS)
            for key in ("smoke", "availability")
        },
        "counts": {
            "sources": len(sources),
            "groups": len(snapshot["groups"]),
            "valid_assignments": sum(r["valid"] for r in assignments),
            "invalid_assignments": sum(not r["valid"] for r in assignments),
            "activity_events": len(snapshot.get("activity", {}).get("events", [])),
            "reminders": len(snapshot.get("reminders", {}).get("items", [])),
        },
        "sources": sources,
        "assignments": assignments,
        "recipients": phones,
        "problems": problems,
        "recorded_errors": errors,
        "physical_confirmed": False,
    }
