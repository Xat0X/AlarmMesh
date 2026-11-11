"""Technical load check in a separate throwaway container, never UI acceptance.

The caller mounts a fresh directory below config/mvp-acceptance/technical-checks
at /config and the repository integration read-only below /config/custom_components.
No owner account, password or token is created or inspected.
"""

import asyncio
import json
import sys
from pathlib import Path

from homeassistant import bootstrap
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import __version__
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.runner import RuntimeConfig


async def main() -> None:
    """Boot the example config and exercise setup/unload without a web login."""
    assert __version__ == "2026.10.4", __version__
    # Match the HA CLI's config-directory import path for custom integrations.
    sys.path.insert(0, "/config")
    hass = await bootstrap.async_setup_hass(
        RuntimeConfig(config_dir="/config", skip_pip=True, log_no_color=True)
    )
    assert hass is not None
    try:
        from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN

        assert not hass.config.recovery_mode
        await hass.async_start()
        await hass.async_block_till_done()
        sources = ["binary_sensor.mvp_smoke_a", "binary_sensor.mvp_smoke_b"]
        for entity_id in sources:
            state = hass.states.get(entity_id)
            assert state is not None and state.state == "off", entity_id
            assert state.attributes["device_class"] == "smoke"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOURCE_ENTITY_IDS: sources}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.result.smoke_status.value == "no_smoke_reported"
        assert entry.runtime_data.result.source_availability.value == "complete"
        assert await hass.config_entries.async_unload(entry.entry_id)
        report = {
            "kind": "technical_bootstrap_only_not_ui_acceptance",
            "home_assistant": __version__,
            "sources": sources,
            "alarmmesh_setup": "PASS",
            "alarmmesh_unload": "PASS",
            "owner_account_created": False,
        }
        await asyncio.to_thread(
            Path("/config/technical-result.json").write_text,
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report))
    finally:
        await hass.async_stop(force=True)


if __name__ == "__main__":
    asyncio.run(main())
