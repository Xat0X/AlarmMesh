# Matter review results — 2026-11-16

Current local changes on clean starting main
`8522584942b136f5c919525c5d0040e7e4bf2c0e` (published beta.7).
No version, tag, commit or release was created. The historical 508 backend / 66
frontend tests and beta.7 visual results are not new Matter evidence.

The [Matter guide](matter-support.md) is the model/function matrix, source record
and user guide. This document is the central results list for this assignment.

## Automated and simulated evidence

Local evidence is ignored by Git, under
`config/matter-review/b4cab94925924a6a95f62b27db2dfc7a/`.
The final standard validation report and package inventory identify the local
changes; results apply to those bytes, not a new hosted CI run.

| Check | Evidence category | Result / reference |
| --- | --- | --- |
| New Matter contracts, registry identity/endpoints/bridges, mixed groups, CO isolation, maintenance, self-test lifecycle | Real HA test fixtures and mocked actions | See final validation report below; no radio or controller |
| Actual HA Matter descriptions and unique-ID mapping | Offline actual official HA classes, 2026.10.4 and 2026.11.1 | PASS in both driver reports; optional functions remain conditional on actual entities |
| Actual SelfTestRequest button | Actual HA button class, command I/O mocked | PASS; endpoint/cluster/command asserted, no network or real device command |
| HA registry source/control binding, test activity versus real smoke, interconnect, unload | Isolated HA fixture in both official images | PASS; ignored empty-data registry owner, no controller |
| Existing mixed-provider execution | Isolated synthetic MQTT broker, real discovery; actual ZHA classes/quirks with mock I/O | PASS on both exact versions; no production broker, radio or physical result |
| Local draft restore, stale revision, identity change, fresh acknowledgement, account isolation, expiry/tampering | DOM and local-storage unit tests | PASS; not a visual or real browser-reload observation |
| Simulator configuration, ownership, mounts and loaded HA version | Technical inspection, HA 2026.11.1 | PASS; localhost:8131 only, RO product/fixture mounts, no privilege or hardware |
| Simulator final rest state | Sanitized startup audit from the live owned simulator | PASS: 102 helpers off, test result idle, selected smoke off, no active test, all automatic output off, controller absent |
| Two deterministic integration-root packages | ZIP byte/inventory checks | PASS: 39 files each; details below |

Final standard route: **PASS**, `pwsh -NoProfile -File ./dev/validate.ps1`.
Linux Python 3.14, unchanged pinned dependencies/baseline HA 2026.10.4:
**533 backend tests**, **73 frontend tests**, Ruff lint/format, official hassfest,
PowerShell parse/fault checks, Compose and cleanup all PASS.

| Final evidence (local, Git-ignored) | Result |
| --- | --- |
| `config/validation/3a1a1c0351e0439997a327cf90638745/validation-result.json` | PASS, final complete route |
| Same directory: `pytest.xml`, `baseline.log`, `frontend.log`, `hassfest.log` | 533 / 73 passed; 0 invalid integrations |
| Same directory: `compatibility-2026.10.4.json` | Requested = actual 2026.10.4; 29 runtime + 20 driver checks PASS |
| Same directory: `compatibility-2026.11.1.json` | Requested = actual 2026.11.1; 29 runtime + 20 driver checks PASS |
| `config/matter-review/b4cab94925924a6a95f62b27db2dfc7a/scope-audit.json` | Protected bytes/original assertions, final ZIP bytes, local links and new-document privacy scan PASS |
| Same review directory: `simulator-audit.json`, `final-results.json` | Safe resting state and final source/package evidence |

The final validation export's 39 product files match the current source and final
packages byte for byte. No hosted run exists for these unpublished changes.
Intermediate failures remain in local logs: the initial 2026.11.1 fixture issue,
the deliberate before-fix regressions, and a Ruff line-length failure in the new
test name. The latter was renamed without changing its assertions before the
successful final full run. None is relabelled as a historical PASS.

## Demonstrated corrections

- A deliberately invalid saved Matter CO-only selection originally produced a
  smoke result. `co-saved-before.log` records the failing assertion. It now stays
  UNKNOWN/INDETERMINATE; new configuration also rejects the CO contract even if
  its device class was overridden. The pure smoke rules were not changed.
- A changed device identifier originally escaped source identity pinning.
  `device-identity-before.log` records the failure. The fingerprint now includes
  the opaque device identifiers; execution stays blocked pending exact review.
- The first 2026.11.1 driver run failed because HA correctly disabled entities
  under a disabled fixture entry. The fixture now uses an ignored registry-only
  owner, which HA does not set up. Production disabled-entity checks remain intact.
  This is fixture correction, not a claim that disabled real devices are usable.
- Loss of separate interconnect evidence during an already latched incident
  originally still allowed a late target assessment. `interconnect-before.log`
  records the failure. The current provenance gate blocks new dispatch, without
  clearing smoke, repeating activation or stopping the existing owned target.
- Restored drafts now include the Matter source fingerprint in identity checks,
  even when optional controls are absent. The revision is never refreshed silently.

Original Python tests and assertions remain unchanged; frontend regressions were
appended. `status.py`, the 79 status tests, manifest/dependencies, branding and
workflow files remain unchanged. The local scope audit verifies this separately.

## New visual matrix — not executed

HA 2026.11.1, same local revision/changes as above, owned simulator only.
Supported computer/browser inventory failed with **native pipe: os error 2** and
**browser access host unavailable**. No supported tab or app was available. No
authentication or browser policy was bypassed. No new screenshots were produced
or claimed; DOM tests and image serving do not substitute for visual observation.

| Language | Theme | Viewport | Result |
| --- | --- | --- | --- |
| Dutch | Light | 390×844 | NOT EXECUTED |
| Dutch | Dark | 390×844 | NOT EXECUTED |
| English | Light | 390×844 | NOT EXECUTED |
| English | Dark | 390×844 | NOT EXECUTED |
| Dutch | Light | 1024×768 | NOT EXECUTED |
| Dutch | Dark | 1024×768 | NOT EXECUTED |
| English | Light | 1024×768 | NOT EXECUTED |
| English | Dark | 1024×768 | NOT EXECUTED |

Remaining action: with supported browser access, inspect and screenshot source
selection, Matter help/details, provider filters, mixed groups, exact self-test
confirmation, unsupported controls, long names, empty states, reconnect and local
draft restoration. Exercise only SIMULATED helpers. Finish with every helper off,
idle result, automatic configuration off and no pending test. No viewport was
changed during this assignment. The existing account and selection are preserved.

## Simulator and packages

Open **http://127.0.0.1:8131/alarmmesh** with the existing local simulator account.
The simulator includes fictitious Matter A/B metadata and separate smoke, CO,
forwarded-interconnect, test, fault, end-of-service, battery and availability
helpers. Its owner is an ignored registry fixture; no Matter Server is configured.
The simulation self-test button changes only its own test helper; there is no
terminal success result. These fixtures are not actual commissioned devices.
New Matter sources were not automatically added to the existing selection.

The fixture emits `alarmmesh-simulation-audit.json` locally after startup, with
booleans/counts only. It does not contain accounts, tokens or HA snapshots.
The simulator's own Docker bridge permits outbound traffic; it is not a firewall.
No real provider, cloud account or device endpoint is configured or accessed.
Other web environments, including port 8124, were not touched.

Guarded stop, retaining account/configuration:

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```

Packages: `config/release-packages/matter-b4cab949-final-a/` and
`config/release-packages/matter-b4cab949-final-b/`, each with `alarmmesh.zip` and
`inventory.json`. Both contain the 39 reviewed integration files, including
`matter.py` and `frontend/drafts.js`. SHA-256 for both:

```text
50d4f58eca0e8ef69bb04ce09a816b475f7b319520d1d829d614abf415ca36d0
```

These are local test packages, not published or distribution-approved artifacts.
No installer, commissioning, Thread network, actual device self-test, physical
smoke detection, audibility, CO detection or physical connection-loss validation
was performed. All such acceptance requires a separate authorized procedure.

## Changed files


Product and interface:

- `custom_components/alarmmesh/__init__.py`
- `custom_components/alarmmesh/activity.py`
- `custom_components/alarmmesh/capabilities.py`
- `custom_components/alarmmesh/catalog.py`
- `custom_components/alarmmesh/catalog_data.py`
- `custom_components/alarmmesh/config_flow.py`
- `custom_components/alarmmesh/diagnostics.py`
- `custom_components/alarmmesh/frontend/drafts.js`
- `custom_components/alarmmesh/frontend/panel.js`
- `custom_components/alarmmesh/frontend/translations.js`
- `custom_components/alarmmesh/linking_runtime.py`
- `custom_components/alarmmesh/matter.py`
- `custom_components/alarmmesh/panel.py`
- `custom_components/alarmmesh/preview.py`
- `custom_components/alarmmesh/self_test.py`

Regression and compatibility tooling:

- `dev/catalog/build.py`
- `dev/catalog/review.json`
- `dev/frontend/panel.test.mjs`
- `dev/incident-acceptance/configuration.yaml`
- `dev/incident-acceptance/ui-lovelace.yaml`
- `dev/linking-simulation/alarmmesh_simulation/incident_fixture.py`
- `dev/linking-simulation/alarmmesh_simulation/matter_fixture.py`
- `dev/mvp-acceptance/check_drivers.py`
- `dev/mvp-acceptance/check_matter.py`
- `dev/mvp-acceptance/mvp-acceptance.ps1`
- `dev/release/package.py`
- `dev/tests/test-compatibility.ps1`
- `tests/test_matter.py`

Documentation:

- `CHANGELOG.md`
- `README.md`
- `docs/architecture.md`
- `docs/device-catalog.md`
- `docs/device-compatibility.md`
- `docs/matter-review.md`
- `docs/matter-support.md`
- `docs/panel.md`
- `docs/roadmap.md`


## Independent browser follow-up — 2026-11-16

The implementation-stage visual blocker above is historical. Matter details,
self-test confirmation and setup help have now been inspected in all eight
NL/EN × light/dark × phone/tablet browser combinations (24 screenshots).
The 24 matrix images and independent local review are linked from
`config/matter-review-followup/dc6a435d9db647088786bbcf1a9b2568/review.json`.
This is browser emulation, not physical-device acceptance.

Corrected numeric Matter product ID shown instead of the readable model name,
untranslated combination/detail labels, an empty dialog after cancelling a
standalone self-test, and clipping of long detail headings. Asset versions were
updated so existing browsers fetch the corrected stylesheet. Three new tests
(one backend, two frontend) were observed failing before correction and now pass.

Final full route `dc6a435d9db647088786bbcf1a9b2568`: **534 backend + 75 frontend tests PASS**; all standard
tooling PASS; each exact HA version (2026.10.4 and 2026.11.1) passed **29 runtime
+ 20 driver checks**. All 39 current product files match this validated export.
Two corrected packages, `config/release-packages/matter-review-followup-one/`
and `matter-review-followup-two/`, have identical SHA-256:
`0982ea69194cf6d3d87d3873b1b8a998c3dad5c50e7925b79b9887a9e0be78e3`. Earlier hashes apply only to earlier snapshots.

In-browser workflows additionally verified normal options selection of two Matter
fixtures, provider filtering, a mixed organizational group and actual browser-reload
draft restoration. Original name/members returned; linking/scripts stayed off;
saving cleared the draft and the temporary group was removed. One explicitly
confirmed virtual Matter self-test reached test-active; a separate simulated smoke
report appeared as an alarm and its source was shown. After helpers cleared, the
test ended **unknown, not a pass**. No real controller/radio/device I/O occurred.

Final simulator: four smoke-free test sources (A+B plus two Matter fixtures),
all helpers off, result helper idle, no active test, no groups/reminders/review
drafts and automatic outputs off. One mock request remains historically counted;
sounder request count stayed zero. Dutch/Auto and normal viewport restored.
No commit, push, tag, publication, production change or physical acceptance.
