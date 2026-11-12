# Architecture and scope

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
and the current immutable `StatusResult`. There is no runtime state in
`entry.data`, `entry.options` or `hass.data`, and no outcome is restored from
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
`async_unload_entry` first awaits `async_unload_platforms` for `binary_sensor` and
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

There are no device requests, network connections, polling, timers, background
tasks or AlarmMesh storage of observations. Home Assistant's own Recorder may
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

The [compatibility runner](compatibility.md) uses this unchanged runtime in fresh
official HA 2026.10.4 and 2026.11.1 containers. It drives HA's actual config/options
flows and simulated local sources, then checks the two entities, current-state
rebuild, stable identities and detached old subscriptions. It is development
tooling, never loaded by the installed integration. The default harness remains
2026.10.4; this package changes no product code, persisted schema or dependencies.

[UI simulation acceptance](mvp-acceptance.md), technical compatibility and the
[user-reported pilot](read-only-pilot.md) are different evidence categories.
`complete` only describes usable current HA values; it proves neither recent
radio traffic nor physical smoke detection. No ageing threshold or extra model
property is interpreted. Installation and publication boundaries follow the
[installation guide](installation.md) and [guideline review](guidelines.md).

## Deliberately outside this change

- Alarm grouping, propagation and automatic entity selection or rename tracking.
- Siren activation, silencing, reset, and device test actions.
- Notifications, escalations, automations, and vendor adapters.
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
The [review record](review-results.md) maps current source/lifecycle coverage and
the tooling corrections. This review preserves all production Python modules,
status semantics, configuration schema and stable unique IDs.
