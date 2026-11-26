"""Entry-owned, in-memory observations of selected Home Assistant sources."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .catalog_data import CATALOG
from .status import SourceStatus, StatusResult

if TYPE_CHECKING:
    from .panel import PanelController


@dataclass(slots=True)
class AlarmMeshRuntimeData:
    """Selected IDs and their latest interpretation, never persisted."""

    source_entity_ids: tuple[str, ...]
    source_statuses: dict[str, SourceStatus]
    result: StatusResult
    initialized_platforms: set[Platform] = field(default_factory=set)
    _listeners: set[CALLBACK_TYPE] = field(default_factory=set, init=False, repr=False)
    _observers: set[CALLBACK_TYPE] = field(default_factory=set, init=False, repr=False)
    panel: PanelController | None = field(default=None, init=False, repr=False)

    @callback
    def async_add_observer(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Observe each source change, including unchanged aggregate results."""
        self._observers.add(listener)
        return lambda: self._observers.discard(listener)

    @callback
    def async_notify_observers(self) -> None:
        for listener in tuple(self._observers):
            listener()

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe to changed results for this runtime only."""
        self._listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    @callback
    def async_set_result(self, result: StatusResult) -> None:
        """Publish a changed calculation without recalculating in entities."""
        if result == self.result:
            return
        self.result = result
        for listener in tuple(self._listeners):
            listener()

    @callback
    def async_clear_listeners(self) -> None:
        """Release remaining result subscriptions on teardown or failed setup."""
        self._listeners.clear()
        self._observers.clear()


type AlarmMeshConfigEntry = ConfigEntry[AlarmMeshRuntimeData]


def valid_source_ref(value: object) -> bool:
    """Validate a stored reference even when the selected device is offline."""
    return (
        isinstance(value, str)
        and len(value) <= 255
        and re.fullmatch(r"(?:binary_sensor|sensor)\.[a-z0-9_]+", value) is not None
    )


# Only reviewed exceptions to Home Assistant's smoke device class.
_MQTT_SMOKE_PROPERTIES = {
    (entry["vendor"].casefold(), model.casefold(), domain): tuple(properties)
    for entry in CATALOG["entries"]
    for domain, properties in entry.get("mqtt_smoke_properties", {}).items()
    for model in (entry["model"], f"{entry['description']} ({entry['model']})")
}


def mqtt_source_parts(entity, device, *, reviewed_only=False) -> tuple[str, str] | None:
    """Match a Z2M source property and extract its discovery base topic."""
    if not entity or entity.platform != "mqtt" or not device:
        return None
    properties = _MQTT_SMOKE_PROPERTIES.get(
        (
            (device.manufacturer or "").casefold(),
            (device.model_id or device.model or "").casefold(),
            entity.domain,
        ),
        (),
    )
    if not reviewed_only and entity.domain == "binary_sensor":
        properties = (*properties, "smoke")
    if not properties:
        return None
    ids = [
        value.removeprefix("zigbee2mqtt_")
        for domain, value in device.identifiers
        if domain == "mqtt" and value.startswith("zigbee2mqtt_")
    ]
    if len(ids) != 1:
        return None
    for prop in properties:
        prefix = f"{ids[0]}_{prop}_"
        if entity.unique_id.startswith(prefix) and (
            base := entity.unique_id[len(prefix) :]
        ):
            return ids[0], base
    return None


def is_reviewed_mqtt_source(hass, entity) -> bool:
    """Accept an enabled, reviewed source on its own registered MQTT device."""
    if (
        not entity
        or entity.domain not in {"sensor", "binary_sensor"}
        or entity.platform != "mqtt"
        or entity.disabled_by
        or not entity.device_id
    ):
        return False
    if entity.domain == "binary_sensor" and source_device_class(
        entity, hass.states.get(entity.entity_id)
    ) not in (None, "smoke"):
        return False
    device = dr.async_get(hass).async_get(entity.device_id)
    owner = (
        hass.config_entries.async_get_entry(entity.config_entry_id)
        if entity.config_entry_id
        else None
    )
    return bool(
        device
        and owner
        and owner.domain == "mqtt"
        and entity.config_entry_id in device.config_entries
        and mqtt_source_parts(entity, device, reviewed_only=True)
    )


def source_device_class(entity, state) -> str | None:
    """A registry override takes precedence over the current and original class."""
    return (
        (entity.device_class if entity else None)
        or (state.attributes.get("device_class") if state else None)
        or (entity.original_device_class if entity else None)
    )


def source_status_from_state(hass, entity_id: str, state: State | None) -> SourceStatus:
    """Translate a cached local state; unexpected values remain unknown."""
    if state is None:
        return SourceStatus.MISSING
    entity = er.async_get(hass).async_get(entity_id)
    if entity_id.startswith("sensor."):
        if not is_reviewed_mqtt_source(hass, entity):
            return SourceStatus.UNKNOWN
        return {
            "alarm": SourceStatus.SMOKE_REPORTED,
            "normal": SourceStatus.NO_SMOKE_REPORTED,
            STATE_UNAVAILABLE: SourceStatus.UNREACHABLE,
        }.get(state.state, SourceStatus.UNKNOWN)
    if (
        entity
        and entity.platform == "mqtt"
        and entity.original_device_class != "smoke"
        and state.attributes.get("device_class") != "smoke"
        and entity.device_class != "smoke"
        and not is_reviewed_mqtt_source(hass, entity)
    ):
        return SourceStatus.UNKNOWN
    return {
        STATE_ON: SourceStatus.SMOKE_REPORTED,
        STATE_OFF: SourceStatus.NO_SMOKE_REPORTED,
        STATE_UNKNOWN: SourceStatus.UNKNOWN,
        STATE_UNAVAILABLE: SourceStatus.UNREACHABLE,
    }.get(state.state, SourceStatus.UNKNOWN)


def current_source_status(hass, entity_id: str) -> SourceStatus:
    """Check the observed source again immediately before a decision."""
    return source_status_from_state(hass, entity_id, hass.states.get(entity_id))
