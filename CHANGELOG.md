# Changelog

## 0.1.0-beta.11 — 2026-11-17

- Preserve newer phone settings and active confirmations when recipient refresh replies arrive late, after reopening or reconnecting.

- Distinguish an AlarmMesh request deadline from a definitive provider failure;
  interrupted notification requests remain unknown and are never automatically replayed.
- Bind notification-test confirmation to the current service and message context,
  reconcile lost replies by request ID, and retain bounded test receipts in activity.
- Show phone availability, automatic-send readiness, safe list refresh, actual test
  previews and shared non-executing route decisions in Dutch and English.
- Verify the real HA legacy notify service adapter with a local recording transport.
  See [notification review and evidence limits](docs/notification-review.md).

## 0.1.0-beta.10 — 2026-11-17

- Offer source recovery directly beside missing, unavailable or identity-changed sources; verify actual memberships after interrupted saves without automatic retry.
- Simplify phone-first navigation: one first-use action, a compact overview and
  named missing sources in the status card. Keep smoke visible inside all dialogs.
- Put detector alarm routes and notification settings within two navigation clicks;
  keep optional group outputs and technical details behind explicit disclosures.
- Improve source recovery steps, duplicate-name identification, notification preview,
  touch targets, keyboard focus and narrow-screen layout in Dutch and English.
- Preserve beta.9 recovery reconciliation, confirmations, permissions and status rules.
  See the [local morning review](docs/morning-review.md) for evidence and limits.

## 0.1.0-beta.9 — 2026-11-17

- After a lost recovery acknowledgement, show actual group memberships on reconnect without resubmitting.

- Add read-only per-detector alarm routes across groups, with shared sounder targets,
  global recipients and ordered scripts. Add staged source recovery through existing
  HA selection and atomic membership transfer without inherited control authority.
- Keep live smoke visible inside recovery dialogs and retain recovery choices across
  disconnects without automatic saving.
- Add fresh self-test-dialog data review with new acknowledgement and no dispatch.
  See [local review evidence](docs/route-recovery-review.md).

## 0.1.0-beta.8 — 2026-11-16

- Add Z-Wave JS smoke sources and device health details in mixed groups. Z-Wave sounder control and remote self-test are unsupported.

- Complete eight Matter browser combinations and actual reload-draft/virtual-self-test
  flows. Correct readable Matter model names, EN/NL detail labels, standalone test
  cancellation and long-name wrapping; preserve the original status rules.

- Add HA-registry-only Matter sources, per-endpoint optional battery/fault/end-of-service,
  test/interconnect/CO/mute information, provider/transport labels and NL/EN setup help.
  Review HS1SA-M, S1-M, MS-1, MSC-1 and the distinct MS-1 Interlink variant separately.
- Reuse mixed-provider groups and exact HA self-test buttons with mocked I/O checks
  on 2026.10.4/2026.11.1. No Matter sounder, stop, mute, controller or dependency added.
  Forwarded interconnect remains visible without becoming an independent output origin.
- Pin Matter source identities; block execution after replacement until explicit
  administrator review. Keep invalid saved CO-only selections unknown rather than smoke.
- Preserve bounded local unsent group/settings/reminder drafts across browser reload,
  with original revisions, identity checks and fresh confirmations. No autosubmit.
- See [current results and remaining visual/physical acceptance](docs/matter-review.md).
  Existing smoke rules, 79 status tests, identities and branding stay unchanged.

## 0.1.0-beta.7 — 2026-11-16

- Complete eight language/theme/device browser dialog combinations; correct detector
  search and reminder wording, exact reminder confirmation, copy-field styling and
  explicit self-test result filters. Preserve offline drafts until a full page reload.

- Add bounded local activity observations with request correlations, filters and
  detail links. Quiet baseline, 30-day/1,000-event retention and explicit incomplete
  history preserve the independent incident executor and its receipts.
- Add separate default-off calendar check reminders with explicit recipient/date
  confirmation, later/handled, bounded repeat preferences and durable one-attempt
  receipts. Handling never changes a device self-test result.
- Add combined detector filters, group-member search/counts and previewed group
  copies that cannot inherit linked-sounder or script authority. Preserve branding,
  HTTP request IDs, self-test correlation and both overview identities.
- Extend EN/NL UI, real HA fixture/mock tests and exact compatibility scenarios.
  See [behavior and current evidence](docs/activity-reminders.md). No physical
  output, version change or publication is part of this work.

## 0.1.0-beta.6 — 2026-11-15

- Complete the eight maintenance/example/diagnosis visual combinations and real
  five-minute mock outage flow. Distinguish unassessed stop support for blocked
  preview targets and label recovery receipts as requests, with EN/NL regressions
  observed failing before correction. No physical outputs tested.

- Add separate default-off maintenance phone settings, current device-bound
  battery/fault/outage conditions, bounded durable receipts, quiet startup,
  configurable observation delay, optional confirmed recovery and cleanup.
- Add read-only group action examples sharing execution/receipt decisions, and
  an admin-only allowlisted anonymized diagnosis preview/copy route. No example
  can issue commands or grant authority. Existing branding/navigation retained.
- Extend Dutch/English forms, mock fixtures, privacy/lifecycle tests and both
  exact HA checks. See [behavior and evidence](docs/maintenance-tools.md).
- Generate confirmation request IDs with cryptographically secure random bytes
  supported on local HTTP, rather than secure-context-only randomUUID. Preserve
  exact-target confirmation, request ownership and no automatic retries. Report
  unavailable secure randomness explicitly and show test warnings only once.
  The HTTP-like regression failed before correction; no physical outputs tested.

## 0.1.0-beta.5 — 2026-11-15

- Complete the eight EN/NL light/dark phone/tablet visual checks for setup,
  maintenance, long-name dialogs and incident details. Reset reading position
  when navigating between panel pages while preserving it on live state updates;
  add a regression observed failing before correction. Simulation only.

- Correct review findings: changed smoke-source identity now prevents a misleading
  configured setup state; conflicting battery units stay unknown as percentages.
  Preserve raw diagnostics, smoke rules and existing execution behavior.
- Expand the existing setup guide to seven resumable steps derived from actual
  configuration, with configured, optional-off, unsupported and attention states.
  Keep all target confirmations and automation defaults unchanged.
- Add a compact maintenance view using proven same-device HA metadata, explicit
  unknown values, a display-only 20% battery warning, configuration issues and the
  retained self-test request. No maintenance notifications or device queries.
- Explain incident origins, pending explicit clearance, request types and recorded
  recovery without inventing event order or timestamps. Allow explicit removal of
  saved notification recipients; cancellation preserves the stored configuration.
- Extend Dutch/English text, touch targets, wrapping and existing simulation
  controls. See [current checks and completed visual review](docs/usability-review.md).

## 0.1.0-beta.4 — 2026-11-15

- Complete visual simulation checks for group actions, smoke/outage/recovery and
  built-in self-test activity, timeout and explicit results; see the
  [visual flow review](docs/visual-flow-review.md). Clear obsolete confirmation
  warnings and align long incident rows with a fixed icon column. No real outputs.

- Finish group/script editors: preserve unavailable or changed assignments until
  explicit replacement/removal, lock the reviewed configuration, reject offline
  confirmation and retain drafts through reconnect. Show names/rooms before IDs.
- Show live self-test results only for the matching request, and show involved
  groups plus uncleared unknown origins even when notifications/scripts are off.
  Add two-way script ordering, clearer previews and stronger default dialog contrast.
- Extend the existing package/update runner from published beta.3 to this working
  tree, including fresh installation, process restart, explicit settings, corrupt
  storage and stopped-file recovery. See the completed isolated visual flow review; physical acceptance remains open.

- Fix self-test request ownership: an expired queued task cannot borrow a later
  confirmation, dispatch, alter its successor's status/storage/watchers or return
  its successor's result. Bind callbacks and deadlines to individual requests;
  retain identity, authorization, smoke/conflict checks and cancellation cleanup.
- Correct setup/options text in English and Dutch for optional notifications,
  incident scripts and separately confirmed supported self-tests.

- Add separate group incident-origin selection without replacing the existing
  linking engine, deduplication, Bosch safeguards or ownership-limited stopping.
- Add default-off Companion notification settings and ordered per-group HA script
  start/recovery actions, server-validated targets, explicit test confirmation,
  durable bounded receipts, error isolation and no automatic replay after reload.
- Add capability-gated built-in self-test requests through reviewed existing HA
  buttons/selects. Keep real smoke, activity and explicit device result separate;
  interrupted/no-result tests are unknown, never passed.
- Add Settings and incident details in Dutch/English, preserved offline drafts,
  receiver/script availability and exact-target confirmations. Preserve the local
  guided setup/configuration checks below and original branding.
- Extend isolated backend/DOM and both exact-HA compatibility checks, event-only
  script/mock-phone simulation, and reviewed package inventory. No real device,
  phone, cloud or physical self-test was used. Later isolated visual checks are recorded in the [visual flow review](docs/visual-flow-review.md); physical acceptance remains open.

- Add read-only guided setup and contextual group configuration checks, with
  source/mapping/prerequisite explanations and existing navigation only. Keep
  explicit confirmation, action execution and default-off behavior unchanged.

## 0.1.0-beta.3 — 2026-11-14

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

Opt-in catalog test release. See [installation and limits](docs/releases/0.1.0-beta.3.md).
Validation: 367 backend tests, 20 frontend tests and, on each tested HA version,
20 runtime plus 14 driver checks. No physical tests or live device access performed.


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

### 0.1.0-beta.8 — 2026-11-16

- Add Z-Wave JS smoke sources and device health details in mixed groups. Z-Wave sounder control and remote self-test are unsupported. — Z-Wave JS sources

- Add cached Z-Wave JS smoke sources, provider filtering, exact-device maintenance and setup help.
- Reject overridden CO/heat/diagnostic sources, including invalid saved selections.
- Add registry-only simulator and regression tests; no Z-Wave sounder, self-test or network commands.
