"""Cached Z-Wave JS entity support. No driver, radio, refresh or commands."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


def invalid_source(hass, source):
    """A renamed/overridden CO, heat or diagnostic entity is never smoke."""
    entity = er.async_get(hass).async_get(source)
    return bool(
        entity
        and entity.platform == "zwave_js"
        and (
            entity.domain != "binary_sensor"
            or entity.original_device_class != "smoke"
            or entity.device_class not in (None, "smoke")
        )
    )


def properties(hass, source):
    """Read original HA classes on the exact device and config entry only.

    HA can expose root-node and endpoint devices separately. We deliberately
    never traverse parents or infer associations. Ambiguous values stay unknown.
    """
    registry = er.async_get(hass)
    entity = registry.async_get(source)
    if (
        not entity
        or entity.platform != "zwave_js"
        or not entity.device_id
        or entity.disabled_by
        or invalid_source(hass, source)
    ):
        return []
    device = dr.async_get(hass).async_get(entity.device_id)
    if not device or not any(domain == "zwave_js" for domain, _ in device.identifiers):
        return []
    rows = []
    for related in er.async_entries_for_device(registry, entity.device_id):
        if (
            related.platform != "zwave_js"
            or related.config_entry_id != entity.config_entry_id
            or related.disabled_by
            or related.device_class not in (None, related.original_device_class)
        ):
            continue
        key = {
            ("sensor", "battery"): "battery",
            ("binary_sensor", "battery"): "battery_low",
            ("binary_sensor", "problem"): "fault",
        }.get((related.domain, related.original_device_class))
        if key:
            rows.append((key, related))
    return rows


def describe(hass, source):
    """Distinguish smoke observation from unverified sounder/test commands."""
    return {
        "source_valid": not invalid_source(hass, source),
        "sounder": False,
        "self_test": False,
        "physical_tested": False,
    }
