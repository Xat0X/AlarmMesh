# AlarmMesh

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/alarmmesh/brand/dark_logo@2x.png">
  <source media="(prefers-color-scheme: light)" srcset="custom_components/alarmmesh/brand/logo@2x.png">
  <img src="custom_components/alarmmesh/brand/logo.png" alt="AlarmMesh — read-only smoke reports and source availability for Home Assistant" width="560">
</picture>

Smoke reports and source availability from existing Home Assistant smoke detector
entities, with a local panel for detectors, rooms and groups. The local review
build adds [optional linked sounding](docs/linked-sounding.md), off by default.

> AlarmMesh is not a certified fire alarm system and must not replace certified standalone smoke detectors.

## Test release: 0.1.0-beta.1

For opt-in testing, enable **Pre-release** in the AlarmMesh Marketplace page and
choose **0.1.0-beta.1**. Back up before updating and follow the restart prompt.
Read the [release notes](docs/releases/0.1.0-beta.1.md) before installing.

## Current status: local panel and two read-only overviews

**Unreleased local extension:** explicit, administrator-confirmed sounder mappings
in groups, with conservative model/provider profiles and separate action results.
This is not part of the published beta below. See [support, lifecycle and simulation
evidence](docs/linked-sounding.md). All physical acceptance remains unperformed.

The interface adds **AlarmMesh** to the Home Assistant sidebar for
administrators: overview, detectors and details, HA rooms, and persistent
organizational groups. It uses the signed-in HA session and needs no YAML,
resource installation, Node on the HA host or separate server. See the
[panel user guide](docs/panel.md). Release validation is separate from earlier hosted
CI or installer acceptance; those dated results remain in the acceptance matrix.

Source selection, passive local tracking and the two read-only overview entities
remain available with linking off. The supplied artwork is unchanged.
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

No smoke reported is not a guarantee of safety. Optional linking calls only
explicitly mapped, verified existing HA controls. It does not add AlarmMesh
services, notifications or device tests. Activation-only profiles have no automatic
stop; a completed HA action is not audible confirmation.

## Install and select sources

On **HA 2026.11+**, use the built-in **Settings > Marketplace > Add from link**
with `https://github.com/Xat0X/AlarmMesh`. On the older **2026.10.4** baseline,
use HACS's **Custom repositories**, type **Integration**, with the same URL.
See [installation, updates and removal](docs/installation.md) for the supported
steps and restart prompts. Adding a repository does not mean public catalog
admission or Home Assistant approval.

After installation, in **Settings > Devices & services > Add integration**,
select **AlarmMesh**, choose an existing smoke detector entity, and submit the
form. Check both overviews: an explicit `off` source gives smoke `off` and source
availability `complete`. More sources can be selected. Only one configuration
can be added.
Use **Configure** on the integration entry to view or replace the selection.
Saving changed options reloads the integration to follow the new selection.
Closing the form or submitting invalid input keeps the saved selection unchanged.
Remove the integration entry to stop tracking and remove its configuration;
uninstall through the installer separately to remove the installed files.

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
according to its own configuration; AlarmMesh adds no observation history.
Group names, stable IDs, member references, optional explicit linking settings
and an edit revision are persisted in HA storage, separately from source selection.
Tracking and overview subscriptions stop on unload or removal.
AlarmMesh does not directly query devices, poll sources, or create network
connections. The overviews do not establish alarm readiness.

Do not add `alarmmesh:` to `configuration.yaml`; configuration is UI-only.
Repository metadata supports custom-repository installation. No catalog
approval is claimed. Development does not require an
installer; use the isolated environment described below.

## Development and design

- [Current acceptance matrix: hosted CI, fresh UI and open checks](docs/acceptance-matrix.md)
- [Local package, file-update and snapshot-recovery checks](docs/release-package.md)
- [Disposable Marketplace and HA backup acceptance](docs/installer-acceptance.md)
- [Development setup and checks](docs/development.md)
- [Installation, updates and removal](docs/installation.md)
- [Reproducible compatibility checks: 2026.10.4 and 2026.11.1](docs/compatibility.md)
- [Isolated local MVP acceptance environment and results](docs/mvp-acceptance.md)
- [Read-only pilot and passive observation protocol](docs/read-only-pilot.md)
- [Architecture and scope](docs/architecture.md)
- [Guidelines and publication readiness](docs/guidelines.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Release readiness and draft release text](docs/release-readiness.md)
- [Changelog](CHANGELOG.md) and [roadmap](docs/roadmap.md)

The repository includes tests, lint/format configuration, a Linux development
container, and GitHub workflows for tests and hassfest. No hardware access or
Home Assistant credentials are needed for the tests.

The optional acceptance environment uses HA 2026.10.4 on localhost port 8124
with simulated sources only. The twelve documented UI acceptance scenarios were
executed on 2026-11-11, including a real container restart. Results and limitations
are recorded in the acceptance guide; physical-device validation is outside scope.
The real-device pilot records user-reported installation and current status on
Core 2026.11.1 separately. Physical smoke transitions, connection loss/recovery
and a production restart remain unvalidated.
