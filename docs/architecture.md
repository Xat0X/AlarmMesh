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
| `__init__.py` | Asynchronous setup and unload hooks with no side effects |
| `status.py` | Pure status interpretation, not connected to Home Assistant flows or runtime |
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
at least one valid source to save. No options update listener or reload is needed
because no runtime consumes the selection yet.

There are no credentials, platforms, runtime data objects, listeners, background
tasks, device connections, network requests, service registrations, or dependencies
declared by AlarmMesh. Setup and unload return successfully because there are no
resources to acquire or release. A loaded entry and saved selection do not
indicate fire protection or alarm readiness.

## Configuration API references

Source selection follows the official [config flow](https://contributors.home-assistant.io/core/integrations/config-flow/),
[options flow](https://contributors.home-assistant.io/core/integrations/options-flow/)
and [entity selector](https://www.home-assistant.io/docs/blueprint/selectors/#entity-selector)
guidance reviewed on 2026-11-11. API behavior is tested against the pinned baseline
in `docs/development.md`; no dependencies or config-entry versions are changed.

## Deliberately outside this change

- Reading or monitoring smoke reports, runtime aggregation, grouping and propagation.
- Connecting the pure `status.py` calculation to selected entities.
- Siren activation, silencing, reset, and device test actions.
- Notifications, escalations, automations, and vendor adapters.
- Device discovery, polling, event subscriptions, coordinators, and entities.
- Claims of reliability, certification, or production readiness.

## Future implementation boundaries

Design each capability separately before adding it. Future vendor adapters should
use established Home Assistant entities or explicit capability contracts. Keep
state interpretation separate from actions with physical effects. Specify stale
and unavailable state handling, restart behavior, deduplication, explicit user
intent, and cleanup before introducing subscriptions or background work.

Add tests for each new behavior and failure mode. Add platform forwarding and
unloading only when there are real platforms, and use entry-owned runtime data
when resources exist. Evolve persisted configuration through explicit migration
when needed; do not change the stable domain or unique ID casually. Nothing in
this foundation authorizes future device actuation.
