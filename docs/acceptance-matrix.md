# Current read-only MVP acceptance — 2026-11-12

Repository base: **a300d39b7eac4ef80ebb971e859b9866f2145c15**, `main`, initially
clean. This review adds packaging/check tooling, five tooling tests and
documentation only. Product files, metadata, dependencies, workflows and all
existing tests remain unchanged. These local changes have **no new hosted CI
result**. This is the central current results list; the dated
[earlier review](review-results.md) and [original UI acceptance](mvp-acceptance.md)
are historical evidence, not overwritten results.

All local evidence paths below are ignored by Git. Screenshots contain only the
disposable simulation session and remain local. PASS means the stated scope,
never physical smoke detection or store approval.

## Automated evidence

| Revision / actual version | Category and check | Result / evidence | Remaining action |
| --- | --- | --- | --- |
| Exact a300d39 / Linux Python 3.14.10, HA 2026.10.4 | Hosted tests, Ruff lint/format | PASS: 244 tests; [GitHub run 43308245220](https://github.com/Xat0X/AlarmMesh/actions/runs/43308245220), completed successfully 2026-11-12 21:15 UTC; `config/release-evidence/a300d39/hosted-summary.json` | New local changes need their own future authorized hosted run. |
| Exact a300d39 / official hassfest | Hosted integration validation | PASS in the same run | No catalog approval implied. |
| Exact a300d39 / requested=actual 2026.10.4 and 2026.11.1 | Hosted technical compatibility | PASS: both jobs and both downloaded artifacts inspected, each with all 12 scenarios and cleanup PASS; `config/release-evidence/a300d39/compatibility-<version>.json` | No claim about other versions. |
| a300d39 plus this local review / HA 2026.10.4 | Full local validation | PASS: 249 tests and all route checks; see final local result below | Local evidence does not replace hosted execution. |
| 0e7ba38 → a300d39 / exact 2026.10.4 | File replacement, new HA process, removal/re-add, stopped-file snapshot restore | PASS: `config/update-checks/2026.10.4/044f9c0c5cbf4c09aa14e8fd6e27aa38/update-result.json` | Integration payload is identical across these revisions; no differing-version upgrade claim. |
| 0e7ba38 → a300d39 / exact 2026.11.1 | Same independent file/restart/recovery check | PASS: `config/update-checks/2026.11.1/9f476d8b16f841b7ba3d75156108f406/update-result.json` | Same limitation. |
| a300d39 integration / manifest 0.0.1 | Local test package | PASS: 18 reviewed files, reproducible ZIP and SHA-256; [inventory and commands](release-package.md) | Not a published/distribution-approved release. |

Hosted artifact ZIP digests were matched to GitHub's metadata before inspecting
their JSON. Artifact IDs: **13983659705** (2026.10.4) and **13984881601**
(2026.11.1). Both report exact a300d39 and a clean worktree. No raw job logs,
accounts or storage are added to Git.

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

## Installer, pilot and unperformed acceptance

| Revision / HA | Evidence category | Result / evidence | Remaining action |
| --- | --- | --- | --- |
| Local a300d39 package / both exact versions | Automated file installation/replacement | PASS, reports above | This is not Marketplace/HACS end-to-end acceptance. |
| Intended release / Marketplace on 2026.11.1 or HACS on 2026.10.4 | Real installer acceptance | NIET UITGEVOERD: disposable backend checks have no installer/GitHub authorization; the UI baseline has no configured HACS | Separately authorize/setup an installer in a disposable instance and test install/update/uninstall of the chosen published candidate. No live credentials may be reused. |
| Both exact versions / stopped test files | Automated snapshot recovery | PASS, reports above | Home Assistant backup creation/restore itself remains NIET UITGEVOERD: the minimal simulation configuration does not load the backup integration. Test separately before claiming that route. |
| Reported AlarmMesh 0.0.1 / production Core 2026.11.1; exact installed commit not independently identified | User report | Installation, Heiman source selection, no smoke/complete and selection/current display after reload confirmed; [pilot register](read-only-pilot.md) | This task did not access or inspect that installation. |
| Same pilot | Screenshots from the earlier pilot | Only the observations explicitly classified in the pilot register | No new production screenshot inspected or committed here. |
| Physical smoke transitions, physical loss/recovery, production restart, separately observed physical self-test | NIET UITGEVOERD | Neither UI helpers nor a self-test prove smoke detection | Separate owner-planned acceptance under manufacturer instructions; use the passive protocol meanwhile. |

No product defect was demonstrated; no production correction or status-rule
change was made. All 244 existing tests, including the 79 status tests, retain
their assertions. Five new tests guard package allowlisting, missing runtime
files, exact deterministic contents and refusal to overwrite an artifact.

## Final local result

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
