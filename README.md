# AlarmMesh

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/alarmmesh/brand/dark_logo@2x.png">
  <source media="(prefers-color-scheme: light)" srcset="custom_components/alarmmesh/brand/logo@2x.png">
  <img src="custom_components/alarmmesh/brand/logo.png" alt="AlarmMesh â€” read-only smoke reports and source availability for Home Assistant" width="560">
</picture>

Smoke reports and source availability from existing Home Assistant smoke detector
entities, with a local panel for detectors, rooms and groups. This test release adds [optional linked sounding](docs/linked-sounding.md), off by default.
Version 0.1.0-rc.1 also offers [Companion notifications, group
script actions, incident details and reviewed built-in self-test requests](docs/incident-features.md).
New automatic behavior defaults off; existing explicit choices are preserved.
It includes [opt-in maintenance messages, non-executing action
examples and anonymized support diagnosis](docs/maintenance-tools.md).
This beta adds [bounded activity history, optional check reminders,
detector filters and organizational group copies](docs/activity-reminders.md).
The reviewed panel also improves [guided setup, maintenance and incident details](docs/usability-review.md).
The local [morning UI refinement](docs/morning-review.md) simplifies daily status,
source routes, group setup and notification settings without changing execution rules.
The local [notification correction and review](docs/notification-review.md) adds
request diagnosis and safer confirmation/reconnect handling. Actual phone delivery
and the originally reported live failure remain unverified in that historical review.
The current local work adds [per-phone critical smoke alerts and phone setup help](docs/phone-alerts.md).
The user reports a successful critical notification on the tested iPhone and
settings. This does not establish other phones, sounds or Focus modes.
The local [alarm settings and phone observation review](docs/alarm-settings-review.md)
adds one read-only overview, request-bound user observations, change summaries
and an incident timeline. Earlier [critical-alert evidence](docs/critical-notification-review.md)
remains a dated record of simulation, not a physical test.
Open **Maintenance** from the main menu or browse **Detectors → By room**. Explore the silent family drill under **Overview → Silent practice**, follow a smoke alert to its incident, and record detector maintenance. See the [panel guide](docs/panel.md).

Earlier [finishing checks](docs/finish-review.md) remain dated historical evidence.

> AlarmMesh is not a certified fire alarm system and must not replace certified standalone smoke detectors.

## Device support

The **Matter integration** adds HA-only smoke sources, endpoint-bound
optional diagnostics/self-test requests and separate provider/transport labels.
It offers no Matter sounder, stop or mute command. See the [Matter model/function
matrix and setup](docs/matter-support.md) and [current review results](docs/matter-review.md).
The local draft feature preserves selected unsent configuration input through a
full browser reload, without restoring confirmation or bypassing revisions.
Existing [Z-Wave JS smoke entities](docs/zwave-support.md) can also join mixed groups and provide device health information.

This test release includes an offline catalog of **52 converter definitions /
67 model and variant rows**, additional reviewed HA select/siren/switch profiles,
read-only battery/fault/test details and searchable compatibility in the existing
panel. Linking remains off by default; the catalog alone never permits control.
Seven Heiman models connected through Zigbee2MQTT can stop linked sounding after every contributing detector and the sounding detector report clear. See [linked sounding and stopping for Aqara and Heiman](docs/meeklinken-en-stoppen.md).
See [device coverage, prerequisites, upstream gaps and current evidence](docs/device-compatibility.md).
BSD-2 activation requires its broadcast setting to explicitly report off;
AlarmMesh never changes that setting. The original branding, two overview
entities, source-selection schema and smoke rules remain unchanged.

## Release candidate 0.1.0-rc.1

Open **Activity → Smoke and sounder commands** to see which detector reported smoke and when AlarmMesh requested each linked start or stop. Filter by the local start time of your test.

For opt-in testing, enable **Pre-release** in the AlarmMesh Marketplace page and
choose **0.1.0-rc.1**. Back up before updating and follow the restart prompt.
Read the [release notes](docs/releases/0.1.0-rc.1.md) before installing.

## Current status: local panel and two read-only overviews

**Optional linked sounding:** explicit, administrator-confirmed sounder mappings
in groups, with conservative model/provider profiles and separate action results.
Upgrading from beta.1 leaves existing groups unlinked; new groups also default off.
For this installation review, leave linking off and do not change device prerequisites.
Previously enabled groups retain their explicit configuration: switch them off in
AlarmMesh before updating if any are enabled. Installing this beta must not be used
as a physical alarm test.
Back up before updating: the new group format requires the pre-update backup for rollback. See [support, lifecycle and simulation
evidence](docs/linked-sounding.md). Physical linked-sounding acceptance remains unperformed.

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
explicitly mapped, verified existing HA controls. It adds no arbitrary AlarmMesh services or device transport. In the current
version, notifications and script actions require separate opt-in; built-in
self-test requests require a reviewed model/provider contract and confirmation.
Activation-only profiles have no automatic stop; a completed HA action is not audible confirmation.

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

- [Plain-language interface review and five-minute walkthrough](docs/plain-language-review.md)
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

Z-Wave JS rookmelders via bestaande HA-entiteiten: [ondersteuning en grenzen](docs/zwave-support.md).
