"""Select existing smoke detector entities without monitoring their reports."""

from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import ATTR_DEVICE_CLASS, Platform
from homeassistant.core import HomeAssistant, callback, split_entity_id, valid_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from . import matter, zwave
from .const import CONF_SOURCE_ENTITY_IDS, DOMAIN, NAME
from .runtime import is_alecto_source


def _source_schema(hass: HomeAssistant) -> vol.Schema:
    """Offer reviewed enum sources alongside the existing smoke binary sensors."""
    registry = er.async_get(hass)
    alecto_ids = [
        e.entity_id for e in registry.entities.values() if is_alecto_source(hass, e)
    ]
    config = selector.EntitySelectorConfig(multiple=True)
    if alecto_ids:
        binary_ids = set(hass.states.async_entity_ids(Platform.BINARY_SENSOR))
        binary_ids.update(
            e.entity_id
            for e in registry.entities.values()
            if e.domain == Platform.BINARY_SENSOR and not e.disabled_by
        )
        config["include_entities"] = sorted(
            alecto_ids
            + [
                entity_id
                for entity_id in binary_ids
                if not _validate_sources(hass, [entity_id])
            ]
        )
    else:
        config["filter"] = selector.EntityFilterSelectorConfig(
            domain=Platform.BINARY_SENSOR, device_class=BinarySensorDeviceClass.SMOKE
        )
    return vol.Schema(
        {vol.Required(CONF_SOURCE_ENTITY_IDS): selector.EntitySelector(config)}
    )


def _validate_sources(hass: HomeAssistant, sources: Any) -> str | None:
    """Validate selection shape, identity and ownership, never state values.

    A registry user override takes precedence over current state attributes,
    with original registry device class as fallback. A registry entry alone is
    enough to identify a temporarily absent entity. No source is queried.
    """
    if not isinstance(sources, list) or any(
        not isinstance(entity_id, str) or not valid_entity_id(entity_id)
        for entity_id in sources
    ):
        return "invalid_sources"
    if not sources:
        return "no_sources"
    if len(set(sources)) != len(sources):
        return "duplicate_sources"

    registry = er.async_get(hass)
    for entity_id in sources:
        registered = registry.async_get(entity_id)
        if split_entity_id(entity_id)[0] != Platform.BINARY_SENSOR:
            if is_alecto_source(hass, registered):
                continue
            return "wrong_domain"
        if (
            registered
            and registered.platform == "matter"
            and (
                matter.is_contract(registered, "co")
                or matter.is_contract(registered, "interconnect_co")
            )
        ):
            return "wrong_device_class"
        if zwave.invalid_source(hass, entity_id):
            return "wrong_device_class"
        state = hass.states.get(entity_id)
        if registered is None and state is None:
            return "unknown_entity"
        if registered is not None:
            owner = (
                hass.config_entries.async_get_entry(registered.config_entry_id)
                if registered.config_entry_id
                else None
            )
            if registered.platform == DOMAIN or (owner and owner.domain == DOMAIN):
                return "own_source"

        device_class = registered.device_class if registered is not None else None
        if device_class is None and state is not None:
            device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        if device_class is None and registered is not None:
            device_class = registered.original_device_class
        if device_class != BinarySensorDeviceClass.SMOKE:
            return "wrong_device_class"
    return None


class AlarmMeshConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one configuration with source selection stored only in options."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AlarmMeshOptionsFlow:
        """Return an options flow; Home Assistant supplies its config entry."""
        return AlarmMeshOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require at least one valid smoke detector before creating the entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            sources = user_input.get(CONF_SOURCE_ENTITY_IDS, [])
            if error := _validate_sources(self.hass, sources):
                errors[CONF_SOURCE_ENTITY_IDS] = error
            else:
                return self.async_create_entry(
                    title=NAME,
                    data={},
                    options={CONF_SOURCE_ENTITY_IDS: list(sources)},
                )

        return self.async_show_form(
            step_id="user", data_schema=_source_schema(self.hass), errors=errors
        )


class AlarmMeshOptionsFlow(OptionsFlowWithReload):
    """Save validated sources and let Home Assistant reload changed options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show existing sources, including an empty foundation configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            sources = user_input.get(CONF_SOURCE_ENTITY_IDS, [])
            if error := _validate_sources(self.hass, sources):
                errors[CONF_SOURCE_ENTITY_IDS] = error
            else:
                return self.async_create_entry(
                    title="", data={CONF_SOURCE_ENTITY_IDS: list(sources)}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _source_schema(self.hass),
                {
                    CONF_SOURCE_ENTITY_IDS: self.config_entry.options.get(
                        CONF_SOURCE_ENTITY_IDS, []
                    )
                },
            ),
            errors=errors,
        )
