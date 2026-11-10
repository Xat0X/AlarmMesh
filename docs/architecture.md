# Architecture and scope

## Foundation contract

AlarmMesh uses domain `alarmmesh`. Home Assistant loads it from
`custom_components/alarmmesh`; HACS packages only that integration directory.
All runtime code and translations live there. Tests, documentation, and developer
tooling live outside it and are not runtime dependencies.

| File | Responsibility |
| --- | --- |
| `manifest.json` | Identity, version, configuration support, and metadata |
| `const.py` | Stable domain and display name |
| `config_flow.py` | Confirmation form and one empty version-1 entry |
| `__init__.py` | Asynchronous setup and unload hooks with no side effects |
| `strings.json` | Source UI text |
| `translations/en.json`, `translations/nl.json` | Shipped custom-integration translations |

One entry represents the AlarmMesh service inside a Home Assistant instance, so
`integration_type` is `service`. The current `calculated` IoT classification
makes no claim of a direct cloud or device connection. Revisit that classification
when actual behavior is designed. `single_config_entry` and a stable unique ID
prevent duplicate setup, including confirmation from two open dialogs.

An empty data dictionary is persisted by Home Assistant. There are no credentials,
options, platforms, runtime data objects, listeners, background tasks, device
connections, network requests, service registrations, or dependencies declared
by AlarmMesh. Setup and unload return successfully because there are no resources
to acquire or release. Home Assistant reporting this entry as loaded only means
the skeleton loaded; it does not indicate fire protection or alarm readiness.

## Deliberately outside this change

- Smoke detection, alarm state aggregation, grouping, and propagation.
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
