"""Pure interpretation of source smoke reports, independent of Home Assistant."""

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum


class SourceStatus(Enum):
    """Explicit report or reason a source cannot provide a usable report."""

    SMOKE_REPORTED = "smoke_reported"
    NO_SMOKE_REPORTED = "no_smoke_reported"
    UNKNOWN = "unknown"
    UNREACHABLE = "unreachable"
    MISSING = "missing"


class SmokeStatus(Enum):
    """Combined smoke report; absence of a report does not imply no smoke."""

    SMOKE_REPORTED = "smoke_reported"
    NO_SMOKE_REPORTED = "no_smoke_reported"
    INDETERMINATE = "indeterminate"


class SourceAvailability(Enum):
    """Whether all configured sources provided usable reports."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class StatusResult:
    """Independent smoke interpretation and source availability."""

    smoke_status: SmokeStatus
    source_availability: SourceAvailability


def evaluate_status(sources: Collection[SourceStatus]) -> StatusResult:
    """Evaluate reports without modifying the supplied collection.

    Raise TypeError unless sources is a non-string collection containing only
    SourceStatus members. Validate every member even if smoke is reported.
    Unknown, unreachable and missing reports never imply absence of smoke.
    """
    if not isinstance(sources, Collection) or isinstance(sources, (str, bytes)):
        raise TypeError("sources must be a collection of SourceStatus members")
    if any(not isinstance(source, SourceStatus) for source in sources):
        raise TypeError("every source must be a SourceStatus member")

    if not sources:
        return StatusResult(
            SmokeStatus.INDETERMINATE, SourceAvailability.NOT_CONFIGURED
        )

    complete = all(
        source in (SourceStatus.SMOKE_REPORTED, SourceStatus.NO_SMOKE_REPORTED)
        for source in sources
    )
    availability = (
        SourceAvailability.COMPLETE if complete else SourceAvailability.INCOMPLETE
    )
    if SourceStatus.SMOKE_REPORTED in sources:
        smoke = SmokeStatus.SMOKE_REPORTED
    elif complete:
        smoke = SmokeStatus.NO_SMOKE_REPORTED
    else:
        smoke = SmokeStatus.INDETERMINATE
    return StatusResult(smoke, availability)
