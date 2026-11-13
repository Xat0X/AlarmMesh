"""Compatibility proof with simulation sources, never live-device acceptance."""

import argparse
import asyncio
import json
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from aiohttp import ClientSession

from homeassistant import bootstrap
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import __version__
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.runner import RuntimeConfig

VERSIONS = ("2026.10.4", "2026.11.1")
SCENARIOS = (
    "version_and_fresh_config",
    "configure_two_sources",
    "exactly_two_overviews",
    "off_complete",
    "smoke_on",
    "smoke_with_source_outage",
    "indeterminate_never_off",
    "source_recovery",
    "real_options_flow",
    "old_source_ignored",
    "reload_stable_identity",
    "unload_and_subscription_cleanup",
    "panel_assets_and_group_storage",
    "panel_reload_cleanup",
)
SCOPE = "technische controle met simulatiebronnen, geen fysieke apparaatvalidatie"


def require(condition: bool, message: str) -> None:
    """Keep checks effective even if Python is started with optimizations."""
    if not condition:
        raise AssertionError(message)


async def main(requested: str, config_dir: Path) -> int:
    """Use normal HA setup, helpers and flows in a new mounted configuration."""
    report = {
        "scope": SCOPE,
        "requested_ha_version": requested,
        "actual_ha_version": __version__,
        "git_commit": None,
        "run_id": None,
        "worktree_dirty": None,
        "relevant_local_changes": [],
        "result": "FAIL",
        "scenarios": dict.fromkeys(SCENARIOS, "NIET UITGEVOERD"),
    }
    hass = None
    client = None
    websocket = None
    current = SCENARIOS[0]

    def passed(name: str) -> None:
        report["scenarios"][name] = "PASS"

    try:
        require(__version__ == requested, "Requested and actual HA versions differ")
        require(not (config_dir / ".storage").exists(), "Configuration is not fresh")
        context = json.loads((config_dir / "run-context.json").read_text("utf-8-sig"))
        require(context["requested_ha_version"] == requested, "Run context mismatch")
        require(bool(context["run_id"]), "Missing run identity")
        for key in ("run_id", "git_commit", "worktree_dirty", "relevant_local_changes"):
            report[key] = context[key]
        passed(current)

        # Match HA CLI lookup; the caller mounts only this repo and fresh config.
        sys.path.insert(0, str(config_dir))
        current = "configure_two_sources"
        hass = await bootstrap.async_setup_hass(
            RuntimeConfig(config_dir=str(config_dir), skip_pip=True, log_no_color=True)
        )
        require(hass is not None and not hass.config.recovery_mode, "HA setup failed")
        await hass.async_start()
        await hass.async_block_till_done()
        from custom_components.alarmmesh.const import CONF_SOURCE_ENTITY_IDS, DOMAIN

        sources = ["binary_sensor.mvp_smoke_a", "binary_sensor.mvp_smoke_b"]
        for entity_id in sources:
            state = hass.states.get(entity_id)
            require(state is not None and state.state == "off", "Source not ready")
            require(state.attributes.get("device_class") == "smoke", "Source identity")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        require(result["type"] is FlowResultType.FORM, "Config form missing")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOURCE_ENTITY_IDS: sources}
        )
        require(result["type"] is FlowResultType.CREATE_ENTRY, "Config flow failed")
        entry = result["result"]
        await hass.async_block_till_done()
        require(entry.state is ConfigEntryState.LOADED, "AlarmMesh not loaded")
        passed(current)

        registry = er.async_get(hass)

        def identity() -> list[tuple[str, str, str]]:
            entities = er.async_entries_for_config_entry(registry, entry.entry_id)
            require(len(entities) == 2, "Expected exactly two overview entities")
            require(
                {e.domain for e in entities} == {"binary_sensor", "sensor"}, "Domains"
            )
            require(all(e.device_id is None for e in entities), "Unexpected device")
            return sorted((e.id, e.unique_id, e.entity_id) for e in entities)

        current = "exactly_two_overviews"
        original_identity = identity()
        smoke_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_smoke"
        )
        availability_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_source_availability"
        )
        require(smoke_id is not None and availability_id is not None, "Overview IDs")
        passed(current)

        current = "panel_assets_and_group_storage"
        from homeassistant.auth.const import GROUP_ID_ADMIN
        from homeassistant.components import frontend

        from custom_components.alarmmesh.panel import DATA_HUB

        registration = hass.data[frontend.DATA_PANELS][DOMAIN]
        require(registration.require_admin, "Panel must use HA admin authorization")
        module_url = registration.config["_panel_custom"]["module_url"]
        parsed = urlsplit(module_url)
        version = parse_qs(parsed.query)
        require(
            not parsed.scheme
            and not parsed.netloc
            and not parsed.fragment
            and parsed.path == "/alarmmesh-assets/panel.js"
            and set(version) == {"v"}
            and len(version["v"]) == 1
            and bool(version["v"][0]),
            "Panel module URL must be local and versioned",
        )
        client = ClientSession()
        async with client.get(f"http://127.0.0.1:8123{module_url}") as response:
            require(
                response.status == 200 and "alarmmesh-panel" in await response.text(),
                "Panel asset not served",
            )
        # Supported HA auth APIs create an isolated test-only principal. No
        # onboarding/storage edits, borrowed account, printed token or live HA.
        user = await hass.auth.async_create_user(
            "Compatibility simulation", group_ids=[GROUP_ID_ADMIN]
        )
        refresh = await hass.auth.async_create_refresh_token(
            user, client_id="http://localhost"
        )
        token = hass.auth.async_create_access_token(refresh)
        websocket = await client.ws_connect("http://127.0.0.1:8123/api/websocket")
        require(
            (await websocket.receive_json())["type"] == "auth_required",
            "Expected authenticated transport",
        )
        await websocket.send_json({"type": "auth", "access_token": token})
        require(
            (await websocket.receive_json())["type"] == "auth_ok",
            "Simulation auth failed",
        )

        async def ws_request(message):
            await websocket.send_json(message)
            async with asyncio.timeout(10):
                while True:
                    answer = await websocket.receive_json()
                    if (
                        answer.get("type") == "result"
                        and answer.get("id") == message["id"]
                    ):
                        require(answer["success"], "Panel WebSocket command failed")
                        return answer["result"]

        await ws_request({"id": 1, "type": "alarmmesh/subscribe"})
        initial = (await websocket.receive_json())["event"]
        require(
            initial["available"] and len(initial["sources"]) == 2,
            "Panel runtime data missing",
        )
        await ws_request(
            {
                "id": 2,
                "type": "alarmmesh/group",
                "operation": "create",
                "revision": 0,
                "name": "Simulation group",
                "members": sources,
            }
        )
        original_panel = entry.runtime_data.panel
        group_id = original_panel.groups.groups[0]["id"]
        require(
            original_panel.snapshot()["groups"][0]["result"]
            == original_panel.snapshot()["result"],
            "Group calculation differs",
        )
        passed(current)

        def expect(smoke: str, availability: str) -> None:
            smoke_state = hass.states.get(smoke_id)
            availability_state = hass.states.get(availability_id)
            require(
                smoke_state is not None and smoke_state.state == smoke, "Smoke state"
            )
            require(
                availability_state is not None
                and availability_state.state == availability,
                "Source availability state",
            )

        async def helper(name: str, on: bool) -> None:
            await hass.services.async_call(
                "input_boolean",
                "turn_on" if on else "turn_off",
                {"entity_id": f"input_boolean.{name}"},
                blocking=True,
            )
            await hass.async_block_till_done()

        current = "off_complete"
        expect("off", "complete")
        passed(current)
        current = "smoke_on"
        await helper("mvp_a_smoke", True)
        expect("on", "complete")
        passed(current)
        current = "smoke_with_source_outage"
        await helper("mvp_b_unreachable", True)
        expect("on", "incomplete")
        passed(current)
        current = "indeterminate_never_off"
        await helper("mvp_a_smoke", False)
        expect("unavailable", "incomplete")
        passed(current)
        current = "source_recovery"
        await helper("mvp_b_unreachable", False)
        expect("off", "complete")
        passed(current)

        old_runtime = entry.runtime_data
        old_statuses = old_runtime.source_statuses.copy()
        current = "real_options_flow"
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SOURCE_ENTITY_IDS: [sources[1]]}
        )
        require(result["type"] is FlowResultType.CREATE_ENTRY, "Options flow failed")
        await hass.async_block_till_done()
        require(entry.runtime_data is not old_runtime, "Options did not reload")
        require(
            entry.options == {CONF_SOURCE_ENTITY_IDS: [sources[1]]}, "Options storage"
        )
        expect("off", "complete")
        passed(current)
        current = "old_source_ignored"
        await helper("mvp_a_smoke", True)
        expect("off", "complete")
        require(
            set(entry.runtime_data.source_statuses) == {sources[1]},
            "Old source followed",
        )
        require(old_runtime.source_statuses == old_statuses, "Old runtime changed")
        await helper("mvp_b_smoke", True)
        expect("on", "complete")
        require(
            old_runtime.source_statuses == old_statuses, "Old subscription survived"
        )
        passed(current)

        current = "reload_stable_identity"
        previous = entry.runtime_data
        previous_statuses = previous.source_statuses.copy()
        require(await hass.config_entries.async_reload(entry.entry_id), "Reload failed")
        await hass.async_block_till_done()
        require(entry.runtime_data is not previous, "Runtime was reused")
        require(identity() == original_identity, "Entity identity changed")
        expect("on", "complete")
        await helper("mvp_b_smoke", False)
        expect("off", "complete")
        require(
            previous.source_statuses == previous_statuses, "Reload subscription leak"
        )
        passed(current)

        current = "unload_and_subscription_cleanup"
        final_runtime = entry.runtime_data
        final_statuses = final_runtime.source_statuses.copy()
        require(await hass.config_entries.async_unload(entry.entry_id), "Unload failed")
        require(entry.state is ConfigEntryState.NOT_LOADED, "Entry not unloaded")
        require(not hasattr(entry, "runtime_data"), "Runtime retained")
        await helper("mvp_b_smoke", True)
        require(
            final_runtime.source_statuses == final_statuses, "Source subscription leak"
        )
        for runtime in (old_runtime, previous, final_runtime):
            require(not runtime._listeners, "Entity subscription leak")
        for entity_id in (smoke_id, availability_id):
            state = hass.states.get(entity_id)
            require(
                state is None or state.state == "unavailable", "Overview still active"
            )
        passed(current)
        current = "panel_reload_cleanup"
        require(
            not original_panel.unsubscribers and not original_panel.runtime._observers,
            "Old panel subscriptions survived",
        )
        require(
            hass.data[DATA_HUB].controller is None
            and DOMAIN not in hass.data[frontend.DATA_PANELS],
            "Unloaded panel still registered",
        )
        require(
            await hass.config_entries.async_setup(entry.entry_id),
            "Panel re-setup failed",
        )
        await hass.async_block_till_done()
        current_panel = entry.runtime_data.panel
        require(
            current_panel.groups.groups[0]["id"] == group_id,
            "Group storage/identity not retained",
        )
        require(
            current_panel.snapshot()["groups"][0]["unselected"] == [sources[0]],
            "Stale member was silently removed",
        )
        await ws_request(
            {
                "id": 3,
                "type": "alarmmesh/group",
                "operation": "delete",
                "revision": 1,
                "group_id": group_id,
            }
        )
        require(not current_panel.groups.groups, "Group deletion failed")
        await ws_request({"id": 4, "type": "unsubscribe_events", "subscription": 1})
        require(not hass.data[DATA_HUB].listeners, "WebSocket subscription leaked")
        require(
            await hass.config_entries.async_unload(entry.entry_id),
            "Final panel unload failed",
        )
        require(
            not current_panel.unsubscribers and not current_panel.runtime._observers,
            "Final panel listener leak",
        )
        passed(current)
        report["result"] = "PASS"
    except Exception as exc:
        report["scenarios"][current] = "FAIL"
        report["error_type"] = type(exc).__name__
        # Keep the original failure locally; never include it in CI artifacts.
        await asyncio.to_thread(
            (config_dir / "failure-traceback.log").write_text,
            traceback.format_exc(),
            encoding="utf-8",
        )
    finally:
        if websocket is not None:
            await websocket.close()
        if client is not None:
            await client.close()
        if hass is not None:
            try:
                await hass.async_stop(force=True)
            except Exception as exc:
                report["result"] = "FAIL"
                report["shutdown_error_type"] = type(exc).__name__
                await asyncio.to_thread(
                    (config_dir / "shutdown-traceback.log").write_text,
                    traceback.format_exc(),
                    encoding="utf-8",
                )
        await asyncio.to_thread(
            (config_dir / "technical-result.json").write_text,
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-version", choices=VERSIONS, default=VERSIONS[0])
    parser.add_argument("--config", type=Path, default=Path("/config"))
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.ha_version, args.config)))
