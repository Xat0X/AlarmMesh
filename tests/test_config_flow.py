"""Exercise source selection, validation and singleton behavior in Home Assistant."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN, NAME


@pytest.fixture
async def smoke_sources(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> list[str]:
    """Provide two simulated, registered smoke binary sensors."""
    sources = []
    for name in ("hall", "kitchen"):
        entity = entity_registry.async_get_or_create(
            "binary_sensor",
            "test",
            name,
            suggested_object_id=name,
            original_device_class="smoke",
        )
        hass.states.async_set(entity.entity_id, "off", {"device_class": "smoke"})
        sources.append(entity.entity_id)
    return sources


@pytest.mark.parametrize("count", [1, 2])
async def test_user_confirmation(
    hass: HomeAssistant, smoke_sources: list[str], count: int
) -> None:
    """Opening creates nothing; valid sources are stored only in options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not hass.config_entries.async_entries(DOMAIN)

    entity_selector = next(iter(result["data_schema"].schema.values()))
    assert entity_selector.config["multiple"] is True
    assert entity_selector.config["filter"] == [
        {"domain": ["binary_sensor"], "device_class": ["smoke"]}
    ]

    selection = smoke_sources[:count]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: selection}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {}
    assert result["result"].options == {CONF_SOURCE_ENTITY_IDS: selection}
    assert result["result"].version == 1
    assert result["result"].unique_id == DOMAIN
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    "options", [{}, {CONF_SOURCE_ENTITY_IDS: ["binary_sensor.hall"]}]
)
async def test_already_configured(hass: HomeAssistant, options: dict[str, Any]) -> None:
    """A persisted entry prevents a duplicate even when it is not loaded."""
    MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={}, options=options
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_parallel_flows(hass: HomeAssistant, smoke_sources: list[str]) -> None:
    """Two open dialogs cannot create two foundation entries."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert first["type"] is FlowResultType.FORM
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"

    result = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_SOURCE_ENTITY_IDS: smoke_sources}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize("flow_kind", ["config", "options"])
@pytest.mark.parametrize(
    ("selection", "error"),
    [
        ([], "no_sources"),
        (None, "invalid_sources"),
        ("binary_sensor.hall", "invalid_sources"),
        (42, "invalid_sources"),
        ([None], "invalid_sources"),
        ([42], "invalid_sources"),
        ([{}], "invalid_sources"),
        (["not an entity id"], "invalid_sources"),
        (["binary_sensor."], "invalid_sources"),
        (["00000000000000000000000000000000"], "invalid_entity_id"),
        (["binary_sensor.hall", "binary_sensor.hall"], "duplicate_sources"),
        (["binary_sensor.missing"], "unknown_entity"),
        (["binary_sensor.hall", "binary_sensor.missing"], "unknown_entity"),
        (["sensor.smoke"], "wrong_domain"),
        (["binary_sensor.motion"], "wrong_device_class"),
        (["binary_sensor.no_class"], "wrong_device_class"),
        (["binary_sensor.own"], "own_source"),
    ],
)
async def test_invalid_selection(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    smoke_sources: list[str],
    flow_kind: str,
    selection: Any,
    error: str,
) -> None:
    """Both backends reject invalid input without replacing saved sources."""
    hass.states.async_set("sensor.smoke", "off", {"device_class": "smoke"})
    hass.states.async_set("binary_sensor.motion", "off", {"device_class": "motion"})
    hass.states.async_set("binary_sensor.no_class", "off")
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "own",
        suggested_object_id="own",
        original_device_class="smoke",
    )
    entry = None
    if flow_kind == "options":
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={},
            options={CONF_SOURCE_ENTITY_IDS: smoke_sources},
        )
        entry.add_to_hass(hass)
        manager = hass.config_entries.options
        result = await manager.async_init(entry.entry_id)
    else:
        manager = hass.config_entries.flow
        result = await manager.async_init(DOMAIN, context={"source": SOURCE_USER})

    if error == "invalid_sources":
        # Home Assistant rejects malformed selector input before calling the step.
        with pytest.raises(InvalidData):
            await manager.async_configure(
                result["flow_id"], {CONF_SOURCE_ENTITY_IDS: selection}
            )
    else:
        result = await manager.async_configure(
            result["flow_id"], {CONF_SOURCE_ENTITY_IDS: selection}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {
            CONF_SOURCE_ENTITY_IDS: (
                "invalid_sources" if error == "invalid_entity_id" else error
            )
        }
    if entry:
        assert entry.data == {}
        assert entry.options == {CONF_SOURCE_ENTITY_IDS: smoke_sources}
    else:
        assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("flow_kind", ["config", "options"])
async def test_missing_selection(hass: HomeAssistant, flow_kind: str) -> None:
    """Missing input cannot create a new entry or alter an old empty entry."""
    if flow_kind == "options":
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)
        manager = hass.config_entries.options
        result = await manager.async_init(entry.entry_id)
    else:
        manager = hass.config_entries.flow
        result = await manager.async_init(DOMAIN, context={"source": SOURCE_USER})
    with pytest.raises(InvalidData):
        await manager.async_configure(result["flow_id"], {})
    if flow_kind == "options":
        assert entry.options == {}


@pytest.mark.parametrize("flow_kind", ["config", "options"])
@pytest.mark.parametrize(
    ("state_value", "metadata"),
    [
        ("unknown", "state"),
        ("unavailable", "state"),
        ("unknown", "registry"),
        ("unavailable", "registry"),
        (None, "registry"),
        ("unknown", "override"),
        ("unavailable", "override"),
    ],
)
async def test_temporarily_unusable_source(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    flow_kind: str,
    state_value: str | None,
    metadata: str,
) -> None:
    """Identity metadata allows selection without interpreting source state."""
    entity_id = "binary_sensor.temporary"
    if metadata != "state":
        entity = entity_registry.async_get_or_create(
            "binary_sensor",
            "test",
            "temporary",
            suggested_object_id="temporary",
            original_device_class="motion" if metadata == "override" else "smoke",
        )
        if metadata == "override":
            entity_registry.async_update_entity(entity.entity_id, device_class="smoke")
    if state_value is not None:
        hass.states.async_set(
            entity_id,
            state_value,
            {"device_class": "smoke"} if metadata == "state" else {},
        )
    selection = {CONF_SOURCE_ENTITY_IDS: [entity_id]}
    if flow_kind == "options":
        entry = MockConfigEntry(domain=DOMAIN, data={}, options=selection)
        entry.add_to_hass(hass)
        manager = hass.config_entries.options
        result = await manager.async_init(entry.entry_id)
        marker = next(iter(result["data_schema"].schema))
        assert marker.description["suggested_value"] == [entity_id]
    else:
        manager = hass.config_entries.flow
        result = await manager.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await manager.async_configure(result["flow_id"], selection)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    if flow_kind == "options":
        assert entry.options == selection
    else:
        assert result["result"].options == selection


@pytest.mark.parametrize("initial_sources", [[], ["binary_sensor.hall"]])
@pytest.mark.parametrize("count", [1, 2])
async def test_options_replace_sources(
    hass: HomeAssistant,
    smoke_sources: list[str],
    initial_sources: list[str],
    count: int,
) -> None:
    """Empty foundation entries and populated entries can save a new selection."""
    original_options = (
        {CONF_SOURCE_ENTITY_IDS: initial_sources} if initial_sources else {}
    )
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, version=1, data={}, options=original_options
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    marker = next(iter(result["data_schema"].schema))
    assert marker.description["suggested_value"] == initial_sources
    assert entry.options == original_options

    selection = list(reversed(smoke_sources))[:count]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: selection}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SOURCE_ENTITY_IDS: selection}
    assert entry.data == {}
    assert entry.version == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    reopened = await hass.config_entries.options.async_init(entry.entry_id)
    marker = next(iter(reopened["data_schema"].schema))
    assert marker.description["suggested_value"] == selection
    hass.config_entries.options.async_abort(reopened["flow_id"])


async def test_cancel_options(hass: HomeAssistant, smoke_sources: list[str]) -> None:
    """An invalid edit followed by cancellation keeps the saved selection."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_SOURCE_ENTITY_IDS: smoke_sources}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: []}
    )
    assert result["type"] is FlowResultType.FORM
    marker = next(iter(result["data_schema"].schema))
    assert marker.description["suggested_value"] == smoke_sources
    hass.config_entries.options.async_abort(result["flow_id"])
    assert entry.data == {}
    assert entry.options == {CONF_SOURCE_ENTITY_IDS: smoke_sources}


@pytest.mark.parametrize("metadata", ["state", "registry", "override"])
async def test_explicit_non_smoke_metadata(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, metadata: str
) -> None:
    """Non-smoke metadata is not masked by a fallback or an unavailable state."""
    entity = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "conflicting",
        original_device_class="motion" if metadata == "registry" else "smoke",
    )
    if metadata == "override":
        entity_registry.async_update_entity(entity.entity_id, device_class="motion")
    hass.states.async_set(
        entity.entity_id,
        "unavailable",
        {"device_class": "motion"}
        if metadata == "state"
        else {"device_class": "smoke"}
        if metadata == "override"
        else {},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [entity.entity_id]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITY_IDS: "wrong_device_class"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_options_source_removed_while_editing(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, smoke_sources: list[str]
) -> None:
    """Submit-time validation catches disappeared sources without data loss."""
    original = {CONF_SOURCE_ENTITY_IDS: [smoke_sources[0]]}
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=original)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    entity_registry.async_remove(smoke_sources[1])
    hass.states.async_remove(smoke_sources[1])
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [smoke_sources[1]]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITY_IDS: "unknown_entity"}
    assert entry.options == original
    assert entry.data == {}

    # Correcting the invalid edit can still save through the same options flow.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], original
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == original


async def test_cancel_config(hass: HomeAssistant) -> None:
    """Closing setup creates no entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_source_owned_by_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, smoke_sources: list[str]
) -> None:
    """Ownership also excludes entities with a different registry platform."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_SOURCE_ENTITY_IDS: smoke_sources}
    )
    entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "owned",
        config_entry=entry,
        original_device_class="smoke",
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [entity.entity_id]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITY_IDS: "own_source"}
    assert entry.options == {CONF_SOURCE_ENTITY_IDS: smoke_sources}
