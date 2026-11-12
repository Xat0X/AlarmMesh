# Read-only MVP review — 2026-11-12

**Historical review of 0e7ba38 plus the then-local review changes.** The tables,
blocked browser/onboarding observations and pending hosted-run statements below
describe that earlier review only. On 2026-11-12, a separate follow-up verified
hosted a300d39 and its artifacts and completed the fresh simulation UI checklist.
Use the [central current acceptance matrix](acceptance-matrix.md) for those new
results and remaining boundaries; the original record is retained intact below.

Base: **0e7ba380de2cc1a267580de8973ab3b9515f21a3** on `main`, initially clean.
The working changes are for review; there is no new committed revision. No
production Python, status semantics, schema, domain, entry version, unique IDs,
manifest/minimum version or dependencies changed. All supplied SVG/PNG files,
including the packaged images, remain unchanged. No license was selected.

## Focused quality review

| Concern | Implementation and existing regression evidence | Finding |
| --- | --- | --- |
| Selection and backend validation | `config_flow.py`; config-flow tests cover shapes, duplicates, identity metadata/overrides, own sources, absent IDs, parallel dialogs and singleton | No demonstrated product defect. Current state values are not used as identity validation. |
| Empty/unknown/missing/unavailable sources and smoke priority | `runtime.py`, unchanged `status.py`; initial-state, recovery, remove/reappear, foundation and priority tests | No demonstrated product defect. Explicit off is required for no smoke reported. Information completeness remains separate. |
| Initial subscription/snapshot and options | `__init__.py`; subscribe-before-snapshot, real options flow, repeated swaps/reloads and frozen old-runtime assertions | No demonstrated product defect. Fresh local states are read after subscribing without yielding. |
| Unload and partial setup | Platform initialization markers and HA unload callbacks; injected forwarding/platform failures, cleanup, failed-unload and restart-fixture tests | Preserve the tested HA policy. A failed platform unload is not falsely reported as successful; baseline recovery may require restart after the fault is resolved. |
| Identity and disabled entities | Entry-based unique IDs; custom registry names/IDs, source changes, restart fixtures, one/both disabled overview tests | No schema/identity change needed. State processing remains independent of enabled overviews. |
| Translation/availability display | Shipped EN/NL files; translation API tests, overview availability tests | Automated resources and state semantics pass; a fresh visual UI inspection remains separate. |

No production-code correction or duplicate product regression test was justified
by this review. The existing 79 status tests are unchanged. Known scope limits
(fixed source IDs, no freshness guarantee, no direct device validation) are
intentional and documented, not repaired by adding functionality.

## Tooling corrections and new regression coverage

- Original runtime exceptions previously lost their message/traceback. They are
  now retained locally in ignored failure logs; public JSON contains only the
  scenario and exception type. Tests verify nonzero failure and no path/detail
  leakage into the public summary.
- Cleanup errors could previously prevent the final report from being written
  and obscure the original failure. Cleanup failures now produce a FAIL report
  and nonzero exit while retaining both original and cleanup details locally.
- New run IDs bind host context and runtime results. A fresh, non-existing export
  path and matching version/commit/run/scenario status are required. Fault tests
  reject stale output, a reused configuration and failure paths instead of
  accepting an old success.
- The full validation command exports only Git-visible sources for the baseline
  and hassfest containers, excluding ignored web/account data and `.git`.
- Six PNG requirement tests and a genuine authenticated HA fixture test verify
  exact local brand-image responses with placeholders disabled. These fixtures
  are disposable test accounts, not credentials or onboarding changes in a
  running installation.

## Final local checks

Use [the complete route](development.md#complete-local-validation). Final result
paths and actual outcomes are recorded below after execution. Reports are local,
ignored evidence; only sanitized compatibility summaries are CI artifact inputs.

| Check | Actual version | Result | Local evidence |
| --- | --- | --- | --- |
| Complete route | Linux Python 3.14.10 / pinned HA 2026.10.4 | PASS: Ruff 0.17.4 lint/format, 244 tests, PowerShell parse/fault tests, Compose, hassfest (1 valid integration), both versions and cleanup | `config/validation/6b905803b17d4810a228f56cb7357a4e/validation-result.json` |
| Baseline tests / image serving | Exact 2026.10.4 | PASS: 244 tests, including 235 unchanged existing tests and 9 new cases | `config/validation/6b905803b17d4810a228f56cb7357a4e/pytest.xml` and `baseline.log` |
| Compatibility scenarios | Exact requested/actual 2026.10.4 | PASS: configuration, all 12 scenarios, cleanup | `config/validation/6b905803b17d4810a228f56cb7357a4e/compatibility-2026.10.4.json` |
| Compatibility scenarios | Exact requested/actual 2026.11.1 | PASS: configuration, all 12 scenarios, cleanup | `config/validation/6b905803b17d4810a228f56cb7357a4e/compatibility-2026.11.1.json` |
| Workflow static validation | actionlint container | PASS | Executed with only the workflow mounted and network disabled |
| Exact proposed CI runtime step, replayed locally | Requested/actual 2026.10.4 and 2026.11.1 | PASS for both, including fresh artifact destination | `config/compatibility/2026.10.4/b0593bc3ad4a4641b84f759a943fa890/compatibility-result.json` and `config/compatibility/2026.11.1/5b6cfc78eec24c3d9ddcaa5bab00970a/compatibility-result.json` |
| Scope, links and privacy | Current local changes | PASS | Protected-file Git diff and status-test hashes unchanged; no runtime files tracked; relative doc/image targets exist; targeted private-data scan clean |
| Workflow on GitHub | Proposed matrix | NOT PERFORMED | No push/hosted run authorized |

The two extra Python tooling cases test reused-storage/stale-success failure and
private traceback retention. The seven image cases are six file checks plus one
actual HA HTTP fixture check. Existing assertions were not weakened. Local
reports explicitly record the uncommitted working changes; a green local report
does not identify a new commit or certify every other HA version.

The final CI runtime step was extracted from the workflow and replayed with each
matrix value on the local Docker host. Each replay allocated a new directory and
passed its exact summary path through the step-output mechanism. Only that file
is eligible for upload; the workflow never searches for a latest/previous PASS.
GitHub runner provisioning, checkout and artifact upload itself were not exercised
locally and remain part of the first authorized hosted run.

Actionlint initially could not be approved with the whole working tree mounted
into a third-party container. The safer retry mounted only the workflow file,
disabled networking and passed. No review rejection or security policy was
bypassed. The workflow's actual GitHub execution remains unverified.

## Separate UI smoke test

A new disposable **HA 2026.10.4** instance was prepared from the simulation YAML,
with a separate ignored configuration under `config/review-ui/`. Its integration
mount is read-only, privileged mode/hardware/host networking are absent, and only
**http://127.0.0.1:8125/** is published. Configuration validation and HTTP 200 pass.
The public onboarding API confirms that owner onboarding is unfinished. No
account, password or token was created or reused for it.

The in-app browser host was unavailable. Windows Computer Use was then stopped
because it could not determine the current browser URL confidently enough to
enforce policy. No browser inputs were performed in the new instance and no
alternate automation bypass was attempted. These are **not new observed UI PASS
results**. The [historical twelve UI scenarios](mvp-acceptance.md) remain valid
only for their recorded date/revision and are not substituted here.

| Requested fresh UI check | Result | Remaining procedure after user onboarding/browser recovery |
| --- | --- | --- |
| English and Dutch configuration/options text | NOT PERFORMED | Inspect both forms and validation text in each profile language; preserve selection on cancel/invalid input. |
| Select simulation sources | NOT PERFORMED | Add AlarmMesh and select A+B from the existing simulated smoke entities. |
| Exactly two overview entities | NOT PERFORMED | Inspect entry entities: smoke and source availability; no device or extra entities. |
| `off` / `complete` | NOT PERFORMED | All four simulation helpers off. |
| `on` / `complete` | NOT PERFORMED | A smoke on, both sources reachable. |
| `on` / `incomplete` | NOT PERFORMED | Keep A smoke on; B unreachable on. |
| `unavailable` / `incomplete` without smoke | NOT PERFORMED | A smoke off while B remains unreachable. |
| Current-state recovery | NOT PERFORMED | B unreachable off: off/complete; repeat recovery while A stays on and verify smoke remains on. |
| Change selected sources | NOT PERFORMED | Select B only through options; A changes have no effect, B changes do. Restore A+B afterwards. |
| Identity through reload | NOT PERFORMED | Record/customize overview names/IDs, reload, verify preserved identities and exactly two entities. |
| Branding on light and dark backgrounds | NOT PERFORMED | Inspect supplied logo/icon in both HA themes; note missing, stale or clipped images. |

The precise next user action is to open the new localhost URL and complete its
onboarding with a disposable local account. Enter credentials personally; do not
share them or add them to Git. Then the checklist above can be executed in that
instance only. The original port-8124 acceptance container and its account/config
were not touched. Generated screenshots, if later needed, stay locally ignored.

For local environment names, read the ignored
`config/review-ui/current-run.json`. The new container is left running for that
optional handoff. Before stopping/removing it, verify its exact name, mounts and
`org.alarmmesh.purpose=review-ui` label; use `docker stop <that-container>` and
optionally `docker rm <that-container>`, then remove only its named review network.
Keep the ignored configuration until the owner chooses otherwise. Never use broad
prune/removal or the original web acceptance lifecycle commands for this instance.

## Evidence and remaining boundaries

Automated fixture/container proof, the historical simulation UI observations,
the [user-reported physical pilot](read-only-pilot.md), and unperformed physical
tests are distinct categories. Real smoke transitions, physical disconnection/
recovery, production restart and separately observed physical self-test behavior
remain **NOT PERFORMED**. No actual smoke, battery, radio/MQTT or device test
command was requested or executed. Future physical acceptance requires separate
planning under manufacturer instructions.

The remaining owner decisions are license/artwork distribution rights, whether
and when to release a reviewed revision/version, and whether to pursue a catalog
submission later. UI onboarding is a remaining user action, not implied consent
to publish. [Release readiness](release-readiness.md) contains the draft release
text; [roadmap](roadmap.md) proposes the next small steps without implementing them.
