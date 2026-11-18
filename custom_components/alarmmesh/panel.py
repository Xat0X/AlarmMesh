"""Authenticated push presentation, HA registry metadata and panel lifecycle."""

import json
import re
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import (
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    __version__,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .activity import Activity
from .automation import AutomationError
from .catalog import CATALOG
from .diagnostics import support_report
from .effects import IncidentEffects
from .groups import GroupError, GroupStore
from .linking_runtime import LinkingRuntime
from .maintenance import Maintenance
from .matter import MatterSources, is_co_source
from .preview import group_preview, source_preview
from .recovery import recover_groups, recovery_plan
from .reminders import Reminders
from .runtime import AlarmMeshConfigEntry
from .self_test import SelfTests
from .status import SourceStatus, StatusResult, evaluate_status
from .zwave import invalid_source as invalid_zwave_source

DATA_HUB = "alarmmesh_panel"
ASSET_URL = "/alarmmesh-assets"


def result_dict(result: StatusResult) -> dict:
    """Expose stable semantic names; the browser never evaluates smoke."""
    return {
        "smoke": result.smoke_status.name,
        "availability": result.source_availability.name,
    }


def configuration_review(
    sources: list[dict], groups: list[dict], automation: dict
) -> dict:
    """Derive guidance from current validated metadata; never persist progress."""
    issues = []

    def issue(code, *, source=None, group=None, target=None, phase=None):
        issues.append(
            {
                "code": code,
                "source": source,
                "group": group,
                "target": target,
                "phase": phase,
            }
        )

    if not sources:
        issue("setupNoSources")
    for source in sources:
        if source["identity_changed"]:
            issue("source_identity_changed", source=source["entity_id"])
        if source["status"] not in {"SMOKE_REPORTED", "NO_SMOKE_REPORTED"}:
            issue("checkSourceUnavailable", source=source["entity_id"])
        if not source["area_id"]:
            issue("noRoom", source=source["entity_id"])
    for group in groups:
        for source in group["unselected"]:
            issue("storedSourceMissing", source=source, group=group["id"])
        for row in group["binding_checks"]:
            if not row["valid"]:
                issue(
                    row["reason"],
                    source=row["source"],
                    group=group["id"],
                    target=row["target"],
                )
        for row in group["script_checks"]:
            if not row["valid"]:
                issue(
                    "script_changed",
                    group=group["id"],
                    target=row["entity_id"],
                    phase=row["phase"],
                )
    for target in automation["missing_recipients"]:
        issue("recipient_unavailable", target=target)
    if automation["error"]:
        issue(automation["error"])
    bindings = [row for group in groups for row in group["binding_checks"]]
    actions = [row for group in groups for row in group["script_checks"]]
    enabled_linking = any(group["linking"]["enabled"] for group in groups)
    enabled_actions = any(group.get("actions", {}).get("enabled") for group in groups)
    notifications = automation["settings"]
    steps = [
        (
            "sources",
            "configured"
            if sources
            and all(
                s["status"] in {"SMOKE_REPORTED", "NO_SMOKE_REPORTED"}
                and not s["identity_changed"]
                for s in sources
            )
            else "needs_attention",
            len(sources),
        ),
        (
            "rooms",
            "configured"
            if sources and all(s["area_id"] for s in sources)
            else "needs_attention",
            sum(bool(s["area_id"]) for s in sources),
        ),
        (
            "groups",
            "needs_attention"
            if any(
                g["unselected"]
                or (g["linking"]["enabled"] or g.get("actions", {}).get("enabled"))
                and not g.get("origins", g["members"])
                for g in groups
            )
            else "configured"
            if groups
            else "disabled",
            len(groups),
        ),
        (
            "sounders",
            "needs_attention"
            if any(
                g["linking"]["enabled"]
                and any(not r["valid"] for r in g["binding_checks"])
                for g in groups
            )
            else "configured"
            if enabled_linking
            else "disabled"
            if bindings
            or any(s["capability"]["status"] != "detection_only" for s in sources)
            else "not_supported",
            len(bindings),
        ),
        (
            "notifications",
            "needs_attention"
            if notifications["enabled"]
            and any(
                r["enabled"] and r["service"] in automation["missing_recipients"]
                for r in notifications["recipients"]
            )
            else "configured"
            if notifications["enabled"]
            else "disabled",
            len(notifications["recipients"]),
        ),
        (
            "scripts",
            "needs_attention"
            if enabled_actions and any(not r["valid"] for r in actions if r["enabled"])
            else "configured"
            if enabled_actions
            else "disabled",
            len(actions),
        ),
        ("check", "needs_attention" if issues else "configured", len(issues)),
    ]
    return {
        "steps": [
            {"id": key, "status": status, "count": count}
            for key, status, count in steps
        ],
        "issues": issues,
    }


class PanelHub:
    """One HA-process transport; subscribers survive entry reload, not stale data."""

    def __init__(self) -> None:
        self.controller: PanelController | None = None
        self.listeners: set[Callable] = set()

    @callback
    def publish(self, *_args) -> None:
        if self.controller is not None:
            self.controller.activity.capture(self.controller)
        for listener in tuple(self.listeners):
            listener()

    def snapshot(self) -> dict:
        if self.controller is None:
            return {"available": False}
        return self.controller.snapshot()


class PanelController:
    """Entry-owned view of the same runtime, plus organizational group storage."""

    def __init__(self, hass: HomeAssistant, entry: AlarmMeshConfigEntry, hub: PanelHub):
        self.hass, self.entry, self.hub = hass, entry, hub
        self.runtime = entry.runtime_data
        self.groups = GroupStore(hass, entry.entry_id)
        self.matter_sources = MatterSources(hass, entry)
        self.linking = LinkingRuntime(hass, entry, self.groups, hub.publish)
        self.effects = IncidentEffects(
            hass, entry, self.linking, self.groups, hub.publish
        )
        self.selftests = SelfTests(hass, entry, self.linking, hub.publish)
        self.maintenance = Maintenance(hass, entry, self.linking, hub.publish)
        self.activity = Activity(hass, entry, hub.publish)
        self.reminders = Reminders(
            hass, entry, self.linking, hub.publish, self.activity
        )
        self.integration_version = "unknown"
        self.linking.effects_changed = self._outputs_changed
        self.linking.independent_test_source = self.selftests.independent_source
        self.unsubscribers: list[Callable] = []
        self.script_unsubscribe = None

    async def async_start(self) -> None:
        self.integration_version = await self.hass.async_add_executor_job(
            lambda: json.loads((Path(__file__).parent / "manifest.json").read_text())[
                "version"
            ]
        )
        await self.groups.async_load()
        await self.matter_sources.load()
        await self.effects.load()
        await self.selftests.load()
        await self.maintenance.load()
        await self.activity.load()
        await self.reminders.load()
        self.unsubscribers.append(self.runtime.async_add_observer(self.hub.publish))
        for event in (
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            ar.EVENT_AREA_REGISTRY_UPDATED,
            EVENT_SERVICE_REGISTERED,
            EVENT_SERVICE_REMOVED,
        ):
            self.unsubscribers.append(
                self.hass.bus.async_listen(event, self._registry_changed)
            )
        await panel_custom.async_register_panel(
            self.hass,
            "alarmmesh",
            "alarmmesh-panel",
            sidebar_title="AlarmMesh",
            sidebar_icon="mdi:smoke-detector",
            module_url=f"{ASSET_URL}/panel.js?v=20261118-independent-1",
            require_admin=True,
        )
        self.hub.controller = self
        self._watch_scripts()
        self.activity.capture(self)
        self.linking.start()
        self.maintenance.start()
        self.reminders.start()
        self.hub.publish()

    @callback
    def _outputs_changed(self):
        self.effects.changed()
        self.maintenance.changed()
        self.reminders.changed()

    @callback
    def _registry_changed(self, *_args):
        changed = False
        for source, status in self.runtime.source_statuses.items():
            if status is not SourceStatus.UNKNOWN and (
                is_co_source(self.hass, source)
                or invalid_zwave_source(self.hass, source)
            ):
                self.runtime.source_statuses[source] = SourceStatus.UNKNOWN
                changed = True
        if changed:
            self.runtime.async_set_result(
                evaluate_status(self.runtime.source_statuses.values())
            )
            self.runtime.async_notify_observers()
        self.linking.refresh_watch()
        self._watch_scripts()
        self.selftests.check_identity()
        self.reminders.changed()
        self.hub.publish()

    def _watch_scripts(self):
        if self.script_unsubscribe:
            self.script_unsubscribe()
            self.script_unsubscribe = None
        ids = [
            e.entity_id
            for e in er.async_get(self.hass).entities.values()
            if e.domain == "script"
        ]
        if ids:
            self.script_unsubscribe = async_track_state_change_event(
                self.hass, ids, self.hub.publish
            )

    async def async_close(self) -> None:
        await self.async_pause()
        await self.selftests.close()
        await self.maintenance.close()
        await self.reminders.close()
        await self.effects.close()
        await self.linking.close()
        await self.groups.async_close()
        await self.activity.close()
        await self.matter_sources.close()
        if self.script_unsubscribe:
            self.script_unsubscribe()
            self.script_unsubscribe = None
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        if self.hub.controller is self:
            self.hub.controller = None
            frontend.async_remove_panel(self.hass, "alarmmesh")
            self.hub.publish()

    async def async_pause(self):
        await self.reminders.pause()
        await self.maintenance.pause()
        await self.linking.pause()
        await self.effects.pause()
        await self.selftests.pause()
        await self.activity.pause()

    def snapshot(self) -> dict:
        """Resolve entity area before device area; don't infer device capabilities."""
        entities = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        areas = ar.async_get(self.hass)
        sources = []
        rooms: dict[str | None, dict] = {}
        for entity_id in self.runtime.source_entity_ids:
            entity = entities.async_get(entity_id)
            device = (
                devices.async_get(entity.device_id)
                if entity and entity.device_id
                else None
            )
            area_id = (
                entity.area_id
                if entity and entity.area_id
                else device.area_id
                if device
                else None
            )
            area = areas.async_get_area(area_id) if area_id else None
            state = self.hass.states.get(entity_id)
            name = (
                (entity.name if entity else None)
                or (state.attributes.get("friendly_name") if state else None)
                or (entity.original_name if entity else None)
                or entity_id
            )
            status = self.runtime.source_statuses[entity_id]
            room_id = area.id if area else None
            source = {
                "entity_id": entity_id,
                "name": name,
                "status": status.name,
                "identity_changed": self.linking.capabilities.source_identity_changed(
                    entity_id
                ),
                "ha_state": state.state if state else None,
                "area_id": room_id,
                "area_name": area.name if area else None,
                "model": (
                    (device.model or device.model_id)
                    if entity and entity.platform in {"matter", "zwave_js"}
                    else (device.model_id or device.model)
                )
                if device
                else None,
                "manufacturer": device.manufacturer if device else None,
                "device_name": (device.name_by_user or device.name) if device else None,
                "groups": [
                    g["id"] for g in self.groups.groups if entity_id in g["members"]
                ],
                "capability": self.linking.capabilities.describe(entity_id),
                "selftest": self.selftests.describe(entity_id),
                "reminder_identity": self.reminders.identity(entity_id),
            }
            sources.append(source)
            room = rooms.setdefault(
                room_id, {"id": room_id, "name": source["area_name"], "members": []}
            )
            room["members"].append(entity_id)

        def summary(members: list[str]) -> dict:
            return result_dict(
                evaluate_status(
                    [
                        self.runtime.source_statuses.get(member, SourceStatus.MISSING)
                        for member in members
                    ]
                )
            )

        for room in rooms.values():
            room["result"] = summary(room["members"])
        automation = self.effects.snapshot()
        groups = [
            {
                **group,
                "result": summary(group["members"]),
                "unselected": [
                    member
                    for member in group["members"]
                    if member not in self.runtime.source_entity_ids
                ],
                "linking_status": "disabled"
                if not group["linking"]["enabled"]
                else "review_needed"
                if not set(group["members"]) <= set(self.runtime.source_entity_ids)
                or any(
                    self.linking.capabilities.resolve(b) is None
                    for b in group["linking"]["bindings"]
                )
                else "enabled",
            }
            for group in self.groups.groups
        ]
        for group in groups:
            group["binding_checks"] = []
            for binding in group["linking"]["bindings"]:
                source = next(
                    (s for s in sources if s["entity_id"] == binding["source"]), None
                )
                valid = (
                    binding["source"] in group["members"]
                    and source is not None
                    and self.linking.capabilities.resolve(binding) is not None
                )
                reason = (
                    source["capability"]["reason"]
                    if source and source["capability"]["status"] != "linkable"
                    else "control_changed"
                )
                group["binding_checks"].append(
                    {**binding, "valid": valid, "reason": None if valid else reason}
                )
            group["script_checks"] = [
                {
                    **binding,
                    "phase": phase,
                    "enabled": group["actions"]["enabled"],
                    "valid": any(
                        s["entity_id"] == binding["entity_id"]
                        and s["identity"] == binding["identity"]
                        for s in automation["scripts"]
                    ),
                }
                for phase in ("start", "recovery")
                for binding in group.get("actions", {}).get(phase, [])
            ]
        maintenance = self.maintenance.snapshot()
        review = configuration_review(sources, groups, automation)
        if self.matter_sources.error:
            review["issues"].append(
                {"code": self.matter_sources.error, "purpose": "matter"}
            )
            review["steps"][-1].update(
                status="needs_attention", count=len(review["issues"])
            )
        maintenance_problems = []
        if maintenance["error"]:
            maintenance_problems.append(
                {"code": maintenance["error"], "purpose": "maintenance"}
            )
        for target in maintenance["missing_recipients"]:
            if maintenance["settings"]["enabled"] and any(
                r["service"] == target and r["enabled"]
                for r in maintenance["settings"]["recipients"]
            ):
                maintenance_problems.append(
                    {
                        "code": "recipient_unavailable",
                        "target": target,
                        "purpose": "maintenance",
                    }
                )
        if maintenance_problems:
            review["issues"].extend(maintenance_problems)
            review["steps"][-1].update(
                status="needs_attention", count=len(review["issues"])
            )
        return {
            "available": True,
            "entry_id": self.entry.entry_id,
            "title": self.hass.config.location_name,
            "result": result_dict(self.runtime.result),
            "usable": sum(
                s["status"] in {"SMOKE_REPORTED", "NO_SMOKE_REPORTED"} for s in sources
            ),
            "sources": sources,
            "rooms": list(rooms.values()),
            "groups": groups,
            "revision": self.groups.revision,
            "incident": self.linking.snapshot(),
            "automation": automation,
            "selftest": deepcopy(self.selftests.record),
            "maintenance": maintenance,
            "activity": self.activity.snapshot(),
            "reminders": self.reminders.snapshot(),
            "review": review,
            "matter_revision": self.matter_sources.revision,
            "matter_error": self.matter_sources.error,
        }


async def async_prepare(hass: HomeAssistant) -> PanelHub:
    """Register static, credential-free code/commands once per HA process."""
    if DATA_HUB not in hass.data:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    ASSET_URL, str(Path(__file__).parent / "frontend"), False
                ),
                StaticPathConfig(
                    "/alarmmesh-brand", str(Path(__file__).parent / "brand"), True
                ),
            ]
        )
        hass.data[DATA_HUB] = PanelHub()
        websocket_api.async_register_command(hass, ws_subscribe)
        websocket_api.async_register_command(hass, ws_group)
        websocket_api.async_register_command(hass, ws_catalog)
        websocket_api.async_register_command(hass, ws_settings)
        websocket_api.async_register_command(hass, ws_phone_preview)
        websocket_api.async_register_command(hass, ws_test)
        websocket_api.async_register_command(hass, ws_maintenance)
        websocket_api.async_register_command(hass, ws_preview)
        websocket_api.async_register_command(hass, ws_route)
        websocket_api.async_register_command(hass, ws_current)
        websocket_api.async_register_command(hass, ws_recovery)
        websocket_api.async_register_command(hass, ws_diagnostics)
        websocket_api.async_register_command(hass, ws_reminder)
        websocket_api.async_register_command(hass, ws_group_copy)
        websocket_api.async_register_command(hass, ws_matter_review)
    return hass.data[DATA_HUB]


@websocket_api.websocket_command({vol.Required("type"): "alarmmesh/subscribe"})
@websocket_api.require_admin
@callback
def ws_subscribe(hass, connection, msg):
    """HA owns authentication, subscription cancellation and reconnect transport."""
    hub = hass.data[DATA_HUB]

    @callback
    def send():
        if connection.user is not None and connection.user.is_admin:
            connection.send_event(msg["id"], hub.snapshot())
        else:
            connection.send_event(msg["id"], {"available": False})

    hub.listeners.add(send)
    connection.subscriptions[msg["id"]] = lambda: hub.listeners.discard(send)
    connection.send_result(msg["id"])
    send()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/group",
        vol.Required("operation"): vol.In(["create", "update", "delete"]),
        vol.Required("revision"): vol.All(int, vol.Range(min=0)),
        vol.Optional("group_id"): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional("name"): vol.All(str, vol.Length(max=256)),
        vol.Optional("members"): vol.All(
            [vol.All(str, vol.Length(max=255))], vol.Length(max=256)
        ),
        vol.Optional("linking"): dict,
        vol.Optional("confirmed"): bool,
        vol.Optional("origins"): [str],
        vol.Optional("actions"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_group(hass, connection, msg):
    """Only administrators may mutate; reject stale or invalid requests."""
    hub = hass.data[DATA_HUB]
    if (controller := hub.controller) is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        await controller.groups.async_mutate(msg, controller.runtime.source_entity_ids)
    except GroupError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], {"revision": controller.groups.revision})
    controller.linking.changed()
    hub.publish()


@websocket_api.websocket_command({vol.Required("type"): "alarmmesh/catalog"})
@websocket_api.require_admin
@callback
def ws_catalog(hass, connection, msg):
    """Static offline evidence, fetched once; never grants execution authority."""
    connection.send_result(msg["id"], CATALOG)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/settings",
        vol.Required("revision"): int,
        vol.Required("notifications"): dict,
        vol.Optional("confirmed", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_settings(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None or controller.linking._paused:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        await controller.effects.settings.save(
            msg["notifications"],
            msg["revision"],
            msg["confirmed"],
            before_save=controller.effects.prepare_settings,
        )
    except (AutomationError, OSError) as err:
        code = (
            str(err) if isinstance(err, AutomationError) else "automation_storage_error"
        )
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(
        msg["id"], {"revision": controller.effects.settings.revision}
    )
    controller.effects.changed()
    controller.hub.publish()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/notification_preview",
        vol.Required("target"): vol.All(str, vol.Length(max=255)),
        vol.Required("request_id"): vol.Match(r"^[a-f0-9]{32}$"),
    }
)
@websocket_api.require_admin
@callback
def ws_phone_preview(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "not_loaded")
        return
    try:
        effects = controller.effects
        confirmation = effects.confirmation(msg["target"], msg["request_id"])
        if not confirmation:
            effects.phone_plan(msg["target"], test=True)
            raise AutomationError("recipient_unavailable")
        plan = effects.phone_plan(msg["target"], test=True)
    except AutomationError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(
        msg["id"],
        {
            **plan,
            "confirmation": confirmation,
            "context": effects.confirmation(msg["target"]),
            "request_id": msg["request_id"],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/test",
        vol.Required("kind"): vol.In(["notification", "script", "selftest"]),
        vol.Required("target"): vol.All(str, vol.Length(max=255)),
        vol.Optional("identity", default=""): vol.All(str, vol.Length(max=64)),
        vol.Required("confirmed"): bool,
        vol.Required("request_id"): vol.All(str, vol.Length(min=32, max=32)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_test(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:

        def authorized():
            return connection.user is not None and connection.user.is_admin

        if msg["kind"] == "selftest":
            if not re.fullmatch("[a-f0-9]{32}", msg["request_id"]):
                raise AutomationError("invalid_request")
            result = await controller.selftests.start(
                msg["target"],
                msg["identity"],
                msg["confirmed"],
                authorized,
                msg["request_id"],
            )
        else:
            if msg["kind"] == "notification" and (
                not msg["identity"]
                or msg["identity"]
                != controller.effects.confirmation(msg["target"], msg["request_id"])
                and (
                    controller.effects.phone_profile(msg["target"]) is not None
                    or msg["identity"] != controller.effects.confirmation(msg["target"])
                )
            ):
                raise AutomationError("notification_confirmation_stale")
            result = await controller.effects.manual(
                msg["kind"],
                msg["target"],
                msg["identity"],
                msg["confirmed"],
                msg["request_id"],
                authorized,
            )
    except (AutomationError, OSError) as err:
        code = (
            str(err) if isinstance(err, AutomationError) else "automation_storage_error"
        )
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/maintenance_settings",
        vol.Required("revision"): int,
        vol.Required("settings"): dict,
        vol.Required("confirmed"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_maintenance(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        await controller.maintenance.save(
            msg["settings"], msg["revision"], msg["confirmed"]
        )
    except (AutomationError, OSError) as err:
        code = (
            str(err)
            if isinstance(err, AutomationError)
            else "maintenance_storage_error"
        )
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(msg["id"], {"revision": controller.maintenance.revision})
    controller.hub.publish()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/preview",
        vol.Required("group_id"): str,
        vol.Required("source"): str,
    }
)
@websocket_api.require_admin
@callback
def ws_preview(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        result = group_preview(controller, msg["group_id"], msg["source"])
    except AutomationError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "alarmmesh/diagnostics"})
@websocket_api.require_admin
@callback
def ws_diagnostics(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    connection.send_result(
        msg["id"],
        support_report(
            controller.snapshot(), controller.integration_version, __version__
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/reminder",
        vol.Required("operation"): vol.In({"save", "snooze", "handle", "delete"}),
        vol.Required("source"): vol.All(str, vol.Length(max=255)),
        vol.Required("revision"): int,
        vol.Required("value"): dict,
        vol.Required("confirmed"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_reminder(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        await controller.reminders.save(
            msg["operation"],
            msg["source"],
            msg["revision"],
            msg["value"],
            msg["confirmed"],
        )
    except (AutomationError, OSError) as err:
        code = (
            str(err) if isinstance(err, AutomationError) else "reminder_storage_error"
        )
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(msg["id"], {"revision": controller.reminders.revision})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/group_copy",
        vol.Required("group_id"): str,
        vol.Required("revision"): int,
        vol.Required("name"): vol.All(str, vol.Length(max=64)),
        vol.Required("members"): vol.All([str], vol.Length(max=256)),
        vol.Required("origins"): vol.All([str], vol.Length(max=256)),
        vol.Required("confirmed"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_group_copy(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None or controller.linking._paused:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    if msg["confirmed"] is not True:
        connection.send_error(
            msg["id"],
            "automation_confirmation_required",
            "Confirm the organizational copy",
        )
        return
    try:
        await controller.groups.async_mutate(
            {**msg, "operation": "copy"}, controller.runtime.source_entity_ids
        )
    except (GroupError, OSError) as err:
        code = str(err) if isinstance(err, GroupError) else "invalid_storage"
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(msg["id"], {"revision": controller.groups.revision})
    controller.hub.publish()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/matter_review",
        vol.Required("source"): str,
        vol.Required("identity"): str,
        vol.Required("revision"): int,
        vol.Required("confirmed"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_matter_review(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None or controller.linking._paused:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        await controller.matter_sources.review(
            msg["source"], msg["identity"], msg["revision"], msg["confirmed"]
        )
    except (AutomationError, OSError) as err:
        code = (
            str(err)
            if isinstance(err, AutomationError)
            else "matter_identity_storage_error"
        )
        connection.send_error(msg["id"], code, code)
        return
    controller.activity.record(
        "configuration", "configuration", "changed", source=msg["source"]
    )
    controller.linking.changed()
    controller.hub.publish()
    connection.send_result(msg["id"], {"revision": controller.matter_sources.revision})


@websocket_api.websocket_command(
    {vol.Required("type"): "alarmmesh/route", vol.Required("source"): str}
)
@websocket_api.require_admin
@callback
def ws_route(hass, connection, msg):
    controller = hass.data[DATA_HUB].controller
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        result = source_preview(controller, msg["source"])
    except AutomationError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "alarmmesh/recovery",
        vol.Required("source"): str,
        vol.Optional("target"): str,
        vol.Optional("groups"): [str],
        vol.Optional("token"): str,
        vol.Optional("confirmed"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_recovery(hass, connection, msg):
    panel = hass.data[DATA_HUB].controller
    if panel is None:
        connection.send_error(msg["id"], "not_loaded", "AlarmMesh is not loaded")
        return
    try:
        if "target" in msg:
            if msg.get("confirmed") is not True:
                raise AutomationError("test_confirmation_required")
            await recover_groups(
                panel,
                msg["source"],
                msg["target"],
                msg.get("groups", []),
                msg.get("token"),
            )
            panel.hub.publish()
        result = (
            {"saved": True, "revision": panel.groups.revision}
            if "target" in msg
            else recovery_plan(panel, msg["source"])
        )
    except (AutomationError, OSError) as err:
        code = str(err) if isinstance(err, AutomationError) else "error"
        connection.send_error(msg["id"], code, code)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "alarmmesh/current"})
@websocket_api.require_admin
@callback
def ws_current(hass, connection, msg):
    panel = hass.data[DATA_HUB].controller
    connection.send_result(
        msg["id"], panel.snapshot() if panel else {"available": False}
    )
