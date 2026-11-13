"""Test-only fixture entry, never shipped in the AlarmMesh integration."""

from homeassistant.config_entries import ConfigFlow


class SimulationFlow(ConfigFlow, domain="alarmmesh_simulation"):
    VERSION = 1

    async def async_step_import(self, _data):
        await self.async_set_unique_id("alarmmesh-linking-simulation")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="SIMULATED providers only", data={})
