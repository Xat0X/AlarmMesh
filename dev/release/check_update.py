"""Persistent HA-process update/recovery checks, exclusively simulated sources."""

import argparse
import asyncio
import hashlib
import json
import sys
import traceback
from pathlib import Path

from homeassistant import bootstrap
from homeassistant.components.brands import BrandsIntegrationView
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import __version__
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.runner import RuntimeConfig

SOURCES = ["binary_sensor.mvp_smoke_a", "binary_sensor.mvp_smoke_b"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def run(phase: str, requested: str) -> int:
    root = Path("/evidence")
    report = {
        "phase": phase,
        "requested_ha_version": requested,
        "actual_ha_version": __version__,
        "result": "FAIL",
        "checks": [],
        "scope": (
            "simulated file replacement and stopped-file snapshot recovery; "
            "not installer or HA backup acceptance"
        ),
    }
    hass = None
    try:
        require(__version__ == requested, "HA version mismatch")
        sys.path.insert(0, "/config")
        hass = await bootstrap.async_setup_hass(
            RuntimeConfig(config_dir="/config", skip_pip=True, log_no_color=True)
        )
        require(
            hass is not None and not hass.config.recovery_mode, "HA bootstrap failed"
        )
        await hass.async_start()
        await hass.async_block_till_done()
        from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN

        registry = er.async_get(hass)

        async def helper(name: str, on: bool) -> None:
            await hass.services.async_call(
                "input_boolean",
                "turn_on" if on else "turn_off",
                {"entity_id": f"input_boolean.{name}"},
                blocking=True,
            )
            await hass.async_block_till_done()

        def identity(entry) -> list[dict]:
            entities = er.async_entries_for_config_entry(registry, entry.entry_id)
            require(len(entities) == 2, "Expected exactly two overviews")
            require(
                all(entity.device_id is None for entity in entities),
                "Unexpected device",
            )
            return sorted(
                [
                    {
                        "registry_id": e.id,
                        "unique_id": e.unique_id,
                        "entity_id": e.entity_id,
                        "name": e.name,
                    }
                    for e in entities
                ],
                key=lambda item: item["entity_id"],
            )

        def expect(entry, smoke: str, availability: str) -> None:
            ids = identity(entry)
            for item in ids:
                expected = (
                    smoke
                    if item["entity_id"].startswith("binary_sensor.")
                    else availability
                )
                state = hass.states.get(item["entity_id"])
                require(
                    state is not None and state.state == expected,
                    "Unexpected current overview state",
                )

        async def create():
            flow = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                flow["flow_id"], {CONF_SOURCE_ENTITY_IDS: SOURCES}
            )
            require(result["type"] is FlowResultType.CREATE_ENTRY, "Config flow failed")
            await hass.async_block_till_done()
            entry = result["result"]
            require(entry.state is ConfigEntryState.LOADED, "AlarmMesh setup failed")
            return entry

        if phase == "seed":
            require(
                not hass.config_entries.async_entries(DOMAIN),
                "Seed configuration already has AlarmMesh",
            )
            entry = await create()
            expect(entry, "off", "complete")
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
                smoke = entity.domain == "binary_sensor"
                registry.async_update_entity(
                    entity.entity_id,
                    new_entity_id="binary_sensor.alarmmesh_update_smoke"
                    if smoke
                    else "sensor.alarmmesh_update_sources",
                    name="SIMULATION customized smoke"
                    if smoke
                    else "SIMULATION customized sources",
                )
            await helper("mvp_a_smoke", True)
            await helper("mvp_b_unreachable", True)
            expect(entry, "on", "incomplete")
            checkpoint = {
                "entry_id": entry.entry_id,
                "options": dict(entry.options),
                "data": dict(entry.data),
                "identity": identity(entry),
                "smoke": "on",
                "availability": "incomplete",
            }
            (root / "checkpoint.json").write_text(
                json.dumps(checkpoint, indent=2), encoding="utf-8"
            )
            report["checks"].append("seed_selection_custom_identity_and_on_incomplete")
        else:
            checkpoint = json.loads((root / "checkpoint.json").read_text("utf-8"))
            entries = hass.config_entries.async_entries(DOMAIN)
            require(len(entries) == 1, "Saved configuration missing or duplicated")
            entry = entries[0]
            require(entry.state is ConfigEntryState.LOADED, "Saved entry did not load")
            require(entry.entry_id == checkpoint["entry_id"], "Entry identity changed")
            require(
                dict(entry.options) == checkpoint["options"]
                and dict(entry.data) == checkpoint["data"],
                "Saved selection/data changed",
            )
            require(
                identity(entry) == checkpoint["identity"],
                "Custom names or entity identity changed",
            )
            expect(entry, checkpoint["smoke"], checkpoint["availability"])
            report["checks"].append(
                "saved_selection_identity_and_actual_helper_states_after_new_process"
            )
            await helper("mvp_a_smoke", False)
            expect(entry, "unavailable", "incomplete")
            await helper("mvp_b_unreachable", False)
            expect(entry, "off", "complete")
            report["checks"].append(
                "current_source_changes_not_cached_alarmmesh_outcome"
            )

        # Exercise the HA local-brand loader, without an account, token, CDN or UI.
        # Authenticated HTTP serving is covered separately by the existing fixture.
        view = BrandsIntegrationView(hass)
        for filename in (
            "icon.png",
            "icon@2x.png",
            "logo.png",
            "logo@2x.png",
            "dark_logo.png",
            "dark_logo@2x.png",
        ):
            response = await view._serve_from_custom_integration(DOMAIN, filename)
            require(
                response is not None and response.status == 200,
                "Local branding not loaded",
            )
            expected = await asyncio.to_thread(
                (
                    Path("/config/custom_components/alarmmesh/brand") / filename
                ).read_bytes
            )
            require(
                hashlib.sha256(response.body).digest()
                == hashlib.sha256(expected).digest(),
                "Brand placeholder or wrong file",
            )
        report["checks"].append(
            "ha_brand_loader_reads_six_exact_files_technical_not_visual"
        )

        if phase == "update":
            runtime = entry.runtime_data
            require(
                await hass.config_entries.async_remove(entry.entry_id),
                "Entry removal failed",
            )
            await hass.async_block_till_done()
            require(
                not hass.config_entries.async_entries(DOMAIN), "Entry still configured"
            )
            snapshot = runtime.source_statuses.copy()
            await helper("mvp_a_smoke", True)
            require(
                runtime.source_statuses == snapshot and not runtime._listeners,
                "Removed entry still follows sources",
            )
            require(
                not er.async_entries_for_config_entry(registry, entry.entry_id),
                "Removed registry entries retained",
            )
            new_entry = await create()
            require(
                new_entry.entry_id != entry.entry_id,
                "Recreated entry reused removed identity",
            )
            expect(new_entry, "on", "complete")
            await helper("mvp_a_smoke", False)
            expect(new_entry, "off", "complete")
            report["checks"].append(
                "remove_detaches_old_runtime_and_readd_has_exactly_two_current_overviews"
            )
        if phase == "restore":
            report["checks"].append(
                "stopped_file_snapshot_restored_checkpoint_then_normal_off_complete"
            )
        report["result"] = "PASS"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        (root / f"{phase}-traceback.log").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
    finally:
        if hass is not None:
            try:
                await hass.async_stop(force=True)
            except Exception as exc:
                report["result"] = "FAIL"
                report["shutdown_error_type"] = type(exc).__name__
                (root / f"{phase}-shutdown.log").write_text(
                    traceback.format_exc(), encoding="utf-8"
                )
        (root / f"{phase}-result.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(json.dumps(report))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("seed", "update", "restore"), required=True)
    parser.add_argument(
        "--ha-version", choices=("2026.10.4", "2026.11.1"), required=True
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.phase, args.ha_version)))
