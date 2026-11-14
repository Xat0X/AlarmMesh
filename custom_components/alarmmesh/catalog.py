"""Offline catalog: evidence and recognition, never execution authority."""

from .catalog_data import CATALOG
from .profiles import PROFILES, validate_profiles

ASSESSMENTS = {
    "detection": {"documented", "conditional", "not_available", "unconfirmed"},
    "activation": {
        "implemented",
        "documented_not_implemented",
        "not_available",
        "unconfirmed",
    },
    "stop": {"implemented", "not_authorized"},
    "self_test": {"implemented_read_only", "conditional_read_only", "not_available"},
}


def validate_catalog(data: dict) -> None:
    """Reject incomplete reviews or dangling control references during development."""
    validate_profiles()
    if data["schema"] != 1 or data["definitions"] != len(data["entries"]):
        raise ValueError("Invalid catalog schema/count")
    identities = set()
    variants = set()
    for entry in data["entries"]:
        if entry["id"] in identities or entry["physical_tested"] is not False:
            raise ValueError("Duplicate identity or unsupported physical claim")
        identities.add(entry["id"])
        if set(entry["providers"]) != {"zigbee2mqtt", "zha"}:
            raise ValueError("Every definition needs both provider assessments")
        for alias in [
            {"vendor": entry["vendor"], "model": entry["model"]},
            *entry["aliases"],
        ]:
            key = (alias["vendor"], alias["model"])
            if key in variants:
                raise ValueError("Duplicate website variant")
            variants.add(key)
        for subject in [entry, *entry["aliases"]]:
            if set(subject.get("providers", {})) != {"zigbee2mqtt", "zha"}:
                raise ValueError("Every variant needs both provider assessments")
            for provider, review in subject["providers"].items():
                if (
                    not {
                        "detection",
                        "information",
                        "activation",
                        "stop",
                        "self_test",
                        "requirements",
                        "gaps",
                        "sources",
                        "profile",
                    }
                    <= review.keys()
                ):
                    raise ValueError("Incomplete A-F assessment")
                profile = review["profile"]
                if any(
                    review[key] not in allowed for key, allowed in ASSESSMENTS.items()
                ):
                    raise ValueError("Unknown assessment must not imply support")
                if (review["activation"] == "implemented") != bool(profile):
                    raise ValueError("Implemented activation requires an exact profile")
                if profile and (
                    profile not in PROFILES
                    or PROFILES[profile].provider != provider
                    or not entry["matchers"][provider]
                    or not review["sources"]
                ):
                    raise ValueError("Unreviewed control profile")
                if (
                    profile
                    and subject is not entry
                    and {
                        "vendor": subject["vendor"].casefold(),
                        "model": subject["model"].casefold(),
                    }
                    not in entry["matchers"][provider]
                ):
                    raise ValueError(
                        "Alias authority requires its own provider matcher"
                    )
                if review["stop"] == "implemented" and (
                    not profile or not PROFILES[profile].safe_stop
                ):
                    raise ValueError("Unreviewed stop authority")
    if data["website_rows"] != len(variants) or data["variants"] != len(variants) - len(
        identities
    ):
        raise ValueError("Incomplete website inventory")


def recognize(provider: str, model: str, vendor: str) -> dict | None:
    """Exact provider/registry model+vendor, never visible names or entity suffixes.

    Shared TS0601 IDs only match a documented manufacturer fingerprint. Multiple
    matching definitions are ambiguous, including future overlapping signatures.
    """
    model, vendor = model.casefold(), vendor.casefold()
    found = []
    for entry in CATALOG["entries"]:
        matches = list(entry["matchers"].get(provider, ()))
        if provider == "zigbee2mqtt":
            # Older Z2M discovery used 'description (model)' as its model field.
            matched = any(
                m["vendor"] == vendor
                and (model == m["model"] or model.endswith(f" ({m['model']})"))
                for m in matches
            )
        else:
            matched = {"vendor": vendor, "model": model} in matches
        # Additional read-only recognition never grants an action matcher.
        if not matched:
            matched = any(
                f["model"]
                and f["manufacturer"]
                and f["model"].casefold() == model
                and f["manufacturer"].casefold() == vendor
                for f in entry["fingerprints"]
            )
        if not matched and provider == "zha":
            vendors = {m["vendor"] for m in entry["matchers"]["zigbee2mqtt"]}
            matched = vendor in vendors and model in {
                m.casefold() for m in entry["zigbee_models"]
            }
        if matched:
            found.append(entry)
    return found[0] if len(found) == 1 else None


def action_profile(entry: dict, provider: str, model: str, vendor: str) -> str | None:
    """Recognition may be broader than authority (e.g. read-only Tuya variants)."""
    model, vendor = model.casefold(), vendor.casefold()
    matches = entry["matchers"].get(provider, ())
    if any(
        m["vendor"] == vendor
        and (
            model == m["model"]
            or provider == "zigbee2mqtt"
            and model.endswith(f" ({m['model']})")
        )
        for m in matches
    ):
        return entry["providers"][provider]["profile"]
    return None
