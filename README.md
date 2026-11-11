# AlarmMesh

Vendor-independent smoke alarm linking, monitoring and testing for Home Assistant.

> AlarmMesh is not a certified fire alarm system and must not replace certified standalone smoke detectors.

## Current status: two read-only overviews

The description above includes future project direction. The current version
offers source selection, passive local tracking and two read-only overviews.
AlarmMesh lets you select existing smoke detector entities during setup and
replace that selection later through the integration options. Select at least
one `binary_sensor` with device class `smoke`. AlarmMesh reads their current local
Home Assistant states when loaded and follows changes to those selected IDs.
An already active smoke report is recognized immediately on loading. The shared
in-memory result is shown by exactly two entities, with no physical device entry:

- A smoke binary sensor: `on` means smoke reported; `off` means **no smoke
  reported** ("geen rook gemeld"). An indeterminate result is `unavailable`, never
  `off`. A smoke report remains `on` even if another source is unreachable or
  missing.
- A source availability enum-sensor: `complete`, `incomplete` or `not_configured`.
  This sensor remains available when sources are unreachable. It describes
  completeness of source information, not fire safety.

No smoke reported is not a guarantee of safety. AlarmMesh does not link alarms,
activate sirens, send notifications, or perform device tests. There are no alarm
actions or AlarmMesh services.

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
sources, the smoke overview is `unavailable` and source availability is
`not_configured`. Selected IDs are fixed: renamed sources are not followed
automatically. Home Assistant generates the overview entity IDs; users can
customize their names and IDs. Their identities stay stable across restarts,
reloads and source-selection changes. Either overview can be disabled without
stopping the other.

`on` means smoke reported, `off` explicitly means no smoke reported, `unknown`
remains unknown, and `unavailable` means unreachable. An absent or removed entity
is missing; unexpected state values are unknown. Any smoke report takes
precedence, while incomplete source availability is shown separately. AlarmMesh
does not store or restore observations as current truth; every load starts from
Home Assistant's current local states. Home Assistant may record entity history
according to its own configuration; AlarmMesh adds no history or storage.
Tracking and overview subscriptions stop on unload or removal.
AlarmMesh does not directly query devices, poll sources, or create network
connections. The overviews do not establish alarm readiness.

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
