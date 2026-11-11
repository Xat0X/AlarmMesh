"""Exercise both read-only overview platforms through Home Assistant fixtures."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.translation import async_get_translations

from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN
from custom_components.alarmmesh.status import (
    SmokeStatus,
    SourceAvailability,
    StatusResult,
    evaluate_status,
)

SOURCE = "binary_sensor.hall"
OTHER = "binary_sensor.kitchen"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a persisted source selection, without loading it yet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={CONF_SOURCE_ENTITY_IDS: [SOURCE]},
    )
    entry.add_to_hass(hass)
    return entry


def overview_ids(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, str]:
    """Find HA-generated entity IDs by the stable config-entry-based unique IDs."""
    registry = er.async_get(hass)
    smoke = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_smoke"
    )
    availability = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_source_availability"
    )
    assert smoke is not None
    assert availability is not None
    return smoke, availability


def assert_overviews(
    hass: HomeAssistant, entry: MockConfigEntry, smoke: str, availability: str
) -> None:
    """Assert state-machine output, including the enum's standard metadata."""
    smoke_id, availability_id = overview_ids(hass, entry)
    smoke_state = hass.states.get(smoke_id)
    availability_state = hass.states.get(availability_id)
    assert smoke_state is not None
    assert availability_state is not None
    assert smoke_state.state == smoke
    assert smoke_state.attributes["device_class"] == "smoke"
    assert availability_state.state == availability
    assert availability_state.attributes["device_class"] == "enum"
    assert availability_state.attributes["options"] == [
        "complete",
        "incomplete",
        "not_configured",
    ]
    assert set(smoke_state.attributes) <= {"device_class", "friendly_name"}
    assert set(availability_state.attributes) <= {
        "device_class",
        "friendly_name",
        "options",
    }


@pytest.mark.parametrize(
    ("source_states", "smoke", "availability"),
    [
        (["on"], "on", "complete"),
        (["off"], "off", "complete"),
        (["unknown"], "unavailable", "incomplete"),
        (["unavailable"], "unavailable", "incomplete"),
        ([None], "unavailable", "incomplete"),
        (["unexpected"], "unavailable", "incomplete"),
        (["on", "unavailable"], "on", "incomplete"),
        (["on", None], "on", "incomplete"),
        (["off", "off"], "off", "complete"),
        (["off", "unknown"], "unavailable", "incomplete"),
        ([], "unavailable", "not_configured"),
    ],
)
async def test_initial_overviews(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    source_states: list[str | None],
    smoke: str,
    availability: str,
) -> None:
    """Both overviews immediately reflect the shared initial runtime result."""
    sources = [SOURCE, OTHER][: len(source_states)]
    hass.config_entries.async_update_entry(
        entry, options={CONF_SOURCE_ENTITY_IDS: sources}
    )
    for entity_id, state in zip(sources, source_states, strict=True):
        if state is not None:
            hass.states.async_set(entity_id, state)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert_overviews(hass, entry, smoke, availability)


async def test_empty_foundation(hass: HomeAssistant) -> None:
    """An entry predating source options exposes honest empty-selection states."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert_overviews(hass, entry, "unavailable", "not_configured")
    assert entry.data == {}
    assert entry.options == {}


async def test_updates_and_reappearance(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Source changes, removal and reappearance update both views without polling."""
    hass.states.async_set(SOURCE, "on")
    assert await hass.config_entries.async_setup(entry.entry_id)
    for state, smoke, availability in (
        ("off", "off", "complete"),
        ("unknown", "unavailable", "incomplete"),
        ("on", "on", "complete"),
        ("unavailable", "unavailable", "incomplete"),
        ("off", "off", "complete"),
        ("unexpected", "unavailable", "incomplete"),
    ):
        with patch(
            "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
        ) as calc:
            hass.states.async_set(SOURCE, state)
            await hass.async_block_till_done()
            calc.assert_called_once()
        assert_overviews(hass, entry, smoke, availability)
    hass.states.async_remove(SOURCE)
    await hass.async_block_till_done()
    assert_overviews(hass, entry, "unavailable", "incomplete")
    hass.states.async_set(SOURCE, "on")
    await hass.async_block_till_done()
    assert_overviews(hass, entry, "on", "complete")


async def test_options_and_custom_identity(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Selection changes and repeated loads retain user names, IDs and registry IDs."""
    hass.states.async_set(SOURCE, "off", {"device_class": "smoke"})
    hass.states.async_set(OTHER, "on", {"device_class": "smoke"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    originals = []
    for entity_id in overview_ids(hass, entry):
        domain = entity_id.split(".")[0]
        updated = entity_registry.async_update_entity(
            entity_id,
            new_entity_id=f"{domain}.my_alarmmesh_overview",
            name=f"My {domain} overview",
        )
        originals.append(updated)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [OTHER]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert_overviews(hass, entry, "on", "complete")
    hass.states.async_set(SOURCE, "on")
    hass.states.async_set(OTHER, "off")
    await hass.async_block_till_done()
    assert_overviews(hass, entry, "off", "complete")

    for _ in range(3):
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert_overviews(hass, entry, "off", "complete")
    for original in originals:
        current = entity_registry.async_get(original.entity_id)
        assert current is not None
        assert current.unique_id == original.unique_id
        assert current.id == original.id
        assert current.name == original.name
        assert (
            hass.states.get(current.entity_id).attributes["friendly_name"]
            == original.name
        )
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2


@pytest.mark.parametrize("operation", ["unload", "remove", "reload"])
async def test_entity_subscription_cleanup(
    hass: HomeAssistant, entry: MockConfigEntry, operation: str
) -> None:
    """Removed entities unsubscribe even when old runtime is still referenced."""
    hass.states.async_set(SOURCE, "off")
    with patch(
        "custom_components.alarmmesh.entity.AlarmMeshEntity.async_write_ha_state",
        autospec=True,
        side_effect=Entity.async_write_ha_state,
    ) as write:
        assert await hass.config_entries.async_setup(entry.entry_id)
        old_runtime = entry.runtime_data
        if operation == "unload":
            assert await hass.config_entries.async_unload(entry.entry_id)
        elif operation == "remove":
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        write.reset_mock()
        old_runtime.async_set_result(
            StatusResult(SmokeStatus.SMOKE_REPORTED, SourceAvailability.COMPLETE)
        )
        write.assert_not_called()
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        assert write.call_count == (2 if operation == "reload" else 0)
    if operation == "reload":
        assert_overviews(hass, entry, "on", "complete")


async def test_repeated_reload_has_one_subscription_per_entity(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Each changed result writes exactly once to each overview after every reload."""
    hass.states.async_set(SOURCE, "off")
    with patch(
        "custom_components.alarmmesh.entity.AlarmMeshEntity.async_write_ha_state",
        autospec=True,
        side_effect=Entity.async_write_ha_state,
    ) as write:
        assert await hass.config_entries.async_setup(entry.entry_id)
        for index in range(4):
            assert await hass.config_entries.async_reload(entry.entry_id)
            write.reset_mock()
            hass.states.async_set(SOURCE, "on" if index % 2 == 0 else "off")
            await hass.async_block_till_done()
            assert write.call_count == 2
            assert {call.args[0].entity_id for call in write.call_args_list} == set(
                overview_ids(hass, entry)
            )


@pytest.mark.parametrize("platform", ["binary_sensor", "sensor"])
async def test_platform_setup_failure_cleans_subscriptions(
    hass: HomeAssistant, entry: MockConfigEntry, platform: str
) -> None:
    """A real platform error swallowed by HA still rolls back the whole setup."""
    hass.states.async_set(SOURCE, "off")
    with patch(
        f"custom_components.alarmmesh.{platform}.async_setup_entry",
        side_effect=RuntimeError("Simulated platform failure"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    old_runtime = entry.runtime_data
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        calc.assert_not_called()
    assert not old_runtime._listeners
    registry = er.async_get(hass)
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        assert hass.states.get(registered.entity_id).state == "unavailable"
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert_overviews(hass, entry, "on", "complete")


async def test_forwarding_exception_cleans_sources(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Import/forwarding exceptions also stop sources before setup returns failure."""
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("Simulated forwarding failure"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    with patch(
        "custom_components.alarmmesh.evaluate_status", wraps=evaluate_status
    ) as calc:
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        calc.assert_not_called()
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert_overviews(hass, entry, "on", "complete")


@pytest.mark.parametrize("disabled_domain", ["binary_sensor", "sensor"])
async def test_disabling_one_overview_keeps_other_live(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    disabled_domain: str,
) -> None:
    """Disabling one overview removes its subscription without stopping sources."""
    hass.states.async_set(SOURCE, "off")
    with patch(
        "custom_components.alarmmesh.entity.AlarmMeshEntity.async_write_ha_state",
        autospec=True,
        side_effect=Entity.async_write_ha_state,
    ) as write:
        assert await hass.config_entries.async_setup(entry.entry_id)
        ids = overview_ids(hass, entry)
        disabled = next(
            entity_id for entity_id in ids if entity_id.split(".")[0] == disabled_domain
        )
        enabled = next(entity_id for entity_id in ids if entity_id != disabled)
        entity_registry.async_update_entity(
            disabled, disabled_by=er.RegistryEntryDisabler.USER
        )
        await hass.async_block_till_done()
        write.reset_mock()
        hass.states.async_set(SOURCE, "on")
        await hass.async_block_till_done()
        write.assert_called_once()
        assert write.call_args.args[0].entity_id == enabled
        assert hass.states.get(enabled).state == (
            "complete" if disabled_domain == "binary_sensor" else "on"
        )
        assert await hass.config_entries.async_reload(entry.entry_id)
        write.reset_mock()
        hass.states.async_set(SOURCE, "unavailable")
        await hass.async_block_till_done()
        write.assert_called_once()
        assert write.call_args.args[0].entity_id == enabled
        assert hass.states.get(enabled).state == (
            "incomplete" if disabled_domain == "binary_sensor" else "unavailable"
        )


async def test_cached_overview_is_not_restored(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """A saved smoke result never overrides a current explicit no-smoke report."""
    registered = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{entry.entry_id}_smoke",
        config_entry=entry,
    )
    mock_restore_cache(hass, [State(registered.entity_id, "on")])
    hass.states.async_set(SOURCE, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert_overviews(hass, entry, "off", "complete")


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_entity_translations(hass: HomeAssistant, language: str) -> None:
    """Names and all enum labels are available through HA's translation API."""
    translations = await async_get_translations(hass, language, "entity", {DOMAIN})
    prefix = f"component.{DOMAIN}.entity"
    assert translations[f"{prefix}.binary_sensor.smoke.name"] == (
        "AlarmMesh smoke report" if language == "en" else "AlarmMesh rookmelding"
    )
    assert translations[f"{prefix}.sensor.source_availability.name"] == (
        "AlarmMesh source availability"
        if language == "en"
        else "AlarmMesh bronbeschikbaarheid"
    )
    for state in ("complete", "incomplete", "not_configured"):
        assert translations[f"{prefix}.sensor.source_availability.state.{state}"]
