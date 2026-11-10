# AlarmMesh

Vendor-independent smoke alarm linking, monitoring and testing for Home Assistant.

> AlarmMesh is not a certified fire alarm system and must not replace certified standalone smoke detectors.

## Current status: internal passive source tracking

The description above is the project direction, not functionality available today.
AlarmMesh lets you select existing smoke detector entities during setup and
replace that selection later through the integration options. Select at least
one `binary_sensor` with device class `smoke`. AlarmMesh reads their current local
Home Assistant states when loaded and follows changes to those selected IDs.
Source statuses and the combined smoke/availability result are kept internally
in memory. An already active smoke report is recognized immediately on loading.
No overview entities or actions are exposed. AlarmMesh does not link alarms,
activate sirens, send notifications, or perform device tests.

## Select sources

Use an isolated development Home Assistant instance (baseline: 2026.10.4).
Copy `custom_components/alarmmesh` into its configuration directory under
`custom_components/alarmmesh`, then restart Home Assistant. In **Settings >
Devices & services > Add integration**, select **AlarmMesh**, choose one or more
smoke detector entities, and submit the form. Only one configuration can be added.
Use **Configure** on the integration entry to view or replace the selection.
Saving changed options reloads the integration to follow the new selection.
Closing the form or submitting invalid input keeps the saved selection unchanged.
Remove the integration entry to stop tracking and remove the configuration.

Temporarily `unknown` or `unavailable` detectors can remain selected when Home
Assistant's entity metadata identifies them as smoke detectors. Duplicate,
nonexistent, non-smoke and AlarmMesh-owned entities are rejected. Existing empty
foundation configurations still load; open **Configure** to add sources. Without
sources, the internal result is indeterminate and not configured. Selected IDs
are fixed: renamed entities are not followed automatically.

`on` means smoke reported, `off` explicitly means no smoke reported, `unknown`
remains unknown, and `unavailable` means unreachable. An absent or removed entity
is missing; unexpected state values are unknown. Any smoke report takes
precedence, while incomplete source availability remains visible in the internal
result. These observations are not stored or restored; every load starts from
Home Assistant's current local states. Tracking stops on unload or removal.
AlarmMesh does not directly query devices, poll sources, or create network
connections. Internal tracking does not establish alarm readiness.

Do not add `alarmmesh:` to `configuration.yaml`; configuration is UI-only.
HACS metadata is included, but this is not a published or approved HACS release.
There is no need to install it through HACS to develop the project.

## Development and design

- [Development setup and checks](docs/development.md)
- [Architecture and scope](docs/architecture.md)
- [Guidelines and publication readiness](docs/guidelines.md)

The repository includes tests, lint/format configuration, a Linux development
container, and GitHub workflows for tests and hassfest. No hardware access or
Home Assistant credentials are needed for the tests.
