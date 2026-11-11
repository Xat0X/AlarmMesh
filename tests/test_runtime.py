"""Verify passive local observations and config-entry subscription lifecycle."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN
from custom_components.alarmmesh.runtime import AlarmMeshRuntimeData
from custom_components.alarmmesh.status import (
    SmokeStatus,
    SourceAvailability,
    SourceStatus,
    StatusResult,
    evaluate_status,
)

SOURCE = "binary_sensor.hall"
OTHER = "binary_sensor.kitchen"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a saved entry with one selected source, without loading it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={CONF_SOURCE_ENTITY_IDS: [SOURCE]},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    ("state", "source_status", "smoke", "availability"),
    [
        (
            "on",
            SourceStatus.SMOKE_REPORTED,
            SmokeStatus.SMOKE_REPORTED,
            SourceAvailability.COMPLETE,
        ),
        (
            "off",
            SourceStatus.NO_SMOKE_REPORTED,
            SmokeStatus.NO_SMOKE_REPORTED,
            SourceAvailability.COMPLETE,
        ),
        (
            "unknown",
            SourceStatus.UNKNOWN,
            SmokeStatus.INDETERMINATE,
            SourceAvailability.INCOMPLETE,
        ),
        (
            "unavailable",
            SourceStatus.UNREACHABLE,
            SmokeStatus.INDETERMINATE,
            SourceAvailability.INCOMPLETE,
        ),
        (
            None,
            SourceStatus.MISSING,
            SmokeStatus.INDETERMINATE,
            SourceAvailability.INCOMPLETE,
        ),
        *[
            (
                state,
                SourceStatus.UNKNOWN,
                SmokeStatus.INDETERMINATE,
                SourceAvailability.INCOMPLETE,
            )
            for state in ("unexpected", "", "ON", "true", "1")
        ],
    ],
)
async def test_initial_states(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    state: str | None,
    source_status: SourceStatus,
    smoke: SmokeStatus,
    availability: SourceAvailability,
) -> None:
    """Every mapping, including already active smoke, is evaluated during setup."""
    if state is not None:
        hass.states.async_set(SOURCE, state)
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data
    assert isinstance(runtime, AlarmMeshRuntimeData)
    assert runtime.source_entity_ids == (SOURCE,)
    assert runtime.source_statuses == {SOURCE: source_status}
    assert runtime.result == StatusResult(smoke, availability)


async def test_multiple_sources(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Smoke still wins when a different selected detector is unreachable."""
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: [SOURCE, OTHER]}
    )
    hass.states.async_set(SOURCE, "on")
    hass.states.async_set(OTHER, "unavailable")
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.source_statuses == {
        SOURCE: SourceStatus.SMOKE_REPORTED,
        OTHER: SourceStatus.UNREACHABLE,
    }
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.SMOKE_REPORTED, SourceAvailability.INCOMPLETE
    )

    hass.states.async_set(SOURCE, "off")
    await hass.async_block_till_done()
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.INCOMPLETE
    )
    hass.states.async_set(OTHER, "off")
    await hass.async_block_till_done()
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.NO_SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("on", "off", SourceStatus.NO_SMOKE_REPORTED),
        ("off", "on", SourceStatus.SMOKE_REPORTED),
        ("unknown", "on", SourceStatus.SMOKE_REPORTED),
        ("unknown", "off", SourceStatus.NO_SMOKE_REPORTED),
        ("unavailable", "on", SourceStatus.SMOKE_REPORTED),
        ("unavailable", "off", SourceStatus.NO_SMOKE_REPORTED),
        ("off", "unknown", SourceStatus.UNKNOWN),
        ("off", "unavailable", SourceStatus.UNREACHABLE),
        ("off", "unexpected", SourceStatus.UNKNOWN),
    ],
)
async def test_state_changes(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    before: str,
    after: str,
    expected: SourceStatus,
) -> None:
    """Selected state changes update the same runtime and its evaluated result."""
    hass.states.async_set(SOURCE, before)
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data
    hass.states.async_set(SOURCE, after)
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert runtime.source_statuses == {SOURCE: expected}
    assert runtime.result == evaluate_status([expected])


async def test_remove_and_reappear(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """A removed source becomes missing and is still watched for reappearance."""
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.states.async_remove(SOURCE)
    await hass.async_block_till_done()
    assert entry.runtime_data.source_statuses == {SOURCE: SourceStatus.MISSING}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.INCOMPLETE
    )
    hass.states.async_set(SOURCE, "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.source_statuses == {SOURCE: SourceStatus.SMOKE_REPORTED}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


@pytest.mark.parametrize("options", [{}, {CONF_SOURCE_ENTITY_IDS: []}])
async def test_no_sources(
    hass: HomeAssistant, entry: MockConfigEntry, options: dict
) -> None:
    """Empty foundation options load without a state subscription."""
    hass.config_entries.async_update_entry(entry, options=options)
    with patch(
        "custom_components.alarmmesh.async_track_state_change_event",
        wraps=async_track_state_change_event,
    ) as track:
        assert await hass.config_entries.async_setup(entry.entry_id)
        track.assert_not_called()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.source_entity_ids == ()
    assert entry.runtime_data.source_statuses == {}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.INDETERMINATE, SourceAvailability.NOT_CONFIGURED
    )


async def test_missing_source_appears(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A configured source absent at startup is subscribed to immediately."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.source_statuses == {SOURCE: SourceStatus.MISSING}
    hass.states.async_set(SOURCE, "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.source_statuses == {SOURCE: SourceStatus.SMOKE_REPORTED}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


async def test_unselected_source_ignored(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Unselected changes and removals do not even invoke the calculation."""
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    original_result = entry.runtime_data.result
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(OTHER, "on")
        await hass.async_block_till_done()
        hass.states.async_remove(OTHER)
        await hass.async_block_till_done()
        calc.assert_not_called()
    assert entry.runtime_data.source_statuses == {
        SOURCE: SourceStatus.NO_SMOKE_REPORTED
    }
    assert entry.runtime_data.result is original_result


async def test_subscribe_before_snapshot(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A change while installing the listener cannot escape the initial snapshot."""
    hass.states.async_set(SOURCE, "off")

    def install(hass, entity_ids, action):
        # Change before the real subscription: there is no event to catch later.
        hass.states.async_set(SOURCE, "on")
        return async_track_state_change_event(hass, entity_ids, action)

    with patch(
        "custom_components.alarmmesh.async_track_state_change_event",
        side_effect=install,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.source_statuses == {SOURCE: SourceStatus.SMOKE_REPORTED}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


@pytest.mark.parametrize("operation", ["unload", "reload", "remove"])
async def test_subscription_cleanup(
    hass: HomeAssistant, entry: MockConfigEntry, operation: str
) -> None:
    """Old runtime stops receiving events after every supported unload path."""
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    if operation == "unload":
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
    elif operation == "reload":
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert entry.runtime_data is not old_runtime
    else:
        await hass.config_entries.async_remove(entry.entry_id)
        assert hass.config_entries.async_get_entry(entry.entry_id) is None
    await hass.async_block_till_done()
    if operation != "reload":
        assert not hasattr(entry, "runtime_data")

    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        if operation == "reload":
            calc.assert_called_once()
            assert (
                entry.runtime_data.source_statuses[SOURCE]
                is SourceStatus.SMOKE_REPORTED
            )
        else:
            calc.assert_not_called()
    assert old_runtime.source_statuses == {SOURCE: SourceStatus.NO_SMOKE_REPORTED}


async def test_repeated_reload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Repeated reloads retain one active processor and freeze old runtimes."""
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtimes = []
    for index in range(4):
        old_runtimes.append(
            (entry.runtime_data, entry.runtime_data.source_statuses.copy())
        )
        assert await hass.config_entries.async_reload(entry.entry_id)
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            hass.states.async_set(SOURCE, "on" if index % 2 == 0 else "off")
            await hass.async_block_till_done()
            calc.assert_called_once()
        for old_runtime, statuses in old_runtimes:
            assert old_runtime.source_statuses == statuses


async def test_setup_after_unload_reads_fresh_state(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A previous result is never restored over current local source states."""
    hass.states.async_set(SOURCE, "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_set(SOURCE, "off")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data is not old_runtime
    assert old_runtime.result.smoke_status is SmokeStatus.SMOKE_REPORTED
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.NO_SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


async def test_changed_options_reload(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Saving changed options swaps sources and takes a fresh initial snapshot."""
    hass.states.async_set(SOURCE, "off", {"device_class": "smoke"})
    hass.states.async_set(OTHER, "on", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    old_runtime = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [OTHER]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not old_runtime
    assert entry.runtime_data.source_entity_ids == (OTHER,)
    assert entry.runtime_data.source_statuses == {OTHER: SourceStatus.SMOKE_REPORTED}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.SMOKE_REPORTED, SourceAvailability.COMPLETE
    )

    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        calc.assert_not_called()
        hass.states.async_set(OTHER, "off")
        await hass.async_block_till_done()
        calc.assert_called_once()
    assert old_runtime.source_statuses == {SOURCE: SourceStatus.NO_SMOKE_REPORTED}
    assert entry.runtime_data.result == StatusResult(
        SmokeStatus.NO_SMOKE_REPORTED, SourceAvailability.COMPLETE
    )


@pytest.mark.parametrize("selection", [[SOURCE], []])
async def test_unchanged_or_invalid_options_keep_runtime(
    hass: HomeAssistant, entry: MockConfigEntry, selection: list[str]
) -> None:
    """Unchanged options and invalid edits followed by cancellation do not reload."""
    hass.states.async_set(SOURCE, "off", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: selection}
    )
    if not selection:
        assert result["type"] is FlowResultType.FORM
        hass.config_entries.options.async_abort(result["flow_id"])
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert entry.options == {CONF_SOURCE_ENTITY_IDS: [SOURCE]}


async def test_configuration_unchanged(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Status processing neither mutates nor saves configuration or observations."""
    original_data = deepcopy(dict(entry.data))
    original_options = deepcopy(dict(entry.options))
    assert await hass.config_entries.async_setup(entry.entry_id)
    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as update:
        for state in ("on", "off", "unknown", "unavailable", "unexpected"):
            hass.states.async_set(SOURCE, state)
            await hass.async_block_till_done()
        hass.states.async_remove(SOURCE)
        await hass.async_block_till_done()
        update.assert_not_called()
    assert entry.data == original_data
    assert entry.options == original_options


async def test_only_read_only_overviews(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Smoke adds only two overview entities without devices or alarm services."""
    hass.states.async_set(SOURCE, "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 2
    assert {entity.domain for entity in entities} == {"binary_sensor", "sensor"}
    assert all(entity.device_id is None for entity in entities)
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert DOMAIN not in hass.services.async_services()
    assert not hass.states.async_all(DOMAIN)
