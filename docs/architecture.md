# Architecture and scope

## Foundation contract

AlarmMesh uses domain `alarmmesh`. Home Assistant loads it from
`custom_components/alarmmesh`; HACS packages only that integration directory.
All runtime code and translations live there. Tests, documentation, and developer
tooling live outside it and are not runtime dependencies.

| File | Responsibility |
| --- | --- |
| `manifest.json` | Identity, version, configuration support, and metadata |
| `const.py` | Stable domain, display name and source-selection option key |
| `config_flow.py` | Source selection, validation and options for one version-1 entry |
| `__init__.py` | Initial local snapshot and entry-owned state-change subscription |
| `runtime.py` | Typed runtime data and translation of local states to source statuses |
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
unchanged `evaluate_status` function. Only the explicitly selected IDs are
subscribed. A removed source remains selected as `MISSING` and can reappear under
the same ID. No automatic selection, registry subscription or rename tracking is
introduced.

The helper's unsubscribe callback is registered with `entry.async_on_unload`.
`async_unload_entry` returns success; Home Assistant then invokes that callback
and clears `runtime_data`. Entry removal follows the same unload path. Reload
removes the old subscription before setup takes a new snapshot and installs one
new subscription, including when options change. Old sources and old runtime
objects receive no further updates.

There are no exposed platforms, overview entities, devices or services. There
are no device requests, network connections, polling, timers, background tasks,
history or persisted observations. A loaded entry and an internal smoke result
do not indicate fire protection or alarm readiness.

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

## Deliberately outside this change

- Visible overview entities or exposing the internal smoke and availability results.
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

Add tests for each new behavior and failure mode. Add platform forwarding and
unloading only when there are real platforms, and use entry-owned runtime data
when resources exist. Evolve persisted configuration through explicit migration
when needed; do not change the stable domain or unique ID casually. Nothing in
this foundation authorizes future device actuation.
