# MVP acceptance: isolated local Home Assistant

**Status: UI-acceptatie met gesimuleerde bronnen geslaagd op 2026-11-11.**

Prepared on 2026-11-11 for Home Assistant **2026.10.4** and AlarmMesh commit
**ddc9d497c30b70922bdbc341337591b9d6abe55d** (`ddc9d49`, step 5).
The working-tree changes in step 6 are environment examples, tooling and docs;
production integration code is unchanged.

This is simulated-source acceptance only. No smoke detection, hardware, sirens,
notifications, physical tests or fire-safety certification is being validated.
**Geen rook gemeld is geen garantie op veiligheid.**

## Current environment and next action

- Local URL: **http://127.0.0.1:8124/**
- Container: `alarmmesh-mvp-acceptance`, running and left available.
- Image: `ghcr.io/home-assistant/home-assistant:2026.10.4`.
- Observed image digest:
  `sha256:23f4dfbb69ce76315dbc4de7915504f1c2dcecd7ca2648113a493a385972e133`.
- Runtime configuration and all local account/storage data:
  `config/mvp-acceptance/`, already ignored by Git.
- Integration: repository `custom_components/alarmmesh`, mounted read-only at
  `/config/custom_components/alarmmesh`.
- No host networking, privileged mode, device access, Docker socket, existing HA
  configuration or real accounts are mounted.
- Web container: a dedicated Docker bridge, `alarmmesh-mvp-acceptance-web`, with
  only `127.0.0.1:8124 -> 8123/tcp` published. This bridge is not an outbound
  firewall. The minimal configuration does not enable device discovery or cloud
  integrations. Technical checks use a separate internal Docker network without
  an external route, `alarmmesh-mvp-acceptance`.

The user completed onboarding and supplied the existing signed-in browser session.
At the user's explicit request, the assistant then executed the UI scenarios
below through the in-app browser on 2026-11-11. No password, token or new account
was entered or created by the assistant. Earlier browser-access failures applied
only to preparation; browser control succeeded during this acceptance run.

Final state: the test container is running, profile language is Dutch, both MVP
sources are selected, all four simulation helpers are off, and the two overviews
show no smoke reported (`off`) and complete source information (`complete`).
AlarmMesh was removed and recreated as scenario 11 requires, so its final entry
identity differs from the entry used for the reload/restart tests. No production
code, credentials or real-device settings were changed. Nothing was committed
or pushed during UI acceptance.

## Reproduce the environment

Run from the repository root in PowerShell with Docker Desktop running:

```powershell
docker pull ghcr.io/home-assistant/home-assistant:2026.10.4
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Prepare
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Check
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Start
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Status
```

`Prepare` copies only the two public YAML examples. It never replaces a differing
existing file. `Start` probes localhost port 8124 before starting a stopped/new
container, validates configuration and performs the isolated technical load check.
It never recreates an existing container. A named container with unexpected
ownership labels, image, privileges, device mounts, port binding or config/source
mounts is rejected. If port 8124 is occupied, stop and investigate; do not stop
another user's service or silently choose a different binding.

`Check` validates Compose, then runs HA's `check_config` and an actual HA bootstrap
in new directories below `config/mvp-acceptance/technical-checks/`. The check
container has no published port. Its integration mount is read-only and its
network is internal. The bootstrap loads the example helpers/templates, creates
an AlarmMesh entry through its backend config flow, checks its runtime result
and unloads it. It never creates an owner account or touches the main instance's
`.storage`. `technical-result.json` and checker logs remain in those ignored
directories. This is technical proof, **not** completion of any UI scenario.

Normal startup may emit Home Assistant's standard custom-integration warning
and an upstream `rich/segment.py` Python `SyntaxWarning`. The final configuration
and bootstrap checks completed without a configuration/setup error. Earlier
failed checker attempts are retained in their separate technical-check folders;
only the successful final checks count as PASS.

Docker Desktop did not publish a port for a web container attached exclusively
to an internal network (`NetworkSettings.Ports` was empty). The final web setup
uses the separate bridge above; the actual localhost mapping and HTTP response
were verified after the change. This was environment preparation, not a product
code change or an HA acceptance finding.

The frontend, configuration UI, API, YAML dashboard, local input booleans and
template binary sensors are enabled explicitly. `default_config`, hardware
discovery, cloud accounts, Recorder/history and alarm automations are not added.
Home Assistant may load its own required core dependencies.

## Simulated controls and observation

Open the **Simulated sources** dashboard. Each source has two switches:

| Helper | Off | On |
| --- | --- | --- |
| `input_boolean.mvp_a_smoke` | A reports no smoke | A reports smoke |
| `input_boolean.mvp_a_unreachable` | A available | A unavailable |
| `input_boolean.mvp_b_smoke` | B reports no smoke | B reports smoke |
| `input_boolean.mvp_b_unreachable` | B available | B unavailable |

The resulting sources on a fresh instance are `binary_sensor.mvp_smoke_a` and
`binary_sensor.mvp_smoke_b`, both device class `smoke`. Their names are **MVP Smoke
A** and **MVP Smoke B**. Check their actual IDs in the entity list; HA owns ID
generation. No devices are attached to these sources.

Helpers omit `initial`, so HA restores their saved states across a normal
container restart. On first startup they default to off. Do not use Developer
Tools to overwrite a source for the restart scenario: those state overrides are
temporary, are not a saved device report, and template evaluation or restart
replaces them. If Developer Tools > States is used for extra exploratory states
such as `unknown`, mark that separately and return to helper-driven state before
continuing acceptance. Such an override is never a physical-device test.

Find the AlarmMesh overviews through **Settings > Devices & services > AlarmMesh
> Entities**. English translation resources provide **AlarmMesh smoke report** and **AlarmMesh
source availability**; this Dutch-configured instance displayed **AlarmMesh
rookmelding** and **AlarmMesh bronbeschikbaarheid**. During the English profile
check, those existing entity names stayed Dutch; the form text, enum labels and
standard smoke-state labels changed to English. Changing profile language did
not rename the registered entities. Do not assume their generated entity IDs after renaming.
Use the integration/entity detail screens for visible behavior and Developer
Tools > States only to confirm raw `on`/`off`/`unavailable` and enum values.
The smoke device class can render `off` as a translated clear-state label;
interpret it as *geen rook gemeld*, never as guaranteed safety.

## Manual scenarios and results

For every scenario record the operator, date, actual version/commit, actual IDs
and observed result. Use only **PASS**, **FAIL** or **NIET UITGEVOERD**. A FAIL
must include reproduction steps and expected/actual output as a review finding;
do not modify production code during this acceptance step.

All rows below refer to HA **2026.10.4**, integration commit **ddc9d49**, and
UI execution on **2026-11-11** by the assistant, delegated by the user. Onboarding
was completed by the user beforehand. The second column remains the reproducible
procedure; the evidence column records actual observations.

Actual sources: `binary_sensor.mvp_smoke_a` and `binary_sensor.mvp_smoke_b`.
Original entry: `01M768DTQ39FPG324A6ZTBZR0X`. Final recreated entry:
`01M768ZWQ91ARP5FTVW2KED18M`. Default overviews:
`binary_sensor.alarmmesh_rookmelding` and `sensor.alarmmesh_bronbeschikbaarheid`.
For scenarios 8-10, both names and IDs were changed to
`AlarmMesh acceptatietest rook` / `binary_sensor.alarmmesh_acceptatie_rook` and
`AlarmMesh acceptatietest bronnen` / `sensor.alarmmesh_acceptatie_bronnen`.
Those customizations survived both reload and actual container restart. Unique
IDs were not exposed by the inspected UI; this run verifies visible names/IDs
and absence of duplicates, not a separate raw-registry unique-ID comparison.

| # | Concrete steps and expected result | Result | Actual UI evidence |
| --- | --- | --- | --- |
| 1 | Complete onboarding. Settings > Devices & services > Add integration > AlarmMesh. Select MVP Smoke A and B and submit. Exactly one AlarmMesh entry and two overview entities appear, without an AlarmMesh device. Record both actual overview names and entity IDs; also record registry/unique IDs if exposed by this frontend. | PASS | User onboarding complete. Add-integration UI was repeated after scenario 11; A+B selected, success dialog, one entry with exactly two entities and no device association. |
| 2 | Set all four helpers off. Both source reports are off. Smoke overview is off (geen rook gemeld); availability raw state is `complete`. | PASS | All four helper switches off: observed smoke off and availability complete in the rendered States UI; Dutch detail view showed Niet gedetecteerd and Alle bronnen melden een status. |
| 3 | Switch A smoke on; keep A/B reachable. Source A and smoke overview become on. Availability remains `complete`. | PASS | Switched A smoke on in dashboard: source A Detected/Gedetecteerd; overview raw state on, availability complete. |
| 4 | Keep A smoke on/reachable; switch B unreachable on. Smoke stays on and available. Availability becomes `incomplete`. | PASS | With A on, switched B unreachable on: overview remained on, availability changed to incomplete. |
| 5 | Switch A smoke off while B stays unreachable. Smoke overview becomes `unavailable`, never off. Availability stays `incomplete`. | PASS | With B unavailable, switched A smoke off: overview became unavailable while availability stayed incomplete; no false off result. |
| 6 | Switch B unreachable off with both smoke helpers off: smoke off, availability `complete`. Repeat recovery with A smoke on: smoke must remain on while B recovers. | PASS | Recovered B first without smoke (off/complete), then with A still on (on/complete). Recovery did not clear the active smoke report. |
| 7 | Configure AlarmMesh to select only B, with B off/reachable. Toggle A smoke/unreachable; neither overview changes. Toggle B smoke: overview follows B. Configure A+B again and verify current results immediately. | PASS | Saved B-only through options; A smoke/unreachable changes left output unchanged. B smoke toggled output on. Restored A+B and observed current on/incomplete before returning helpers off. |
| 8 | Customize both overview names and optionally their entity IDs in entity settings. Record IDs, unique IDs and names. Reload the AlarmMesh entry. Customizations and unique IDs remain identical; no duplicate entries/entities appear. | PASS | Customized both names and entity IDs as recorded above; UI Reload succeeded and rendered states retained both customizations, with exactly two entities. Raw unique IDs not exposed in inspected UI. |
| 9 | Disable only the smoke overview in entity settings. Toggle source smoke and reachability: the availability overview still reports current completeness. Re-enable smoke and allow HA's existing delayed reload (about 30 seconds); it immediately shows current smoke. Optionally repeat with availability disabled and smoke enabled. | PASS | Disabled smoke entity through UI. Availability continued to update to incomplete. Re-enabled smoke, observed HA 30-second delay notice, then current smoke on and availability incomplete. |
| 10 | Restore A+B selection and both overviews enabled. Set A smoke on, A reachable, B smoke off, B unreachable on. Record helper/source/overview states and customized identities. Run the Restart command below (an actual container restart), wait for HTTP readiness and refresh/log in. Helpers and current reports should restore: smoke on, availability `incomplete`; overview names, entity IDs and unique IDs stay unchanged. Finally restore all helpers off. | PASS | Guarded Restart changed actual container StartedAt from 2026-11-11T15:52:13.081752206Z to 2026-11-11T21:41:00.590883501Z. Reloaded browser: A smoke on, B unavailable, overviews on/incomplete, both custom names and entity IDs preserved. Helpers later reset off. |
| 11 | Remove only AlarmMesh through its integration menu. Its entry and overview entities disappear; the simulated sources/helpers remain. Add AlarmMesh again and select A+B. Exactly two current-result overviews appear. A removed/recreated config entry has a new identity; old customized overview IDs are not guaranteed for this new entry. | PASS | Deleted only the AlarmMesh test entry via UI: no overview states remained, simulation dashboard/helpers persisted. Added AlarmMesh again with A+B: success, new entry ID above, exactly two default overviews off/complete. |
| 12 | In the test user's profile, inspect both English and Dutch UI language settings. Inspect AlarmMesh selection/options descriptions, overview names and translated enum labels. Test an empty selection: understandable validation, existing saved selection unchanged. Dutch wording says geen rook gemeld without a safety guarantee. Record language/screens inspected; user-customized names intentionally override default translated names. | PASS | Inspected Dutch and English options text and complete/incomplete enum labels, and English initial setup form. Empty selections produced Select at least one smoke detector / Selecteer minstens één rookmelder; saved A+B remained intact. Profile restored to Dutch. Existing default names remained Dutch in English profile; not_configured label was not reachable via normal source-required setup and remains automated-test coverage only. |

If scenario 11 leaves customized names from earlier steps unavailable for default
translation inspection, inspect new entities before renaming them. No screenshots
or evidence files containing account details should be committed.

## Technical results, separately from UI acceptance

Actual version: **2026.10.4**. Actual integration commit: **ddc9d49**.

| Check | Result | Evidence / scope |
| --- | --- | --- |
| Existing containers and files preserved | PASS | Initially only `wp-pg` existed, stopped. No existing runtime directory or port-8124 listener was found; no user container/file was overwritten or removed. |
| Example configuration | PASS | Compose schema and HA `python -m homeassistant --script check_config --config /config` succeeded before web startup. |
| Integration load | PASS | Separate HA bootstrap with the example template sources successfully added AlarmMesh, produced no-smoke/complete and unloaded it. No owner account created. |
| Exact HA version | PASS | Official image and running container report `2026.10.4`. |
| Local-only web publication | PASS | Actual Docker port mapping is `8123/tcp -> 127.0.0.1:8124`; HTTP responds locally. No other published port. |
| Container isolation | PASS | Separate Docker bridge, privileged=false, no hardware devices, no host network; repository integration mount has RW=false. |
| Git exclusion | PASS | `config/mvp-acceptance/configuration.yaml`, `.storage/auth` and technical-check data match the existing ignore rule. No account/token added to tracked files. |
| Onboarding/authentication | PASS | Preparation initially verified unfinished onboarding and unauthenticated API rejection. The user subsequently completed onboarding; UI acceptance used their existing authorized browser session. No authentication bypass or credential access. |
| Actual container restart | PASS (technical only) | Container `StartedAt` changed from `2026-11-11T13:48:58.949771758Z` to `2026-11-11T13:58:19.569710506Z`. This predates onboarding and does not pass manual scenario 10. |
| Stop/start instructions | PASS | The guarded Stop and Start commands were exercised, retained the existing test container/configuration and returned to running with localhost HTTP 200. |
| New tooling lint/format | PASS | Ruff 0.17.4 lint and format check succeeded in Linux. PowerShell parser accepted the start/stop script. |
| Diff scope | PASS | Only environment examples/tooling, this guide, README and development documentation changed; production integration, existing tests, dependencies and CI are unchanged. |
| UI scenarios 1-12 | PASS | Executed in the signed-in test browser on 2026-11-11; see actual observations and scope limits above. Scenario 10 used a real container restart. |
| Physical smoke/device validation | NIET UITGEVOERD | Outside scope; only simulated sources exist. |

Existing pytest results are not used as a substitute for the executed UI rows.
This accepts the specified simulated-source MVP scenarios only. Physical-device
behavior, real smoke detection and safety certification remain untested and
outside scope. No new functional step or publication is authorized by this report.

## Stop, start, restart and optional cleanup

From the repository root:

```powershell
# Stop, preserving all local configuration and the test account:
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Stop
# Reuse the same container; configuration is checked before starting:
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Start
# Actual container restart, preserving configuration:
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Restart
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Status
```

Wait for the local HTTP page after starting/restarting. **Reload** on an
integration entry is not a container/process restart and does not pass scenario
10. Never use `docker system prune`, broad container removal, or delete an
existing user's configuration as part of this test.

No cleanup is automatic. If you later choose to remove only this test
environment, first stop it, verify the exact container ownership label
`org.alarmmesh.purpose=mvp-acceptance` and the mounts above, then run:

```powershell
docker rm alarmmesh-mvp-acceptance
docker network rm alarmmesh-mvp-acceptance-web alarmmesh-mvp-acceptance
```

These commands intentionally do not delete `config/mvp-acceptance/`. Keep it if
you need the test account, saved helper states or evidence. Any later deletion of
that exact directory is a separate user choice; never include it in Git.

## Configuration references

- [Home Assistant Container configuration checks](https://www.home-assistant.io/docs/tools/check_config/)
- [Template state and availability](https://www.home-assistant.io/integrations/template/)
- [Input boolean state restoration](https://www.home-assistant.io/integrations/input_boolean/)

The examples and bootstrap were validated against the pinned image, rather than
assuming that newer documentation guarantees this version's behavior.
