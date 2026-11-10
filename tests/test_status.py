"""Test only the pure status calculation, without Home Assistant entities."""

from dataclasses import FrozenInstanceError
from itertools import combinations_with_replacement, permutations

import pytest

from custom_components.alarmmesh.status import (
    SmokeStatus,
    SourceAvailability,
    SourceStatus,
    StatusResult,
    evaluate_status,
)

UNUSABLE = (SourceStatus.UNKNOWN, SourceStatus.UNREACHABLE, SourceStatus.MISSING)


def test_no_sources() -> None:
    """An empty collection is indeterminate and not configured."""
    assert evaluate_status([]) == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.NOT_CONFIGURED
    )


@pytest.mark.parametrize(
    ("source", "smoke", "availability"),
    [
        (
            SourceStatus.SMOKE_REPORTED,
            SmokeStatus.SMOKE_REPORTED,
            SourceAvailability.COMPLETE,
        ),
        (
            SourceStatus.NO_SMOKE_REPORTED,
            SmokeStatus.NO_SMOKE_REPORTED,
            SourceAvailability.COMPLETE,
        ),
        *[
            (source, SmokeStatus.INDETERMINATE, SourceAvailability.INCOMPLETE)
            for source in UNUSABLE
        ],
    ],
)
def test_single_source(
    source: SourceStatus, smoke: SmokeStatus, availability: SourceAvailability
) -> None:
    """Every individual source has an explicit interpretation."""
    assert evaluate_status([source]) == StatusResult(smoke, availability)


def test_all_no_smoke() -> None:
    """Only explicit no-smoke reports establish a combined no-smoke report."""
    assert evaluate_status([SourceStatus.NO_SMOKE_REPORTED] * 4) == StatusResult(
        SmokeStatus.NO_SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


@pytest.mark.parametrize("other", list(SourceStatus))
def test_smoke_with_every_source(other: SourceStatus) -> None:
    """Smoke takes precedence while availability remains independent."""
    availability = (
        SourceAvailability.INCOMPLETE
        if other in UNUSABLE
        else SourceAvailability.COMPLETE
    )
    assert evaluate_status([SourceStatus.SMOKE_REPORTED, other]) == StatusResult(
        SmokeStatus.SMOKE_REPORTED, availability
    )


@pytest.mark.parametrize("other", UNUSABLE)
def test_no_smoke_with_unusable_source(other: SourceStatus) -> None:
    """An unusable report prevents a combined no-smoke report."""
    assert evaluate_status([SourceStatus.NO_SMOKE_REPORTED, other]) == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.INCOMPLETE
    )


@pytest.mark.parametrize(
    "sources",
    [
        sources
        for count in (2, 3)
        for sources in combinations_with_replacement(UNUSABLE, count)
    ],
)
def test_only_unusable_sources(sources: tuple[SourceStatus, ...]) -> None:
    """Combinations of unusable reports remain indeterminate and incomplete."""
    assert evaluate_status(sources) == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.INCOMPLETE
    )


@pytest.mark.parametrize(
    "sources", list(combinations_with_replacement(SourceStatus, 3))
)
def test_order_and_repetition(sources: tuple[SourceStatus, ...]) -> None:
    """Reordering or repeating reports cannot change either outcome."""
    expected = evaluate_status(sources)
    for ordered in permutations(sources):
        assert evaluate_status(ordered) == expected
        assert evaluate_status(ordered * 2) == expected
    assert evaluate_status(set(sources)) == expected


@pytest.mark.parametrize("invalid", [None, True, 0, "unknown", "no_smoke_reported"])
def test_invalid_members(invalid: object) -> None:
    """Invalid members raise even when another source reports smoke."""
    for sources in (
        [invalid],
        [SourceStatus.NO_SMOKE_REPORTED, invalid],
        [SourceStatus.SMOKE_REPORTED, invalid],
        [invalid, SourceStatus.SMOKE_REPORTED],
    ):
        with pytest.raises(TypeError, match="every source must be a SourceStatus"):
            evaluate_status(sources)


@pytest.mark.parametrize("invalid", [None, True, 42, "", "no_smoke_reported", b""])
def test_invalid_collection(invalid: object) -> None:
    """Non-collections and strings are rejected, including empty strings."""
    with pytest.raises(TypeError, match="sources must be a collection"):
        evaluate_status(invalid)


def test_input_unchanged() -> None:
    """The caller's list retains its order, members and repetitions."""
    sources = [*SourceStatus, SourceStatus.NO_SMOKE_REPORTED]
    before = sources.copy()
    evaluate_status(sources)
    assert sources == before


def test_result_immutable() -> None:
    """The returned interpretation cannot be reassigned accidentally."""
    result = evaluate_status([])
    with pytest.raises(FrozenInstanceError):
        result.smoke_status = SmokeStatus.NO_SMOKE_REPORTED
