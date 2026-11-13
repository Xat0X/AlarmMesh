# Architecture and scope

## Optional linked sounding — local extension

The [linking contract and reviewed profiles](linked-sounding.md) extend the panel
without changing `status.py`, selected-source options, overview entities or their
identities. `capabilities.py` reads cached entity/device registry metadata and
validates exact same-device HA controls. `linking.py` is the pure incident/action
decision layer. Entry-owned `linking_runtime.py` alone executes bounded existing
HA select/siren actions; there is no direct MQTT, ZHA cluster or device transport.
Registry-bound fingerprints are checked on save and again immediately before
dispatch. No arbitrary action name/data can be configured.

Group storage keeps outer HA Store version 1 and its existing key. Explicit
payload schema 2 adds default-off `linking` with exact source/target/profile/identity
bindings. Schema-1 groups normalize in memory, retaining names, IDs, members and
revision; load never writes or enables them. Unknown payload schemas fail closed.
Atomic disk-first writes and admin/revision checks cover the entire change.

An independent in-memory incident set retains each smoke origin until explicit
off, without changing the current-state result. Test flags cannot create origins.
Targets are deduplicated across groups. Calls use an eight-slot semaphore and
ten-second timeout, with no automatic retry of dispatched failures. Heiman's
documented automation-only stop is restricted to current-runtime ownership;
Aqara and SMSZB-120 have no automatic stop. Successful action completion is not
physical confirmation. Incidents, requests and ownership are never persisted.

The executor starts after panel/group setup, including current already-on sources.
Unload pauses and cancels/drains work before platform teardown. Success closes all
executor subscriptions; failure retains read-only monitoring but leaves actions
paused with an explicit UI warning. Closed runtimes cannot dispatch. Reload builds
fresh observations/ownership; it never adopts an already active sounder. The
linking guide specifies disable/remap/source-removal and restart limits.

## Integrated panel and organizational groups — local interface package

The new [panel](panel.md) is a packaged native ES-module Web Component, registered
through `panel_custom.async_register_panel` by [panel.py](../custom_components/alarmmesh/panel.py).
HA supplies the authenticated `hass` object; there is no product server, token in
JavaScript, CDN, build step or second login. `frontend`, `http` and `websocket_api`
are built-in HA dependencies, not new pip requirements. Manifest version, config
entry version, options schema and overview unique IDs are unchanged.

The panel and both `alarmmesh/*` WebSocket commands are **admin-only**, using HA's
own authorization decorator. This deliberately avoids exposing an unfiltered
whole-home result to a user lacking source-entity permissions. Existing overview
entities retain HA's normal entity access. Mutations always recheck admin rights;
subscriptions also recheck before each push. Static code and supplied images
contain no private data; their supported HTTP routes and command registrations
last for the HA process. They are not duplicated on entry reload.

One entry-owned `PanelController` presents the existing runtime. Home results use
the exact shared `StatusResult`; room/group subsets call unchanged `evaluate_status`
in that backend only. A separate observer set reports every selected-source
transition, even if the aggregate result did not change, without changing the two
entities' existing result subscriptions. Entity/device/area registry events update
metadata. Entity area takes precedence over device area; absent assignment remains
"No area". Model/manufacturer are registry values. No battery inference, floor
invention, last-contact claim, polling or extra source entity is added.

A process transport hub holds subscribers and the current controller reference,
not a second copy of source observations. Successful unload detaches registry and
runtime observers, removes navigation and publishes unavailable. Reload attaches a
new controller and publishes its current snapshot to still-connected browsers.
Failed platform unload keeps the active controller, matching HA's existing lifecycle.
Setup failure closes a partial controller. Socket disconnect/navigation cancels the
browser subscription; reconnect subscribes again. The UI discards cached status on
disconnect/unload rather than presenting it as current truth.

[groups.py](../custom_components/alarmmesh/groups.py) uses one HA `Store` per entry:
key `alarmmesh.groups.<entry_id>`, storage version **1**, atomic writes. Groups have
stable UUIDs, trimmed 1–64-character names, up to 256 distinct source references
and at most 100 groups. Empty groups are allowed and evaluate to indeterminate /
not configured. An async lock serializes writes; a persisted global edit revision
rejects stale forms with `conflict`. Disk save completes before in-memory state is
committed and pushed. Reload drains an in-flight write before loading the next
controller. Invalid/unreadable storage fails setup without overwriting it.

New member references must be currently selected. Existing references may be
retained or explicitly removed when editing their original group. Removing a
source from options, renaming it, or losing metadata never silently deletes a
group or follows the new ID. An unselected reference contributes `MISSING` to
that group; a selected but absent source uses the runtime's `MISSING`. No current
selected members therefore cannot become an off result. Explicit entry deletion
removes only that entry's group store; re-add creates a new configuration identity.

The browser renders registry/user strings with text nodes. Native modal dialogs,
semantic buttons, visible focus, labels, reduced-motion rules and phone/tablet
breakpoints support interaction. Dutch/English dictionaries are packaged with
the module and follow HA's profile language. DOM tests are not layout or native
focus proof; real-browser observations remain separately recorded.

Official APIs checked **2026-11-13**:
[custom panels](https://contributors.home-assistant.io/frontend/custom-ui/panel/),
[WebSocket commands](https://contributors.home-assistant.io/frontend/extending/websocket-api/),
[authorization](https://contributors.home-assistant.io/core/internals/websocket-api/),
[HA client subscriptions](https://github.com/home-assistant/home-assistant-js-websocket/blob/master/lib/connection.ts).
Exact pinned Core APIs were also inspected in the official 2026.10.4 image.
The sections below document the retained source/overview contract.

## Foundation contract

AlarmMesh uses domain `alarmmesh`. Home Assistant loads it from
`custom_components/alarmmesh`; the Marketplace/HACS installers package only that
integration directory.
All runtime code and translations live there. Tests, documentation, and developer
tooling live outside it and are not runtime dependencies.

| File | Responsibility |
| --- | --- |
| `manifest.json` | Identity, version, configuration support, and metadata |
| `const.py` | Stable domain, display name and source-selection option key |
| `config_flow.py` | Source selection, validation and options for one version-1 entry |
| `__init__.py` | Initial snapshot, source subscription, platform setup and teardown |
| `runtime.py` | Typed observations, shared calculation result and result subscriptions |
| `entity.py` | Common push-only entity identity and subscription cleanup |
| `binary_sensor.py` | Read-only combined smoke overview |
| `sensor.py` | Read-only source availability enum overview |
| `status.py` | Existing pure status interpretation used by the internal runtime |
| `strings.json` | Source UI text |
| `translations/en.json`, `translations/nl.json` | Shipped custom-integration translations |

One entry represents the AlarmMesh service inside a Home Assistant instance, so
`integration_type` is `service`. The current `calculated` IoT classification
makes no claim of a direct cloud or device connection. Revisit that classification
when actual behavior is designed. `single_config_entry` and a stable unique ID
prevent duplicate setup, including confirmation from two open dialogs.

An empty data dictionary is persisted by Home Assistant. Selected entity IDs live
only in `ConfigEntry.options[CONF_SOURCE_ENTITY_IDS]`, where the constant's value
is `source_entity_ids`. Setup uses `ConfigFlow.async_create_entry(options=...)`;
the options flow uses `OptionsFlow.async_create_entry(data=...)` so Home Assistant
persists the replacement options. There is no second copy in `data`.

Both forms use a multiple entity selector filtered to `binary_sensor` entities
with device class `smoke`. Shared backend validation requires a nonempty list of
distinct, valid entity IDs, verifies existence in the local state machine or entity
registry, and rejects other domains, non-smoke entities and AlarmMesh-owned
entities. Ownership is checked against both registry platform and config-entry
domain. No entity IDs or capabilities are inferred from names.

Validation reads only cached identity metadata, never the state value. Registry
`device_class` (user override) takes precedence over current state attributes,
with registry `original_device_class` as fallback. An effective non-smoke device
class is rejected. Thus `unknown`, `unavailable`, or temporarily
absent sources can be selected when smoke identity remains available. This is
identity validation, not smoke interpretation or an availability check.

The options form shows the saved selection. Only successful submission replaces
it; opening, cancelling or submitting invalid input does not update the entry.
Existing empty foundation entries remain valid version-1 entries without a
migration or setup-time validation. Their options form starts empty and requires
at least one valid source to save. `OptionsFlowWithReload` lets Home Assistant
reload the entry after changed options are saved. There is no additional update
listener or second reload mechanism. Invalid or cancelled edits do not reload;
saving unchanged options also leaves the current runtime intact.

## Passive runtime

`AlarmMeshConfigEntry` is `ConfigEntry[AlarmMeshRuntimeData]`. Setup reads only
`entry.options[CONF_SOURCE_ENTITY_IDS]`, defaulting to no sources for foundation
entries. It copies the IDs into a tuple and puts an `AlarmMeshRuntimeData` object
in `entry.runtime_data`, with a `dict[str, SourceStatus]` of latest observations
and the current immutable `StatusResult`. There are no source observations in
`entry.data`, `entry.options` or the process transport hub, and no outcome is restored from
storage. Each setup builds fresh runtime data from the current local states.

| Home Assistant local state | Source status |
| --- | --- |
| `on` | `SMOKE_REPORTED` |
| `off` | `NO_SMOKE_REPORTED` |
| `unknown` | `UNKNOWN` |
| `unavailable` | `UNREACHABLE` |
| Absent or removed entity | `MISSING` |
| Any other state value | `UNKNOWN` |

Setup installs one `async_track_state_change_event` subscription for the selected
IDs before reading the initial snapshot. Installation, snapshot and initial
`evaluate_status` calculation run on the Home Assistant event loop without an
intervening await. An already active source is therefore recognized during setup,
and there is no gap in which a change can be missed. Empty selections do not
subscribe and evaluate to `INDETERMINATE` and `NOT_CONFIGURED`.

The typed, synchronous event callback updates the changed source from the event's
`new_state` (including `None` on removal), then recalculates the result with the
unchanged `evaluate_status` function. `async_set_result` notifies entry-local
listeners only when the combined result changes. Entities never calculate their
own result. Only the explicitly selected IDs are
subscribed. A removed source remains selected as `MISSING` and can reappear under
the same ID. No automatic selection, registry subscription or rename tracking is
introduced.

The helper's unsubscribe callback is registered with `entry.async_on_unload`.
`async_unload_entry` pauses linked execution, then awaits `async_unload_platforms` for `binary_sensor` and
`sensor`, returning its success status. Home Assistant then invokes the source
unsubscribe callback, clears remaining result listeners and clears `runtime_data`.
Entry removal follows the same unload path. Reload removes old subscriptions
before setup takes a new snapshot and installs new subscriptions, including when
options change. Old sources and old runtime objects receive no further updates.

## Read-only overview entities

After the initial calculation, setup awaits `async_forward_entry_setups` for
exactly `binary_sensor` and `sensor`. Both entities read the current shared result
through properties, have `should_poll = False`, and use `async_added_to_hass` to
subscribe before Home Assistant writes their initial state. Each entity registers
its unsubscribe callback with `async_on_remove`. No earlier AlarmMesh state is
restored, and no separate source subscription is created per entity.

| Overview | Shared runtime result | HA state and availability |
| --- | --- | --- |
| Smoke (`BinarySensorDeviceClass.SMOKE`) | `SMOKE_REPORTED` | `on`, available |
| Smoke | `NO_SMOKE_REPORTED` | `off`, available: no smoke reported, not guaranteed safety |
| Smoke | `INDETERMINATE` | `unavailable`; `is_on` is `None`, never `False` |
| Source availability (`SensorDeviceClass.ENUM`) | `COMPLETE` | `complete`, available |
| Source availability | `INCOMPLETE` | `incomplete`, available |
| Source availability | `NOT_CONFIGURED` | `not_configured`, available |

Smoke availability depends only on the smoke result. Active smoke remains `on`
and available beside missing/unreachable sources; the other overview still shows
`incomplete`. The enum describes completeness of source information, not fire
safety. It has no unit or state class. Neither entity adds custom attributes,
counters, diagnostic data, services or actions, and neither creates a device.

Unique IDs are `{entry.entry_id}_smoke` and
`{entry.entry_id}_source_availability`. They do not depend on selected sources,
user-editable names, or state values. Home Assistant generates the entity IDs and
retains registry customizations across reloads/restarts. Names and enum states
have English and Dutch translations. A disabled overview has no result listener;
the remaining overview and the shared source subscription continue normally.

The pinned Home Assistant version can log a platform setup failure without
raising from forwarding. Each platform therefore marks its initialization in the
runtime, independently of whether its entity is enabled. Missing initialization
fails the whole entry setup. Setup exceptions unload any partial platforms;
Home Assistant's setup-error cleanup then runs `async_on_unload`, stopping sources
and clearing result listeners. Normal unload removes entity listeners before
stopping sources. Failed platform unload is reported as failure rather than
claiming a successful teardown.

## Restart and interrupted lifecycle contract

The step-5 regressions retain the implementation above: no production change was
needed for the tested source changes and lifecycle paths. Selected IDs are fixed
strings. A real entity-registry rename removes the old source state; AlarmMesh
marks that selected ID `MISSING`, does not subscribe to the renamed ID and does
not change options. Selecting the new ID in options replaces the subscription.
Repeated switches, including returning to a previous source, create fresh runtime
objects; old runtimes remain detached. Recovering another source cannot clear
an active smoke report.

Disabling the integration unloads it; enabling it takes a fresh snapshot. Both
overview entities may also be disabled together without stopping source tracking.
Re-enabling them uses Home Assistant's existing delayed reload; AlarmMesh adds no
timer. A source report does not expire merely because it has not changed.

On the pinned Home Assistant 2026.10.4 baseline, a failed platform unload returns
failure and leaves the entry in `FAILED_UNLOAD`, which HA marks non-recoverable
for in-process unload/reload. A remaining platform keeps its result subscription;
already removed entities remain detached. Source cleanup is not falsely claimed
while a platform is still active. Neither HA's state nor its recovery checks are
overridden. After the fault is resolved, restarting HA loads the saved entry and
registry into new objects and rebuilds the result from current sources. An entry
reload after `SETUP_ERROR` remains supported, as covered by the existing tests.

The restart tests stop one fixture HA instance, then create a separate instance
and run HA's base bootstrap against the saved configuration and entity-registry
fixtures. They check current `on`, `off` and absent sources, subsequent source
appearance, preserved custom overview identities/names and recovery after failed
unload. This is a storage-based restart simulation, not a real process restart
or a renamed entry-reload test. No AlarmMesh observations are persisted.

The passive source/overview layer makes no device requests, network connections,
polling, timers or background tasks and stores no observations. The optional
executor above adds only bounded HA action tasks. Home Assistant's own Recorder may
record the exposed states according to its configuration. These read-only
overviews do not establish fire protection or alarm readiness.

## Configuration API references

Source selection follows the official [config flow](https://contributors.home-assistant.io/core/integrations/config-flow/),
[options flow](https://contributors.home-assistant.io/core/integrations/options-flow/)
and [entity selector](https://www.home-assistant.io/docs/blueprint/selectors/#entity-selector)
guidance reviewed on 2026-11-11. API behavior is tested against the pinned baseline
in `docs/development.md`; no dependencies or config-entry versions are changed.

Passive tracking follows the official [event helper and cleanup](https://contributors.home-assistant.io/core/integrations/events/)
and [typed runtime data and config-entry lifecycle](https://contributors.home-assistant.io/core/integrations/config-entries/)
guidance, reviewed on 2026-11-11. Reloading options uses the supported
`OptionsFlowWithReload` API in the same pinned test environment.

The overview platforms follow the official [binary sensor](https://contributors.home-assistant.io/core/entities/binary-sensor/),
[enum sensor](https://contributors.home-assistant.io/core/entities/sensor/),
[entity properties and availability](https://contributors.home-assistant.io/core/entities/entity-class/),
[stable unique ID](https://contributors.home-assistant.io/core/quality-scale/entity-unique-id/)
and config-entry platform lifecycle guidance, reviewed on 2026-11-11.

## Verification and pilot evidence

The [compatibility runner](compatibility.md) verifies the retained runtime in fresh
official HA 2026.10.4 and 2026.11.1 containers. It drives HA's actual config/options
flows and simulated local sources, then checks the two entities, current-state
rebuild, stable identities and detached old subscriptions. It is development
tooling, never loaded by the installed integration. The default harness remains
2026.10.4. New linking checks use local mock HA actions/registry metadata, without
loading MQTT/ZHA drivers. No dependencies are added.

[UI simulation acceptance](mvp-acceptance.md), technical compatibility and the
[user-reported pilot](read-only-pilot.md) are different evidence categories.
`complete` only describes usable current HA values; it proves neither recent
radio traffic nor physical smoke detection. No ageing threshold or extra model
property is interpreted. Installation and publication boundaries follow the
[installation guide](installation.md) and [guideline review](guidelines.md).

## Deliberately outside this change

- Automatic entity selection or rename tracking.
- Generic siren controls, silencing, reset, and device test actions.
- Notifications, escalations, user-supplied commands and direct vendor adapters.
- Device discovery, direct device access, polling, timers and coordinators.
- Claims of reliability, certification, or production readiness.

## Future implementation boundaries

Design each capability separately before adding it. Future vendor adapters should
use established Home Assistant entities or explicit capability contracts. Keep
state interpretation separate from actions with physical effects. The passive
runtime defines unavailable handling, fresh startup snapshots and cleanup; future
work still needs its own decisions about stale reports, deduplication, explicit
user intent and background work before adding behavior.

Add tests for each new behavior and failure mode. Any future platform needs its
own setup/unload lifecycle and entry-owned runtime data. Evolve persisted
configuration through explicit migration
when needed; do not change the stable domain or unique ID casually. Nothing in
this foundation authorizes future device actuation.

The [roadmap](roadmap.md) keeps any next capability behind its own assignment.
The historical [review record](review-results.md) maps source/lifecycle coverage
and earlier tooling corrections. Current linked-sounding evidence is separate in
the [linking guide](linked-sounding.md); status semantics, source-option schema and
stable overview unique IDs remain unchanged.
