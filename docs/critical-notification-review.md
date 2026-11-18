# Critical phone alert and UX review

Review started 2026-11-17 on clean `main`, commit
`7061cd0c17122e53c717708080fb78557551c9fa`, manifest `0.1.0-beta.11`.
All changes are local and uncommitted. No production installation or actual
phone was accessed. New automatic settings remain off. Earlier review results
are historical; this document records this change separately.

## Implemented

Per-recipient iOS/Android profiles, trustworthy registration metadata or explicit
user platform choice, reviewed iOS filenames/default/imported filename, critical
volume, Android alarm channel and TTL warning, platform-specific permission help.
Preview, explicit test and smoke delivery share one validated backend plan.
New-profile confirmations include request ID and the concrete profile/context.
Recovery, maintenance and reminders remain ordinary. Existing beta.11 rows
retain exactly their ordinary settings. Mixed recipients fail independently.

The setup route starts with the phones, reveals relevant controls and ends with
save/confirmation. Tests require separate confirmation and never serve as sound
proof. The settings page summarizes each phone's profile. Missing or replaced
phones are retained with an actionable error. After a lost save response, the
user can verify saved choices through a read-only request; the form stays intact,
the resolved error disappears and saving is disabled until reopening.

## Regressions and observed corrections

| Finding | Before | Correction and evidence |
|---|---|---|
| No platform-specific critical request | Two real-HA-adapter cases failed | iOS sound object and Android alarm fields; `config/critical-review/before.log`, `profiles-final.log` |
| Saving while smoke was already active could trigger a notification | Reproduction failed | Persist current-origin suppression before committing settings; fresh off/on remains eligible. Same before/after logs. |
| Lost save acknowledgement left no UI verification route | New frontend regression failed | Read-only current-settings comparison, no resubmission; `save-reconcile-before.log`, `save-reconcile-after.log`, `save-verified.json` |
| Verified save still displayed its old error and offered save again | Regression failed | Clear resolved error and disable save until reopening; `save-status-before.log`, `frontend-reviewed.log` |
| New sound controls appeared as tiny native controls due to old cached assets | Actually observed in initial screenshots | Version all changed frontend assets; final controls at least 44px high. All eight screenshots repeated and inspected. |

No assertions in existing tests were weakened. `status.py` and its 79 tests,
manifest version, requirements and CI are unchanged. Additive profile fields
are not readable by older beta.11 code: rollback needs a pre-update backup.

## UX audit

| User task | Issue / retained behavior | Concrete change or check |
|---|---|---|
| First use / empty phone list | No phone must not look configured | Empty state directs to Companion setup; layout fixture viewed. Existing first-use source action retained. |
| Normal status, smoke, unavailable sources | Complete must not imply hardware health | Existing named missing-source route retained; mock outage investigated from overview; smoke seen inside open phone form. |
| Find a detector / duplicate names | Identity and room must remain discoverable | Existing filters, device details and identity hints retained; device and route screens inspected. |
| Create groups / optional actions | Optional outputs must not complicate naming | Created a group with name/member; advanced settings initially closed and outputs off. Existing edit/copy regression coverage retained. |
| Configure phones | Flat service list lacked platform/sound | Recipient-first route, platform metadata, per-phone sound, relevant help, quiet save, separate test. |
| Diagnose missing sound | Accepted request could be mistaken for audible success | Explicit unverified phone status; last request outcome; iOS permissions and Android channel/volume/DND explained separately. |
| Save during reconnect | Generic error left uncertain saved state | Explicit read-only saved-choice verification, retained form, no automatic resubmission. |
| Source recovery / conflicts | Must not accidentally transfer authority | Prepared four-step recovery; unchecked confirmation blocked the operation; no source transfer executed. |
| Self-test, battery, maintenance | Unknown must never imply a physical pass | Existing caveats retained; historical unknown self-test remains unknown. No physical self-test executed. |
| Activities / incidents | Historical receipts must not look current smoke | Both screens inspected; separate current smoke, request results and unconfirmed physical outcome retained. |
| Keyboard, narrow screen, long names | Small sound controls and potential overflow | 44px controls, focus rings, wrapping labels and scrollable dialogs; desktop, keyboard return and narrow reflow checked. |

No broad backend refactor or new device control was needed. Group edit/copy and
self-test execution were covered by existing automated regressions, not claimed
as newly executed interactive physical tests.

## Visual and interactive evidence

Only `alarmmesh-incident-ui-316a03fe45be`, HA **2026.11.1**, localhost **8131**.
Verified labels, localhost binding, read-only integration and simulation mounts,
mock notify handlers and ignored metadata-only phone registrations. No real
Companion transport loaded. Browser session used the existing simulator account.

All eight combinations were captured and visually inspected: NL/EN x light/dark
x phone 390x844/tablet 1024x768. iOS fields and Android help were inspected in each.
Desktop 1440x900, keyboard focus/return, long names, empty list and 512x384 reflow
were also viewed. The latter is a narrow CSS viewport, not a physical browser-zoom
or assistive-technology certification. Panel language used a browser fixture;
HA theme used its normal theme event. The outer HA shell remained Dutch.

Local screenshots only: `config/critical-review/screenshots/`. The outer account
sidebar is masked in final matrix captures. No screenshots, account storage or
runtime results are added to Git. Useful files:

- `contact-ios-final.png`, `contact-android-help-final.png`: all eight combinations.
- `contact-broad.png`: overview, devices, empty groups, maintenance, activity,
  incidents, focus, reflow, long names and empty recipients.
- `save-verified.png`: successful read-only reconciliation after lost reply.
- `smoke-in-form.png`, `manual-timeout.png`, `stale-confirmation.png`:
  actual mock interactive scenarios, separate from DOM unit tests.

`flows.json`, `beta11-regression-flows.json`, `usability.json`, `matrix.json` and
`save-verified.json` record the performed browser checks. They include two mixed
critical mock requests, failure, deadline unknown without retry, missing service,
invalidated acknowledgement, draft/resume, list refresh, real browser disconnect,
reconciliation of the same test request, lost save reply, and mock incident/off
recovery with no false unavailable recovery. No output was inferred from visuals:
the simulator's allowlisted counter recorded the final critical fields.

## Validation

Final results and paths are recorded below after completion. The initial full
route passed 584 backend and 101 frontend tests; added maintenance/reminder
isolation cases raised backend coverage to 586, and save reconciliation raised
frontend coverage to 102. These historical counts do not substitute for the
final run. New phone-profile file contains 31 backend cases, including real
HA notify adapter, invalid fields, mixed failures, reload, beta.11 storage,
ordinary recovery/maintenance/reminders and request-bound confirmation.

| Check | Actual environment | Result | Local evidence |
|---|---|---|---|
| Full backend suite, including 79 unchanged status cases | Linux Python 3.14.10, HA 2026.10.4 | **586 PASS** | `config/validation/79b93e15f7af47b1bd9644653f042996/pytest.xml`, `baseline.log` |
| Full frontend suite | Node 24.22.1 | **102 PASS** | Same validation directory, `frontend.log` |
| Ruff lint and format | Fixed development dependencies | **PASS** | Same directory, `baseline.log` |
| Official hassfest | Official container | **PASS** | Same directory, `hassfest.log` |
| PowerShell syntax/tooling faults and Compose | Existing validation route | **PASS** | `config/critical-review/validation-reviewed-console.log` |
| Compatibility | Requested and loaded HA 2026.10.4 | **PASS** | `config/compatibility/2026.10.4/ec16c00c4dff4c1da45931b42d02a035/` |
| Compatibility | Requested and loaded HA 2026.11.1 | **PASS** | `config/compatibility/2026.11.1/d6aee617d321493d924a3d6c7e5d4d9e/` |
| File update, fresh process restart, fresh install/removal and stopped-file restore | HA 2026.11.1 | **PASS** | `config/update-checks/2026.11.1/4a752b89311a4ab9b41f8340e1083ab8/update-result.json` |
| Two deterministic local packages, 42 integration files | Current reviewed source | **PASS** | `config/release-packages/critical-reviewed-a/inventory.json`, `critical-reviewed-b/inventory.json` |
| Eight visual combinations and interactive mock scenarios | Chromium, HA 2026.11.1 on 8131 | **PASS, visually inspected** | `config/critical-review/` JSON reports and screenshots described above |
| Final calm state | Five off sources, 107 off helpers, automatic outputs off | **PASS** | `config/critical-review/final-state.json` |
| Diff, protected files, preserved assertions, local links and targeted privacy review | Current working tree | **PASS** | `config/critical-review/scope-check.json`; `git diff --check` |
| Actual audible critical alerts, phone permissions, physical smoke/sounder tests | Real phones/devices | **NOT EXECUTED** | Outside authorization; needs separate physical acceptance |

Final route: `pwsh -NoProfile -File ./dev/validate.ps1`, overall PASS, cleanup PASS.
These are local checks, not a hosted CI run for this uncommitted change.
Package SHA-256: `e27692695cf51b1b66c1c10f53de9bb3324a22c8bcd1daa396da9d5babd5e9fc`.
The final result annotations were added after testing; integration bytes still
match the tested package inventory.

The update driver uses the reviewed earlier catalog revision `b2f3d7`, isolated
installation copies, a new HA process and a copy of normally stopped test files.
It is a **file-update/restart and stopped-file recovery test**, not Marketplace,
HACS or the Home Assistant backup feature. Beta.11 ordinary storage preservation
is additionally covered by a direct storage regression and real simulator
restart. Deterministic ZIPs are local test packages, not published releases.

## Morning walkthrough (under five minutes)

Open `http://127.0.0.1:8131/alarmmesh` with the existing simulator account.
Go to Settings, open phone settings, expand iPhone and Android and inspect their
sound controls and **Why can I not hear it?** help. Automatic notifications are
off; selecting or viewing a profile makes no sound. Review the saved profile
summary and the separate confirmed test route without needing to execute it.
Then view detector alarm routes, maintenance and activity to see the distinction
between reported source state, request outcomes and unknown physical results.

The final simulator has five off sources, 107 off helpers, no groups, all automatic
outputs/reminders off and no running self-test. An earlier unknown self-test result
is preserved honestly. Stop only this simulator with:
`pwsh -NoProfile -File dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop`.
Configuration is retained; other ports/environments remain untouched.

## Remaining phone acceptance

The user reports ordinary delivery, but critical alert delivery, audible sound
in silent/DND modes, phone permissions, imported sound availability and actual
Android channel behavior have **not** been physically tested. A future explicitly
authorized phone check must confirm those on each phone. No live installation,
real notification, detector, sounder or external action was used. Compatibility
checks use their own isolated test broker; no production MQTT or radio was accessed.
Battery/complete status remains no physical-health guarantee; a self-test is not
proof of smoke detection. Nothing was committed, pushed, tagged or published.


## Exact changed files

- `custom_components/alarmmesh/notification_profiles.py`
- `docs/critical-notification-review.md`
- `docs/phone-alerts.md`
- `tests/test_phone_profiles.py`
- `CHANGELOG.md`
- `README.md`
- `custom_components/alarmmesh/automation.py`
- `custom_components/alarmmesh/effects.py`
- `custom_components/alarmmesh/frontend/drafts.js`
- `custom_components/alarmmesh/frontend/panel.css`
- `custom_components/alarmmesh/frontend/panel.js`
- `custom_components/alarmmesh/frontend/translations.js`
- `custom_components/alarmmesh/panel.py`
- `dev/frontend/panel.test.mjs`
- `dev/linking-simulation/alarmmesh_simulation/incident_fixture.py`
- `dev/release/package.py`
- `docs/architecture.md`
