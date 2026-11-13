"""Entry-owned, in-memory observations of selected Home Assistant sources."""

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


def source_status_from_state(state: State | None) -> SourceStatus:
    """Translate a cached local state; unexpected values remain unknown."""
    if state is None:
        return SourceStatus.MISSING
    return {
        STATE_ON: SourceStatus.SMOKE_REPORTED,
        STATE_OFF: SourceStatus.NO_SMOKE_REPORTED,
        STATE_UNKNOWN: SourceStatus.UNKNOWN,
        STATE_UNAVAILABLE: SourceStatus.UNREACHABLE,
    }.get(state.state, SourceStatus.UNKNOWN)
