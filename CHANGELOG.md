# Changelog

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
