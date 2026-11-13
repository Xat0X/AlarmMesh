"""Authenticated push presentation, HA registry metadata and panel lifecycle."""

from collections.abc import Callable
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .groups import GroupError, GroupStore
from .runtime import AlarmMeshConfigEntry
from .status import SourceStatus, StatusResult, evaluate_status

DATA_HUB = "alarmmesh_panel"
ASSET_URL = "/alarmmesh-assets"


def result_dict(result: StatusResult) -> dict:
    """Expose stable semantic names; the browser never evaluates smoke."""
    return {
        "smoke": result.smoke_status.name,
        "availability": result.source_availability.name,
    }


class PanelHub:
    """One HA-process transport; subscribers survive entry reload, not stale data."""

    def __init__(self) -> None:
        self.controller: PanelController | None = None
        self.listeners: set[Callable] = set()

    @callback
    def publish(self, *_args) -> None:
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
        self.unsubscribers: list[Callable] = []

    async def async_start(self) -> None:
        await self.groups.async_load()
        self.unsubscribers.append(self.runtime.async_add_observer(self.hub.publish))
        for event in (
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            ar.EVENT_AREA_REGISTRY_UPDATED,
        ):
            self.unsubscribers.append(
                self.hass.bus.async_listen(event, self.hub.publish)
            )
        await panel_custom.async_register_panel(
            self.hass,
            "alarmmesh",
            "alarmmesh-panel",
            sidebar_title="AlarmMesh",
            sidebar_icon="mdi:smoke-detector",
            module_url=f"{ASSET_URL}/panel.js?v=20261113-copy",
            require_admin=True,
        )
        self.hub.controller = self
        self.hub.publish()

    async def async_close(self) -> None:
        await self.groups.async_close()
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        if self.hub.controller is self:
            self.hub.controller = None
            frontend.async_remove_panel(self.hass, "alarmmesh")
            self.hub.publish()

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
                "ha_state": state.state if state else None,
                "area_id": room_id,
                "area_name": area.name if area else None,
                "model": device.model if device else None,
                "manufacturer": device.manufacturer if device else None,
                "device_name": (device.name_by_user or device.name) if device else None,
                "groups": [
                    g["id"] for g in self.groups.groups if entity_id in g["members"]
                ],
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
        groups = [
            {
                **group,
                "result": summary(group["members"]),
                "unselected": [
                    member
                    for member in group["members"]
                    if member not in self.runtime.source_entity_ids
                ],
            }
            for group in self.groups.groups
        ]
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
    hub.publish()
