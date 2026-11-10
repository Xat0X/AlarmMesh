"""Entry-owned, in-memory observations of selected Home Assistant sources."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from .status import SourceStatus, StatusResult


@dataclass(slots=True)
class AlarmMeshRuntimeData:
    """Selected IDs and their latest interpretation, never persisted."""

    source_entity_ids: tuple[str, ...]
    source_statuses: dict[str, SourceStatus]
    result: StatusResult


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
