# Changelog

## Unreleased

- Block Bosch BSD-2 linked activation unless its same-device broadcast switch
  explicitly reports off. Recheck before dispatch and invalidate earlier broader
  assignments; never change the device setting automatically.

- Add a reviewed offline catalog of 52 definitions / 67 model and variant rows,
  separate Zigbee2MQTT/ZHA assessments and searchable panel compatibility.
- Add reviewed Heiman, Aqara ZHA, IAS, Bosch and ShinaSystem HA action contracts,
  activation only unless the existing PLUS MQTT stop contract applies. Preserve
  published bindings, source options, group identities and default-off linking.
- Show cached battery, fault, self-test and firmware details without inferring
  radio contact; show only current members in group target assignment.
- Accept actual HA siren IntFlag feature bitmasks while rejecting booleans; the
  regression was observed failing before correction. Do not adopt non-idle manual
  control states. Preserve per-target incident deduplication and all status tests.
- Block positively non-smoke/AlarmMesh-owned replacement origins from starting
  or releasing action incidents; retain latched smoke through identity loss.
  The shared read-only result and all original status rules stay unchanged.
- Extend both compatibility runs with a private synthetic MQTT broker, actual HA
  discovery/action payload checks and offline real ZHA action/quirk serialization.
  See [coverage, limitations and current evidence](docs/device-compatibility.md).

- Correct Dutch catalog text and label the activation filter as external sounder;
  verify the catalog UI with 16 simulated sources, native confirmation/error
  handling, reconnect and phone/tablet layouts. Keep screenshots local.

No physical tests, live device access or new release/publication are claimed.


## 0.1.0-beta.2 — 2026-11-14

- Add optional, administrator-confirmed group sounder mappings, default off, with
  registry-bound MQTT/ZHA capability profiles and independent incident/action results.
- Deduplicate bounded HA action requests; preserve independent smoke origins through
  missing information, prevent old runtime dispatch and restrict automatic stopping
  to owned Heiman automation-only activations. Aqara/SMSZB-120 are activation-only.
- Migrate old group payloads in memory without enabling linking or rewriting on load.
  Preserve source options, overview identities, status calculation and original tests.
- Add mocked profile/lifecycle/storage/authorization tests, confirmation DOM tests
  and mixed-provider scenarios to both existing compatibility runs. Add a separate
  simulated UI environment. See [scope, support and evidence](docs/linked-sounding.md).

- Fix per-target incident deduplication: a new incident can reactivate its target
  while an unrelated group remains active; retain overlap and retry suppression.
- Publish an opt-in linked-sounding test release; existing beta.1 and new groups
  keep linking off. See [update and rollback instructions](docs/releases/0.1.0-beta.2.md).

No physical sounder/detection validation or production installation was performed.
Dependencies and minimum HA version remain unchanged.

## 0.1.0-beta.1 — 2026-11-13

First opt-in interface test release. See [release notes](docs/releases/0.1.0-beta.1.md)
for update instructions and known limits.

- Select existing HA smoke binary sensors through configuration/options.
- Show smoke reports and source-information completeness in two overview entities.
- Add the administrator sidebar panel: overview, detectors/details, HA rooms and
  persistent organizational groups with atomic writes and revision conflicts.
- Preserve existing source selection, overview identities and config-entry schema.
- Include Dutch/English text, supplied branding and phone/tablet/light/dark layouts.
- Fill the screen background, align icon sizes and simplify group-page copy.
- Validate backend/frontend behavior and exact HA 2026.10.4 / 2026.11.1 compatibility.

No siren control, notifications, alarm propagation, mute/reset or device tests.
No smoke reported is not a safety guarantee. This beta does not replace certified
standalone smoke detectors. Historical development and acceptance evidence is
retained under docs/; physical-device and production-upgrade acceptance remain
separate from technical simulation checks.
