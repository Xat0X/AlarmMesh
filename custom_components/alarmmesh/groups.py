"""Versioned, atomic organizational groups; never store source observations."""

import asyncio
from copy import deepcopy
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .automation import (
    DEFAULT_ACTIONS,
    AutomationError,
    script_target,
    validate_actions,
)
from .capabilities import Capabilities

MAX_NAME = 64
MAX_MEMBERS = 256
MAX_GROUPS = 100


class GroupError(ValueError):
    """A public, translated error code for a rejected mutation."""


class GroupStore:
    """Serialize optimistic writes and commit memory only after durable save."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.capabilities = Capabilities(hass)
        self.store = Store(hass, 1, f"alarmmesh.groups.{entry_id}", atomic_writes=True)
        self.revision = 0
        self.groups: list[dict] = []
        self._lock = asyncio.Lock()
        self._closed = False

    async def async_load(self) -> None:
        """Old entries need no migration; damaged data must not be overwritten."""
        if (data := await self.store.async_load()) is not None:
            if (
                not isinstance(data, dict)
                or type(data.get("revision")) is not int
                or data["revision"] < 0
                or not isinstance(data.get("groups"), list)
                or len(data["groups"]) > MAX_GROUPS
                or type(data.get("schema", 1)) is not int
                or data.get("schema", 1) not in (1, 2, 3)
            ):
                raise GroupError("invalid_storage")
            ids = set()
            for group in data["groups"]:
                if (
                    not isinstance(group, dict)
                    or not {"id", "name", "members"} <= group.keys()
                    or not group.keys()
                    <= {"id", "name", "members", "linking", "origins", "actions"}
                ):
                    raise GroupError("invalid_storage")
                group_id = group["id"]
                if (
                    not isinstance(group_id, str)
                    or len(group_id) != 32
                    or any(c not in "0123456789abcdef" for c in group_id)
                    or group_id in ids
                ):
                    raise GroupError("invalid_storage")
                ids.add(group_id)
                self.validate(group["name"], group["members"])
                self.validate_link_shape(
                    group.get("linking", {"enabled": False, "bindings": []})
                )
                self.validate_origins(
                    group.get("origins", group["members"]), group["members"]
                )
                try:
                    validate_actions(group.get("actions", DEFAULT_ACTIONS))
                except AutomationError as err:
                    raise GroupError("invalid_storage") from err
            self.revision = data["revision"]
            self.groups = deepcopy(data["groups"])
            for group in self.groups:
                group.setdefault("linking", {"enabled": False, "bindings": []})

    @staticmethod
    def validate_origins(origins, members):
        _, origins = GroupStore.validate("origins", origins)
        if not set(origins) <= set(members):
            raise GroupError("invalid_origins")
        return origins

    def validate_extensions(self, command, members, previous, selected):
        value = {}
        if "origins" in command or (previous and "origins" in previous):
            value["origins"] = self.validate_origins(
                command.get(
                    "origins", previous.get("origins", members) if previous else members
                ),
                members,
            )
        if "actions" in command or (previous and "actions" in previous):
            old = (
                previous.get("actions", DEFAULT_ACTIONS)
                if previous
                else DEFAULT_ACTIONS
            )
            actions = deepcopy(command.get("actions", old))
            try:
                validate_actions(actions)
            except AutomationError as err:
                raise GroupError(str(err)) from err
            if actions["enabled"]:
                if command.get("confirmed") is not True:
                    raise GroupError("automation_confirmation_required")
                if not value.get("origins", members) or not set(
                    value.get("origins", members)
                ) <= set(selected):
                    raise GroupError("invalid_origins")
            for phase in ("start", "recovery"):
                for binding in actions[phase]:
                    current = script_target(
                        self.capabilities.hass, binding["entity_id"]
                    )
                    if (
                        current is None or current["identity"] != binding["identity"]
                    ) and (actions["enabled"] or binding not in old[phase]):
                        raise GroupError("script_changed")
            value["actions"] = actions
        return value

    @staticmethod
    def validate_link_shape(value: object) -> None:
        """Version-2 payload is bounded and explicit; no arbitrary HA commands."""
        if (
            not isinstance(value, dict)
            or set(value) != {"enabled", "bindings"}
            or type(value["enabled"]) is not bool
            or not isinstance(value["bindings"], list)
            or len(value["bindings"]) > MAX_MEMBERS
        ):
            raise GroupError("invalid_linking")
        seen = set()
        targets = set()
        for binding in value["bindings"]:
            if (
                not isinstance(binding, dict)
                or set(binding) != {"source", "target", "profile", "identity"}
                or any(
                    not isinstance(v, str) or not 1 <= len(v) <= 255
                    for v in binding.values()
                )
            ):
                raise GroupError("invalid_linking")
            if (
                binding["source"] in seen
                or binding["target"] in targets
                or len(binding["identity"]) != 64
                or any(c not in "0123456789abcdef" for c in binding["identity"])
            ):
                raise GroupError("invalid_linking")
            seen.add(binding["source"])
            targets.add(binding["target"])

    def validate_linking(
        self,
        command: dict,
        members: list[str],
        selected: tuple[str, ...],
        previous: dict | None,
    ) -> dict:
        """Validate again at save time, including identity seen in admin's preview."""
        old = (
            previous.get("linking", {"enabled": False, "bindings": []})
            if previous
            else {"enabled": False, "bindings": []}
        )
        value = command.get("linking", old)
        self.validate_link_shape(value)
        value = deepcopy(value)
        if any(b["source"] not in members for b in value["bindings"]):
            raise GroupError("invalid_linking")
        if value["enabled"]:
            if (
                command.get("confirmed") is not True
                or len(members) < 2
                or not value["bindings"]
                or not set(members) <= set(selected)
            ):
                raise GroupError("linking_confirmation_required")
        for binding in value["bindings"]:
            if self.capabilities.resolve(binding) is None and (
                value["enabled"] or binding not in old["bindings"]
            ):
                raise GroupError("control_changed")
        return value

    @staticmethod
    def validate(name: object, members: object) -> tuple[str, list[str]]:
        """Bound both storage and UI input; don't coerce malformed values."""
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME:
            raise GroupError("invalid_name")
        if (
            not isinstance(members, list)
            or len(members) > MAX_MEMBERS
            or any(
                not isinstance(member, str)
                or not member.startswith("binary_sensor.")
                or len(member) > 255
                or not member[14:]
                or any(
                    c not in "abcdefghijklmnopqrstuvwxyz0123456789_"
                    for c in member[14:]
                )
                for member in members
            )
            or len(set(members)) != len(members)
        ):
            raise GroupError("invalid_members")
        return name.strip(), list(members)

    async def async_mutate(self, command: dict, selected: tuple[str, ...]) -> None:
        """Retain stale references only if already in this particular group."""
        async with self._lock:
            if self._closed:
                raise GroupError("not_loaded")
            if (
                type(command.get("revision")) is not int
                or command["revision"] != self.revision
            ):
                raise GroupError("conflict")
            group_id = command.get("group_id")
            previous = next((g for g in self.groups if g["id"] == group_id), None)
            operation = command.get("operation")
            if operation == "copy":
                if previous is None:
                    raise GroupError("not_found")
                members = command.get("members")
                origins = command.get("origins")
                if (
                    not isinstance(members, list)
                    or not isinstance(origins, list)
                    or any(not isinstance(s, str) for s in members + origins)
                    or not set(members) <= set(previous["members"]) & set(selected)
                    or not set(origins)
                    <= set(members) & set(previous.get("origins", previous["members"]))
                ):
                    raise GroupError("invalid_members")
                # Construct a new organizational group, never inherit authority.
                command = {
                    "operation": "create",
                    "revision": command["revision"],
                    "name": command.get("name"),
                    "members": members,
                    "origins": origins,
                }
                group_id, previous, operation = None, None, "create"
            if operation not in {"create", "update", "delete"}:
                raise GroupError("invalid_operation")
            if operation == "create":
                if group_id is not None or len(self.groups) >= MAX_GROUPS:
                    raise GroupError("group_limit")
                creation_id = command.get("creation_id")
                if creation_id is not None:
                    if (
                        not isinstance(creation_id, str)
                        or len(creation_id) != 32
                        or any(c not in "0123456789abcdef" for c in creation_id)
                    ):
                        raise GroupError("invalid_operation")
                    if any(group["id"] == creation_id for group in self.groups):
                        raise GroupError("conflict")
                    group_id = creation_id
            elif "creation_id" in command:
                raise GroupError("invalid_operation")
            elif previous is None:
                raise GroupError("not_found")
            groups = deepcopy(self.groups)
            if operation == "delete":
                groups = [g for g in groups if g["id"] != group_id]
            else:
                name, members = self.validate(
                    command.get("name"), command.get("members")
                )
                allowed = set(selected) | set(previous["members"] if previous else ())
                if not set(members) <= allowed:
                    raise GroupError("invalid_members")
                value = {
                    "id": group_id or uuid4().hex,
                    "name": name,
                    "members": members,
                    "linking": self.validate_linking(
                        command, members, selected, previous
                    ),
                    **self.validate_extensions(command, members, previous, selected),
                }
                if value["linking"]["enabled"] and not value.get("origins", members):
                    raise GroupError("invalid_origins")
                if previous:
                    groups = [value if g["id"] == group_id else g for g in groups]
                else:
                    groups.append(value)
            revision = self.revision + 1
            await self.store.async_save(
                {
                    "schema": 3
                    if any("origins" in g or "actions" in g for g in groups)
                    else 2,
                    "revision": revision,
                    "groups": groups,
                }
            )
            self.groups, self.revision = groups, revision

    async def async_close(self) -> None:
        """Drain a pending write before another runtime loads this entry's store."""
        async with self._lock:
            self._closed = True
