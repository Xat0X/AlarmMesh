"""Verify overview platform lifecycle without devices or alarm actions."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.alarmmesh.const import DOMAIN


async def test_setup_unload_reload(hass: HomeAssistant) -> None:
    """Foundation entries expose two overviews but no devices or services."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 2
    assert {entity.domain for entity in entities} == {"binary_sensor", "sensor"}
    assert all(entity.device_id is None for entity in entities)
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert DOMAIN not in hass.services.async_services()
    assert not hass.states.async_all(DOMAIN)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert all(
        hass.states.get(entity.entity_id).state == "unavailable" for entity in entities
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_remove(entry.entry_id)
    assert not hass.config_entries.async_entries(DOMAIN)
