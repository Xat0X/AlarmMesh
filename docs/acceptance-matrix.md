# Current read-only MVP acceptance — 2026-11-13

Current uncommitted device-catalog work after beta.2 has its own dated
[coverage and evidence matrix](device-compatibility.md#current-evidence).
The historical results below are retained and do not claim visual or physical
acceptance for those additional profiles.

## New local integrated interface — 2026-11-13

Base **bbd767aa2766f55a2a2a62c10e9df18390d1270f** plus the new local panel/group
implementation and preserved prior documentation edits. This is new product code;
**none of the historical hosted CI or installer results below validates it**.
Manifest version remains 0.0.1, config-entry version/source selection and overview
identities are unchanged. Product behavior and operator steps: [panel guide](panel.md).

Current full route: `pwsh -NoProfile -File ./dev/validate.ps1`, exit **0**, **PASS**.
Evidence prefix: `config/validation/0713e9eac4c14d09b9f4f9c6bc035d06/`.

| Control / evidence category | Actual scope and result | Evidence / remaining action |
| --- | --- | --- |
| Full Linux pytest / automated | Python 3.14.10, HA 2026.10.4: **277 PASS**, no skipped tests | `pytest.xml`, `baseline.log`; existing assertions and all 79 protected status tests retained. |
| Backend panel/storage/auth / automated HA fixtures | Included in pytest: 27 new panel cases; real registry, WebSocket auth/role revocation, atomic persistence/conflicts, subset calculations, unload/reload/removal and in-flight save | `tests/test_panel.py`; no physical devices or production credentials. |
| Frontend DOM / automated | Node 24.22.1, eleven component tests **PASS** | `frontend.log`; real component with Linkedom, no layout/native-modal proof. |
| Ruff lint/format, official hassfest, PowerShell parse/fault checks, Compose / automated | All **PASS** | `baseline.log`, `hassfest.log`, `compose.log`, `validation-result.json`. |
| Exact HA 2026.10.4 / automated official image | Requested=actual, **all 14 scenarios PASS** | `compatibility-2026.10.4.json`; includes actual authenticated panel subscription/group mutations, served JS, persisted groups and panel cleanup. |
| Exact HA 2026.11.1 / automated official image | Requested=actual, **all 14 scenarios PASS** | `compatibility-2026.11.1.json`; fresh separate config/internal network/no web ports. |
| Workflow syntax / offline | **PASS**, actionlint | `config/panel-ui/63657ee3edb64b32b0d5f30ceb6eae2a/actionlint.log`; changed workflow has not run on GitHub. |
| Local new integration package / automated | **PASS**, explicit 23-file inventory, two independent builds with identical SHA-256, no Node dependencies or runtime data | `config/release-packages/panel-20261113-ui-accepted/inventory.json`; local test ZIP only. |
| Final scope/privacy/document links / local audit | **PASS**: 84 original Python test/fixture functions and their assertions, protected hashes, package/source and validated-source match, 99 links/eight anchors and whitespace | `config/panel-ui/63657ee3edb64b32b0d5f30ceb6eae2a/scope-audit-final.json`; targeted scan is not a blanket secret-detection guarantee. |
| Disposable web setup / technical | **PASS**, HA 2026.11.1, config check, owned labels/mounts and loopback 8128 | `config/panel-ui/current-run.json`; no installer/backup configuration reused. |
| Actual new panel UI / independent visual observation | **PASS** for the checks detailed below on HA 2026.11.1, current local product files | Owner completed test onboarding; the agent then operated only this localhost simulation through supported native computer control. No credentials read or fabricated. |
| Phone/tablet, light/dark and basic native keyboard behavior / visual | **PASS**, 360/390 px phone, 768/1024 px tablet, actual rendered component | Screenshots below. Browser viewport emulation, not physical phone/tablet or a formal accessibility audit. |
| Physical devices / physical acceptance | **NIET UITGEVOERD**, outside scope | No smoke, self-test, radio/MQTT interruption or production restart. |

The local 23-file package SHA-256 is
`8837a72e161dca107e11a3536612eac7faa01bb2f41ec712881be4d4aa4fc16d`.
Groups use version-1 entry-owned HA storage with atomic writes, revision conflicts,
stable IDs and explicit retention of stale references. UI/commands are admin-only;
no extra HA entities/devices/services, state writes, polling or alarm actions.

Earlier full routes, including `config/validation/fed2faed529c4101bd6952726f6eb94e/`,
remain retained. The route above runs after the phone-card correction discovered
during visual acceptance. Only documentation/result updates follow it. Earlier
installer/backup environments and their evidence remain intact.

### Actual panel UI observations

All rows below use base **bbd767aa2766f55a2a2a62c10e9df18390d1270f** plus the
local panel implementation, exact **HA 2026.11.1**, on **2026-11-13**. They are
independent visual observations, not inherited historical UI results or physical
device evidence. Local evidence prefix:
`config/panel-ui/63657ee3edb64b32b0d5f30ceb6eae2a/`.
Screenshot numbers refer to filenames in its ignored `screenshots/` directory.

| Check | Result / observed behavior | Evidence / boundary |
| --- | --- | --- |
| New config and panel | **PASS**: Dutch config selected A+B; integration page showed two entities; AlarmMesh sidebar opens all four screens | 01; actual admin session, no second login/cloud/product server. |
| Current source states | **PASS**: off/complete; on/complete; on/incomplete with the other source unavailable; indeterminate/incomplete without active smoke; recovery to off/complete | 01, 04–06, 22. Only the four dedicated simulation helpers changed. |
| Detector details | **PASS**: raw `off`, selected source, no-area fallback, unavailable model/device/manufacturer; HA button replaces our dialog with HA entity information | 02; no invented battery, model or contact timestamp. |
| HA areas | **PASS**: assigning A to a room in HA immediately updates the panel; B remains No area; room detail contains only its source and subset result | 04, 17–18. No parallel room registry. |
| Group create/edit/validation/cancel | **PASS**: empty name rejected in Dutch and English, name edited, two selected members saved; cancelled name edit retains stored group | 03, 15; live form and backend, not a DOM-only inference. |
| Group stale references and delete | **PASS**: unselected A remains visible; explicit membership removal restores complete group status; delete asks confirmation, then shows No groups yet | 07, 14–16. Source selection unchanged by group deletion. |
| Source options and reload | **PASS**: Choose sources reaches original HA options; A+B → B leaves A without influence even when A reports smoke; B → B+A immediately recognizes active A | 07–08, 17. Final selection restored to A+B (order immaterial). |
| Real restart and persistent groups | **PASS**: actual Docker restart and subsequent stop/start preserve the saved group/name/members and source selection; final group has two members | `restart-result.json`, 20–21. This is a test-container restart, not a production restart or HA backup test. |
| Lost connection and recovery | **PASS**: while container is stopped, current status is hidden and connection loss is explicit; starting it reconnects automatically to current off/complete | 19–20, 22. No manual page refresh needed for recovery. |
| Phone/tablet, long name, themes | **PASS after correction**: phone cards now use one full-width column; long name wraps, mobile editor fits, bottom navigation works; tablet sidebar, room cards and details fit; both themes readable | Before: 10. After: 14–15, 21–23; tablet: 16–18, 23. 11–13 still showed a cached old stylesheet and are not accepted after-fix evidence. |
| Native keyboard and errors | **PASS, basic check**: visible focus, field-local translated name error, Tab navigation inside detail, Escape closes group/room dialogs, HA information opens after releasing our modal | 02–03, 15, 18. Not a screen-reader/WCAG certification or exhaustive keyboard audit. |
| Packaged branding | **PASS**: square supplied icon and text title readable on light/dark panel backgrounds | 01, 08, 16–17, 23. Panel does not render the wide logo; the historical Marketplace README-logo finding remains open. |

The two-column phone rule made a single long group card unnecessarily narrow.
The only follow-up product correction is one responsive CSS declaration; the
before/after browser observations are its layout regression check. No fake DOM
layout test was added. During this in-place development update Chrome retained
an earlier stylesheet; reloading with DevTools' temporary Disable cache fetched
the corrected file. That setting was restored afterwards. This is not an
installer update/end-to-end claim.

The test instance remains running at **http://127.0.0.1:8128/alarmmesh** with Dutch
dark appearance, both selected sources off/available, A assigned to a room, B
unassigned and one two-member **Simulatiegroep**. All four helpers are off.
Use `pwsh -NoProfile -File ./dev/panel-ui.ps1 -Action Stop` to stop only this owned
instance while keeping its test configuration. No current onboarding action is
outstanding. Non-admin denial, role revocation, concurrent-edit conflicts and
listener cleanup are automated fixture/DOM evidence above; they were not repeated
with separate live browser accounts. No physical acceptance or new hosted CI run
is claimed.

## Historical review context before the new interface

Original review base: **a300d39b7eac4ef80ebb971e859b9866f2145c15**. Follow-up
checkout: **bbd767aa2766f55a2a2a62c10e9df18390d1270f**, `main`, initially clean.
That newer commit already contains the packaging/check tooling, five tooling
tests and documentation described below. Its hosted CI is now independently
verified. Product files, metadata, dependencies, workflows and all original
tests are unchanged relative to a300d39. This follow-up changes documentation
only; those new local edits have **no new hosted CI result**.
This is the central current results list; the dated
[earlier review](review-results.md) and [original UI acceptance](mvp-acceptance.md)
are historical evidence, not overwritten results.

All local evidence paths below are ignored by Git. Screenshots contain only the
disposable simulation session and remain local. PASS means the stated scope,
never physical smoke detection or store approval.

## Actual Marketplace and backup exercise — 2026-11-13

The separate installer instance uses exact **2026.11.1**, revision
**bbd767aa2766f55a2a2a62c10e9df18390d1270f** offered as `bbd767a`, manifest
**0.0.1**. Its only mount is its own writable `/config`; there is no repository
integration mount or manually extracted payload. The owner completed onboarding
and GitHub authorization. Subsequent installer/configuration actions and states
were independently observed through the actual UI. The older 8124/8125 instances
were not used or changed. [Procedure and controlled stop](installer-acceptance.md).

Evidence prefix: `config/installer-acceptance/ca1998c695c243ec82aed06ff8348b90/`.
Accounts, screenshots, backup material and local configuration remain ignored.

| Check / category | Result and evidence | Boundary / remaining action |
| --- | --- | --- |
| New environment / technical | PASS: exact image/version, run labels, one writable own-config mount, no privileges/devices/socket, loopback port 8126; `current-run.json` | Installer bridge permits outbound Internet and is not a LAN-egress firewall. No production connection configured. |
| Actual Marketplace link/install / UI + file verification | PASS: GitHub link added, offered `bbd767a` installed; all 18 installed files match the exact Git commit, `installed-files.json`; screenshots 01–02 | User performed authentication; this is not catalog admission. Initial install loaded immediately. |
| A+B, two overviews and no device / UI | PASS: configuration and entity list, screenshots 01–03 | Raw unique IDs are not displayed by this UI. |
| off/complete, on/complete, on/incomplete, unavailable/incomplete, recovery / UI | PASS: only simulation helpers changed, screenshots 03–07 | No physical source validation. |
| Customized names/IDs and recognizable on/incomplete checkpoint / UI | PASS: `checkpoint.json`, screenshots 08 and 12 | Source A active, source B unreachable; current simulated source values, not a restored AlarmMesh outcome. |
| Actual Marketplace identical-revision reinstall and supported HA restart / UI | PASS: offered reinstall `bbd767a`, restart repair followed, customized IDs/names and on/incomplete retained; screenshots 10–12 | Not an upgrade between different product versions. A differing published version needs later acceptance. |
| Marketplace square icon after restart / visual | PASS: correct icon after HA restart | Initial pre-restart placeholder was transient. |
| Marketplace-rendered wide README logo on dark background / visual | FAIL: light artwork displayed with low-contrast dark text, screenshot 09 (also visible after restart) | Rendering/theme selection needs a separate documentation/branding correction; no asset or production change made here. |
| HA backup creation / actual supported UI | PASS: named manual checkpoint archive, HA shows encrypted local storage and 2026.11.1; `backup-result.json`, screenshot 13 | Settings/configuration backed up; no Recorder/history claim. Key handling belongs to the owner. |
| Supported restore / separate fresh Container target | PASS: HA onboarding uploaded the archive; owner entered the key, submitted restore and signed in with the restored original test account; agent then inspected actual results. Destination `restore-result.json` and `restored-files.json`; screenshots 14–18 under the source evidence prefix | Same exact HA version, all 18 integration hashes, original entry ID, A+B, custom names/IDs, exactly two overviews/no device, on/incomplete checkpoint, live unavailable/incomplete and recovery to off/complete, correct icon. Raw unique IDs were not separately inspected. |
| Entry deletion, Marketplace uninstall and fresh reinstall / actual UI | NIET UITGEVOERD: Computer Use stopped on its browser-URL policy check before deletion; `installer-result.json` | No manual file deletion or installation substitution. Finish only the remaining UI steps in the procedure below. |
| Upgrade between distinct product versions / installer | NIET UITGEVOERD: identical branch payload was reinstalled; no distinct release was created for testing | Version-choice/reinstall menu exists, but alternate-version choices were not submitted/validated. Test a future actually offered distinct approved revision separately. |

The historical installer/backup gaps below describe the earlier review only;
the dated exercise above is the current follow-up and does not rewrite that
earlier evidence. New local documentation has no new hosted CI result.

The HA-created archive is retained at
`config/installer-acceptance/ca1998c695c243ec82aed06ff8348b90/config/backups/AlarmMesh_bbd767a_installer_checkpoint_-_SIMULATION_ONLY_2026-11-13_00.28_26766049.tar`
(2,119,680 bytes), SHA-256
`f0a8444778986147ac460fc0b5b725d1ecd36e8906b3d69558b24f3d77c3b426`.
Its contents and key are not extracted into evidence. The separate destination
run is `99b784e4928b4f32af6072adbf2d0d97`, localhost port 8127.

The original internal restore network served HA inside the container but its
published loopback port was unreachable on this Docker Desktop host. Automatic
approval rejected broadening that boundary; **only after explicit owner approval**
was a dedicated ordinary bridge used. This permits outbound Internet/LAN access;
it is not an egress firewall. The original source stayed stopped during actual
restore and restored-account use. The destination is now stopped, with all four
helpers off. The original is running alone on port 8126 with its last observed/saved
**on/incomplete simulation checkpoint**, pending the remaining uninstall/re-add
sequence. Ports 8124 and 8125 retain their original container start times.

No key or password was read. Backup setup, private emergency-kit saving, key
entry/restore submission and restored-account login were owner actions; restored
files, selected sources, customized overviews and live changes were independently
verified afterward. The earlier stopped-file snapshot was not substituted for
this real HA backup. No production recovery or physical-device claim follows.

Browser automation ended with: “could not determine the current browser URL on
Windows with enough confidence to enforce policy.” No retry through another
automation channel or authentication workaround was attempted. Documentation and
non-UI scope checks were completed independently. The [remaining precise steps](installer-acceptance.md#remaining-ui-only-steps)
require manual action or a future supported browser session; there is no green
total installer-acceptance claim.

## Automated evidence

| Revision / actual version | Category and check | Result / evidence | Remaining action |
| --- | --- | --- | --- |
| Exact bbd767a / Linux Python 3.14.10, HA 2026.10.4 | Hosted tests, Ruff lint/format and hassfest | PASS: 249 tests, 38 files formatted, all four jobs successful; [GitHub run 43318117479](https://github.com/Xat0X/AlarmMesh/actions/runs/43318117479), completed 2026-11-12 22:16 UTC; `config/release-evidence/bbd767a/hosted-summary.json` | Later local documentation edits are not part of that run. |
| Exact bbd767a / requested=actual 2026.10.4 and 2026.11.1 | Hosted compatibility artifacts | PASS: both downloaded ZIP digests match GitHub, exact clean commit, configuration, all 12 scenarios and cleanup; `config/release-evidence/bbd767a/compatibility-<version>.json` | No claim about other versions or physical devices. |
| bbd767a plus local documentation / HA 2026.10.4 baseline and both exact compatibility images | Full local route repeated | PASS: all checks; `config/validation/d74a8321292e4c76b8608dfceea779ae/validation-result.json` | No new hosted result for these documentation edits. |
| 0e7ba38 → bbd767a / exact 2026.10.4 | Fresh file replacement, new processes, removal/re-add and stopped-file restore | PASS: `config/update-checks/2026.10.4/a9367527180747da867f090897b9ab3f/update-result.json`, all stages and cleanup | Identical integration payload; not installer or HA-backup acceptance. |
| 0e7ba38 → bbd767a / exact 2026.11.1 | Same fresh independent check | PASS: `config/update-checks/2026.11.1/0eefd4487bb0459fb5605912f8b417e6/update-result.json`, all stages and cleanup | Same limitation. |
| Exact a300d39 / Linux Python 3.14.10, HA 2026.10.4 | Hosted tests, Ruff lint/format | PASS: 244 tests; [GitHub run 43308245220](https://github.com/Xat0X/AlarmMesh/actions/runs/43308245220), completed successfully 2026-11-12 21:15 UTC; `config/release-evidence/a300d39/hosted-summary.json` | New local changes need their own future authorized hosted run. |
| Exact a300d39 / official hassfest | Hosted integration validation | PASS in the same run | No catalog approval implied. |
| Exact a300d39 / requested=actual 2026.10.4 and 2026.11.1 | Hosted technical compatibility | PASS: both jobs and both downloaded artifacts inspected, each with all 12 scenarios and cleanup PASS; `config/release-evidence/a300d39/compatibility-<version>.json` | No claim about other versions. |
| a300d39 plus this local review / HA 2026.10.4 | Full local validation | PASS: 249 tests and all route checks; see final local result below | Local evidence does not replace hosted execution. |
| 0e7ba38 → a300d39 / exact 2026.10.4 | File replacement, new HA process, removal/re-add, stopped-file snapshot restore | PASS: `config/update-checks/2026.10.4/044f9c0c5cbf4c09aa14e8fd6e27aa38/update-result.json` | Integration payload is identical across these revisions; no differing-version upgrade claim. |
| 0e7ba38 → a300d39 / exact 2026.11.1 | Same independent file/restart/recovery check | PASS: `config/update-checks/2026.11.1/9f476d8b16f841b7ba3d75156108f406/update-result.json` | Same limitation. |
| a300d39 integration / manifest 0.0.1 | Local test package | PASS: 18 reviewed files, reproducible ZIP and SHA-256; [inventory and commands](release-package.md) | Not a published/distribution-approved release. |

Hosted artifact ZIP digests were matched to GitHub's metadata before inspecting
their JSON. Original a300d39 artifact IDs: **13983659705** (2026.10.4) and
**13984881601** (2026.11.1). Follow-up bbd767a artifact IDs: **13989680919**
(2026.10.4) and **13989561250** (2026.11.1). Each pair reports its exact commit
and a clean worktree. No raw job logs, accounts or storage are added to Git.

The file/recovery runs use independent installation copies mounted read-only,
fresh simulation configurations and owned internal networks without web ports.
Seed, replacement and restore use separate real HA processes. They preserve
options, entry/registry/unique/entity IDs and custom names; recognize saved helper
states as current sources; verify six exact brand files through HA's loader;
detach the removed runtime and create exactly two current overviews on re-add.
The restored snapshot returns to the original customized `on/incomplete`
checkpoint, then responds to current helper changes. It is a copy made after a
normal process stop, **not a test of Home Assistant's backup feature**.

## Fresh visual simulation UI

Actually observed on **2026-11-12**, unchanged a300d39 integration, **HA
2026.10.4**, separate review instance on localhost port 8125. Before use, the
container name/run labels, exact version, fresh review configuration, read-only
product mount and localhost-only port were verified. The user completed local
onboarding; no password/token was read, created by tooling or recorded. The
original port-8124 acceptance container and its saved account were untouched.

Follow-up on bbd767a: the integration payload was verified byte-for-byte unchanged
from a300d39; the owned container/version/mounts/localhost binding were rechecked.
The same signed-in test browser was verified at localhost port 8125 and still
shows exactly two overviews, no associated device, no smoke/complete. Opening the
Dutch options form confirms A+B; closing without saving preserves the selection.
The simulation dashboard confirms all four helpers off and both sources clear.
New local evidence is under `config/release-ui-evidence/bbd767a/`: `01-current-off-complete.jpg`,
`02-options-a-b.jpg`, `03-all-helpers-off.jpg`. The full sequence below remains
attributed to its original observation, not claimed as a second complete UI run.
No production browser interaction was performed.

Evidence prefix: `config/release-ui-evidence/a300d39/`. Numbers identify the
locally saved JPEGs; the actual descriptive filenames remain in that directory.

| UI observation | Result | Local screenshot evidence | Remaining action |
| --- | --- | --- | --- |
| Dutch configuration, required-source error, A+B selection | PASS | 01–03 | None for this version/revision. |
| Dutch options prefill, cancel preserves A+B | PASS | 12–13 | None. |
| English configuration/options, required-source error and cancel | PASS | 21–22, 25 | None. Backend-invalid IDs/duplicates remain automated coverage, not forced through the selector. |
| Exactly two overviews, no associated device | PASS | 05, 27, 29 | None. |
| Both off → off/complete | PASS | 05, 10, 29 | None. |
| A on → on/complete | PASS | 07, 27 | None. |
| A on, B unreachable → on/incomplete | PASS | 08 | None. |
| A off, B unreachable → unavailable/incomplete, never off | PASS | 09 | None. |
| Restore B → current off/complete | PASS | 10 | None. |
| Options B-only, then A on has no influence | PASS | 14–16 | None. |
| Custom names and both custom entity IDs survive explicit reload; no duplicates/old result | PASS | 11, 17–19 | Raw unique IDs are tested automatically, not displayed in this UI. |
| Remove entry, no old entities after refresh, re-add A+B with already active A | PASS | 23–25, 27 | Removal intentionally creates a new identity; reload preserves identity. |
| Supplied icon readable on dark and light backgrounds; no placeholder/cropping | PASS | 04, 20 | None for the inspected integration screens. |
| Wide logo's light/dark variant in a live HA screen | NIET UITGEVOERD | Inspected screens display a square icon plus text title, not the wide logo | Inspect if a future installer/screen actually uses the wide logo. Exact six-file serving is technical evidence only. |
| Normal state restored | PASS | 28–29 | A+B selected, all four helpers off, off/complete, Dutch profile and Auto theme. |

The initial English default entity names reflect the instance language at entity
creation; switching profile language does not rename existing registry entries.
Dutch/English form text and translated state labels were separately observed.
Only the dedicated simulation helpers were changed. Developer Tools state
overrides were not needed; these helper values are persisted by HA.

## Earlier installer gaps, pilot and physical acceptance

Installer/backup rows in this historical table describe the review before the
new 2026-11-13 exercise above. They must not be read as its current outcome.

| Revision / HA | Evidence category | Result / evidence | Remaining action |
| --- | --- | --- | --- |
| Local a300d39 package / both exact versions | Automated file installation/replacement | PASS, reports above | This is not Marketplace/HACS end-to-end acceptance. |
| Intended release / Marketplace on 2026.11.1 or HACS on 2026.10.4 | Real installer acceptance | NIET UITGEVOERD: disposable backend checks have no installer/GitHub authorization; the UI baseline has no configured HACS | Separately authorize/setup an installer in a disposable instance and test install/update/uninstall of the chosen published candidate. No live credentials may be reused. |
| Both exact versions / stopped test files | Automated snapshot recovery | PASS, reports above | HA backup creation/restore was not attempted in that review. Its absence from those checks is not evidence that Container cannot support restore; see the new exercise above. |
| Reported AlarmMesh 0.0.1 / production Core 2026.11.1; exact installed commit not independently identified | User report | Installation, Heiman source selection, no smoke/complete and selection/current display after reload confirmed; [pilot register](read-only-pilot.md) | This task did not access or inspect that installation. |
| Same pilot | Screenshots from the earlier pilot | Only the observations explicitly classified in the pilot register | No new production screenshot inspected or committed here. |
| Physical smoke transitions, physical loss/recovery, production restart, separately observed physical self-test | NIET UITGEVOERD | Neither UI helpers nor a self-test prove smoke detection | Separate owner-planned acceptance under manufacturer instructions; use the passive protocol meanwhile. |

No product defect was demonstrated; no production correction or status-rule
change was made. All 244 existing tests, including the 79 status tests, retain
their assertions. Five new tests guard package allowlisting, missing runtime
files, exact deterministic contents and refusal to overwrite an artifact.

The official [Marketplace custom-repository procedure](https://www.home-assistant.io/integrations/marketplace/#custom-repositories),
rechecked on 2026-11-12, requires a GitHub connection for this link-based route.
No such connection was created during that earlier review or borrowed from a real
installation. The existing signed-in review UI is the older 2026.10.4 baseline without HACS;
the 2026.11.1 backend checks have no onboarded installer UI. These are precise
limits of installer evidence, not failed AlarmMesh runtime scenarios.

## Earlier local result — a300d39 plus preparation

Command actually executed: `pwsh -NoProfile -File ./dev/validate.ps1`.
Final evidence prefix: `config/validation/4c0a6e4fda284b5cab04fe6836313b59/`.

| Check | Actual version / scope | Result | Evidence under that prefix |
| --- | --- | --- | --- |
| Full baseline | Linux Python 3.14.10 / pinned HA 2026.10.4 | PASS: 249 tests | `pytest.xml`, `baseline.log` |
| Ruff | 0.17.4 lint and format, all 38 Python files | PASS | `baseline.log` |
| PowerShell | All dev scripts parsed, wrapper failure checks | PASS | `validation-result.json`; command output |
| Compose | Existing simulation configuration | PASS | `compose.log`, `validation-result.json` |
| Official hassfest | Container validator, 1 integration, 0 invalid | PASS | `hassfest.log` |
| Compatibility | Requested=actual 2026.10.4, configuration and all 12 scenarios | PASS | `compatibility-2026.10.4.json` |
| Compatibility | Requested=actual 2026.11.1, configuration and all 12 scenarios | PASS | `compatibility-2026.11.1.json` |
| Owned-resource cleanup / total | All standard-route checks | PASS, process exit 0 | `validation-result.json` |
| Scope / privacy / package / links | Existing tracked tests/product/dependencies/metadata/workflows/artwork unchanged; no tracked runtime; archive hashes/CRC/18-file inventory; 75 relative doc/image targets | PASS | `config/release-evidence/a300d39/scope-audit.json`, final package inventory; local command observations |

An earlier route invocation is retained as **FAIL** at
`config/validation/6ce2ac066423460ba31e4b8c4cd1727d/`: Ruff identified a missing
import-group separator in the new packaging test. That was corrected and the
entire route rerun successfully above; no assertion or check was disabled.
Workflow syntax was not changed in this preparation. Final documentation-only
result updates were followed by link, privacy and whitespace checks.
Packaging/update evidence is independent of pytest; neither replaces observed
UI or open installer/physical acceptance.

## Local validation before installer exercise — bbd767a follow-up

After the relevant documentation updates, the full command
`pwsh -NoProfile -File ./dev/validate.ps1` exited **0**, overall **PASS**.
Current prefix: `config/validation/d74a8321292e4c76b8608dfceea779ae/`.

| Check | Actual version / result | Evidence under current prefix |
| --- | --- | --- |
| Full Linux test suite | Python 3.14.10 / pinned HA 2026.10.4, **249 PASS** | `pytest.xml`, `baseline.log` |
| Ruff lint/format | 0.17.4, **PASS**, 38 files formatted | `baseline.log` |
| PowerShell parse and wrapper failure checks; Compose | **PASS** | `validation-result.json`, `compose.log`; command output |
| Official hassfest | **PASS**, 1 integration, 0 invalid | `hassfest.log` |
| Exact compatibility 2026.10.4 | Configuration and all 12 scenarios **PASS** | `compatibility-2026.10.4.json` |
| Exact compatibility 2026.11.1 | Configuration and all 12 scenarios **PASS** | `compatibility-2026.11.1.json` |
| Cleanup and total | **PASS** | `validation-result.json` |

The new bbd767a package inventory records the same 18 integration files and
SHA-256 as the earlier build; [package details](release-package.md) identify the
new output location. No production/tooling/test correction was necessary in this
follow-up. Existing tests, including all 79 status cases, are unchanged. Final
documentation/image links, whitespace, scope and targeted privacy checks pass;
the local audit is `config/release-evidence/bbd767a/scope-audit.json`. No runtime
or generated package is tracked. Workflow syntax is unchanged, so no new workflow
syntax validation is claimed. Hosted bbd767a is separate from these local edits.

## Installer-exercise validation — documentation only

This exercise changed only documentation, preserving the seven initial local
documentation edits. Production code, all existing tests including the 79 status
cases, tooling, workflow, metadata, dependencies and supplied artwork are
unchanged. Accordingly the full validation command was **not rerun in this
installer exercise**; its preceding 249-test/compatibility result above remains
dated evidence, not a new run or substitute for UI acceptance.

Relative documentation/image targets and local anchors, new-file whitespace,
`git diff --check`, protected file hashes, tracked-file scope and targeted privacy
checks are recorded in
`config/installer-acceptance/ca1998c695c243ec82aed06ff8348b90/scope-audit.json`.
No generated package, backup, screenshot, credential or runtime file is tracked.
Only the two owned new test containers and their networks were managed. The old
acceptance/review environments retain their original start times; current states
and mounts are in the local `environment-audit.json`.

## Local environment handoff

The review simulator remains running at **http://127.0.0.1:8125/** in its normal
state. Its exact identity is in ignored `config/review-ui/current-run.json`.
The original acceptance environment at port 8124 remains running, untouched.
All temporary file-update check containers/networks were cleaned up; their
packages, configuration and stopped-file snapshots are retained locally.

To stop only the review simulator while preserving configuration/account:

```powershell
$review = Get-Content -Raw config/review-ui/current-run.json | ConvertFrom-Json
$purpose = docker inspect $review.name --format '{{index .Config.Labels "org.alarmmesh.purpose"}}'
if ($LASTEXITCODE -ne 0 -or $purpose -ne 'review-ui') { throw 'Review ownership mismatch' }
$run = docker inspect $review.name --format '{{index .Config.Labels "org.alarmmesh.run"}}'
if ($LASTEXITCODE -ne 0 -or $run -ne $review.id) { throw 'Review run mismatch' }
docker stop $review.name
if ($LASTEXITCODE -ne 0) { throw 'Review container did not stop' }
```

Do not use the old acceptance stop command for this review instance, prune
Docker, delete snapshots or remove `config/` automatically. No environment is
stopped as part of this handoff.
