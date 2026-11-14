# Device support and evidence — development after beta.2

AlarmMesh continues to read any explicitly selected, valid Home Assistant
`binary_sensor` with device class `smoke`, including unknown models. Recognition
does not enable linked sounding. Linking remains **off by default** and requires
an exact administrator-confirmed source/target preview. No physical detectors
were accessed or commanded for this work.

Use **AlarmMesh > Compatibility** to search brand/model and filter provider and
function. Each model shows detection, activation, automatic stop and read-only
test-status assessments, with information, requirements, gaps and primary links
under a disclosure. Technical source assessments are in English; the interface
labels are Dutch/English. The [compact model index](device-catalog.md) is available
without a running HA instance. The authoritative per-provider A–F assessment is
the [review snapshot](../dev/catalog/review.json).

## Inventory and denominators

Checked **2026-11-14**, starting from clean main
`8c088d4a354c35106ab105b64827ceb7fc1233a8` (manifest stays `0.1.0-beta.2`).
Current work is uncommitted; earlier release/CI results do not cover this work.

The official website dataset contains 5,868 rows. Its actual filter predicate
`row.exposes.includes("smoke")` selects **67 model/variant rows** and **59 page
links**. Resolving documented converter `whiteLabel` relationships yields **52
canonical definitions and 15 additional variant/white-label rows**. These are
different denominators. All 52 definitions and all 67 rows have separate reviews
for Zigbee2MQTT and ZHA. No guessed model-name filter or website scrape is used.

Of the definitions, 47 describe smoke detectors. The remainder are BYUN contact
proxy, CTM acoustic detector, HESZB heat detector and two SIRZB dedicated sirens.
Their presence under the website's smoke tag is not evidence of optical smoke
detection. They are clearly labelled. A heat/acoustic/contact source still needs
an actual eligible HA smoke entity; none is automatically selected or fabricated.

| Function | Zigbee2MQTT | ZHA |
| --- | --- | --- |
| Catalog assessed | 52/52 definitions; 67/67 rows | 52/52 definitions; 67/67 rows |
| Read smoke | Generic eligible HA smoke entities; documented smoke expose for 50 definitions, including three non-optical types; two dedicated sirens excluded as smoke-detector claims | Generic eligible HA smoke entities; standard IAS/quirk availability is conditional on the actual signature and provider-created entities |
| Reviewed activation contract | 17/52 definitions, covering 21 website rows | 10/52 definitions, conditional on the exact raw model/manufacturer and actual control/features; marketing aliases alone do not authorize ZHA |
| Activation only | 16/52 definitions | All 10 action definitions |
| Automatic stop | 1/52: existing HS1SA-E-PLUS automation-only MQTT route | 0/52 |
| Read self-test status | 28/52 have a reviewed readable flag/enum; read only if HA exposes it | Read only when HA exposes known test-status keys; no blanket model-count claim |
| Physical acceptance in this work | **0** | **0** |

“Implemented” means the HA action contract has software checks, not physical
device acceptance. It does not mean every firmware/provider version exposes the
control. Standard IAS ZHA profiles without a model-specific quirk are conditional
routes requiring an actual typed siren with the reviewed features and tone.
All 15 marketing-alias ZHA assessments remain explicitly unconfirmed; their
Zigbee2MQTT white-label evidence is never inherited as ZHA activation proof.
The catalog filter uses each variant's own provider assessment.

## Implemented action families

The four published beta.2 profile identities remain stable. Eight additional
profile contracts share three small adapters: HA select, siren and switch.

| Family | Added or expanded route | Limits |
| --- | --- | --- |
| Heiman | MQTT automation select for Lover, HM-636THV-AC-M, S1-M, S1-TL, S1-TL-AI, S2-E; PLUS keeps its existing route | New models activation only; automation property similarity does not establish model-specific safe stopping |
| Heiman ZHA | Actual basic IAS siren for PLUS raw identities, HM-636THV-AC-M and S1-TL | Different from MQTT cascade control; one 60 s request, no automatic stop |
| Aqara | Documented JY-GZ-03AQ MQTT alias; ZHA `buzzer_manual_alarm` switch for `LUMI/lumi.sensor_smoke.acn03` | Existing `linkage_alarm` must already report on; firmware 21/0021/0.0.0_0021 blocked; no mute or stop |
| Develco/frient/Cavius | SMSZB-120 MQTT aliases 94430 and 2103; existing raw ZHA SMSZB-120 route retained | Marketing ID 94430 is not assumed to be a ZHA raw model; one 60 s IAS request |
| Standard IAS warning | MQTT HS15A-M, Climax SD-8SCZBS, SMaBiT AV2010/24 and /24A, HESZB-120 (+Frient 94431); conditional ZHA raw-model routes | Actual HA siren required; explicit burglar/Burglar and duration support; basic HESZB ZHA uses fixed tone; heat identity is not optical smoke |
| Bosch Twinguard | MQTT alarm select: `fire` | Only idle `stop` can be claimed; manual fire/burglar/pre-alarm is never adopted; no stop |
| Bosch BSD-2 | MQTT siren `alarm_control`, explicit `smoke` | Same-device `broadcast_alarms` must explicitly be off; missing/unavailable/on blocks execution. Never changed automatically. No invented duration support; no stop/mute |
| ShinaSystem FAM-300Z | MQTT `force_smoke_alarm` switch | Same-device `remote_control_permission` must already report on; never change permission or clear local smoke |

Names alone cannot authorize an action. Device/config-entry/platform identity,
unique IDs, control options/features, prerequisites, firmware and the current
source state are rechecked before dispatch. No visible-name or entity-suffix
matching is used. Shared Tuya TS0601 identifiers require the manufacturer
fingerprint for catalog recognition and have no invented sounder profile.
Changed new profile contracts change their fingerprint and require review;
published contracts are frozen. Existing mappings/options are not rewritten.

Manual or unknown control values are never claimed as idle. All routes retain
the existing bounded executor, independent origin lifetime, shared-target
deduplication, no retries after a failed attempt, target-local-smoke exclusion,
self-test-origin exclusion and detached old runtimes. Automatic stopping remains
exclusive to owned PLUS automation-only activations with explicit release.

## Read-only detector details

The detector page shows reliable manufacturer/model/provider metadata, source
kind, source/control availability, registry firmware and available same-device
battery, low-battery, fault/maintenance, smoke-level and self-test values. It does
not create extra entities or poll devices. Unknown/missing information is **Not
available**, never a fabricated healthy value. State-change time is labelled
**Value changed**. It is not last contact; recent radio contact is not established.
Complete only means current usable HA source values, not detector health.

Requirements, physical limitations and technical entity IDs are folded away.
Only current group members appear in target assignment. A detection-only member
can remain a smoke source. The exact confirmation and stopping limits remain
mandatory. Adding a catalog model, opening a page or loading HA never enables
linking or issues a test/action.

## Concrete upstream gaps

- **Tuya/Moes/Woox alarm enable, silence and test controls:** not evidence of an
  external zoemer command; no generic MQTT payload or cluster escape hatch.
- **TS0601 variants:** signature coverage differs. The reviewed ZHA quirk has
  `TZE200_0zaf1cr8` without the leading underscore, whereas Z2M lists
  `_TZE200_0zaf1cr8`; these are not silently equated. Each other known fingerprint
  remains recorded separately. Missing quirk evidence does not rule out standard
  IAS smoke detection.
- **Heiman ZHA cascade automation-only:** current quirks explicitly expose basic
  IAS warning and leave the proprietary cascade route pending upstream Zigpy API
  support. AlarmMesh implements only the existing HA basic siren contract.
- **Schneider W599001/W599501/755WSA:** remote siren is documented as not
  implemented upstream. Detection remains usable through an eligible HA entity.
- **HALO/HALO+:** hush, test and weather playback do not establish external
  smoke-siren activation. No such commands are offered.
- **SIRZB-110/111:** dedicated sirens, not selected smoke-detector targets. The
  ZHA smart-siren quirk removes default IAS smoke. SIRZB-110 Z2M documentation
  restricts firmware to <=1.7.1; 1.9.3 is incompatible. No speculative target is
  added to increase counts.
- Other models without a reviewed control remain detection only. Model-specific
  missing/unconfirmed functionality and source links are in every catalog entry.

No upstream issue/PR, production quirk, device setting, pairing or firmware change
was made. Future physical acceptance needs a separate assignment under
manufacturer instructions. This document gives no physical test command.

## Reproduce inventory and checks

The snapshot pins five primary repositories: website `df1ef460`, converters
`afdaa028`, Zigbee2MQTT `3c841fdf`, ZHA `2da1a5b5`, quirks `b07fa768` (full hashes
in the snapshot). Converter extraction uses official npm **26.131.0** separately;
the package metadata has no gitHead, so package-to-commit byte identity is not
claimed. The snapshot is reviewed data, not generated actuation authority.

In an ignored development directory, use Node 24.22.1 and install only the pinned
research package with `npm install --ignore-scripts --no-audit --no-fund
zigbee-herdsman-converters@26.131.0`. Then run:

```text
node dev/catalog/extract.cjs <ignored-npm-directory> <ignored-upstream.json> dev/catalog/review.json
python dev/catalog/build.py
python dev/catalog/build.py --check
pwsh -NoProfile -File ./dev/validate.ps1
```

The optional third argument asserts exact canonical/variant relationships.
Review newly extracted signature and expose changes against
`dev/catalog/review.json`; do not automatically grant newly discovered functions.
The build generates the runtime literal and compact index, with no startup or
panel network requests. No node_modules, upstream source archives or device pages
belong in the integration package.

Compatibility runs retain the original 17 scenarios, add three catalog/adapter
scenarios and run 13 additional driver checks on each exact **2026.10.4** and
**2026.11.1** image. The driver phase uses actual HA MQTT discovery/templates and
actions with official Mosquitto **2.0.22** on the run's internal Docker network,
synthetic topics only, no published ports. It also executes actual installed ZHA
basic/advanced IAS actions and Aqara quirk/switch code with endpoint I/O mocked.
It is not a running Zigbee2MQTT/converter transport or full ZHA discovery/radio
test. Registry fixtures remain explicitly identified as metadata mocks.

## Current evidence

Results below are from **2026-11-14**, base
`8c088d4a354c35106ab105b64827ceb7fc1233a8` plus this uncommitted catalog work.
No hosted CI, installer acceptance or physical acceptance is claimed for these
changes. Evidence paths are local and Git ignored. Historical release results
remain in the [central acceptance history](acceptance-matrix.md); the earlier
catalog report and browser-access block remain recorded in
`config/device-catalog/62e5cdaf5c314c80a7105ae14c611659/completion.json`.
After user onboarding, supported native Chrome control of the verified localhost
simulation became available. No browser/authentication bypass was used.

| Check / evidence category | Actual result | Evidence under repository root |
| --- | --- | --- |
| Complete `dev/validate.ps1` / automated | **PASS**, exit 0 | `config/validation/aae793399e7241fc80fa35834bf1b788/validation-result.json` |
| Linux Python 3.14 / HA 2026.10.4 / automated | **356 tests PASS**, all 79 original status tests retained | Same directory: `pytest.xml`, `baseline.log` |
| Node 24.22.1 / actual panel DOM / automated | **19 tests PASS**, original assertions retained, stronger translation check | Same directory: `frontend.log` |
| Ruff lint/format, official hassfest, PowerShell parse/failure checks, Compose, cleanup / automated | **PASS** | Same directory: phase logs and `validation-result.json` |
| HA requested=actual 2026.10.4 / automated | **20 runtime + 13 driver checks PASS** | `config/compatibility/2026.10.4/d66608b293b64459a2d12a69fdca2619/compatibility-result.json`, `technical-result.json`, `driver-result.json` |
| HA requested=actual 2026.11.1 / automated | **20 runtime + 13 driver checks PASS** | `config/compatibility/2026.11.1/94d98e956fa04576a09acf5ec72292bb/compatibility-result.json`, `technical-result.json`, `driver-result.json` |
| Official inventory re-extraction / automated | **52 definitions / 67 rows PASS**, exact reviewed relationships | `config/device-catalog/62e5cdaf5c314c80a7105ae14c611659/catalog-reproduction.log`, `research/reproduced-inventory.json` |
| Deterministic package and allowlist / automated | **PASS**, 29 files, two identical ZIPs | `config/release-packages/catalog-ui-8008d045-a/inventory.json`, `catalog-ui-8008d045-b/inventory.json` |
| Native Chrome / independently observed UI | **PASS** for the representative scenarios below, HA **2026.11.1** | `config/catalog-ui/8573738c06d9408ba8899fb588de8fc2/ui-8008d045-6f74-4089-b6b6-b816bb6300f2/observations-final.json` and cropped PNGs |
| Scope, links, privacy and protected files / local audit | **PASS** | Same UI evidence directory: `scope-audit-final.json` |
| Physical smoke, sound, source connection loss and self-test | **NOT PERFORMED**, every model | No physical device or production network accessed |

The two final local test packages have SHA-256
`52c95beaa1112fa4e8bc27dc9fc300efd7df56c3b28a4420327980c805d3e23e`.
They are not published releases or distribution-approved artifacts. Required
modules, translations and unchanged brand files are present; runtime data,
research sources and developer tools are excluded. Earlier packages/reports are
retained locally and do not substitute for this final snapshot.

Installed offline driver packages were ZHA **2.3.1**, quirks **2.3.0**, Zigpy
**2.3.0** on HA 2026.10.4; ZHA **2.4.3**, quirks **2.4.1**, Zigpy **2.4.1** on
2026.11.1. Both used Paho **2.1.0**. These versions are recorded by the driver
script. Real HA MQTT discovery/templates/actions on the private synthetic broker
and offline ZHA method/quirk serialization are the precise evidence. Full
Zigbee2MQTT/converter transport, ZHA discovery/pairing/radio and physical-device
acceptance remain **NOT PERFORMED**. UI fixtures use mock metadata/actions and do
not add driver evidence.

### Corrections demonstrated during this work

Actual-driver checks exposed beta.2's exact-`int` feature test rejecting real HA
`SirenEntityFeature` IntFlags. A permanent regression failed before correction;
accepting integer bitmasks while excluding `bool` fixes it. Two further failing
regressions showed that a selected ID repurposed as a non-smoke source could
initiate an activation or prematurely release an owned incident. Current origin
identity now gates planning and dispatch; contradictory metadata is not explicit
release. Evidence is `feature-enum-before.log` and `origin-class-both-before.log`
in the ignored research run above. Existing independent/overlapping incident
assertions are retained.

The visual review also found a broken Dutch accent and an activation filter
labelled too narrowly as activation-only although it includes the stop-capable
PLUS. The label now reads **External sounder / Externe zoemer**; the Dutch
implemented label is corrected. The stronger translation regression failed
first (`frontend-before.log` in the UI evidence directory). Module, translation
and CSS cache keys were advanced together; the corrected texts were then
visibly verified. No new actuation authority or status rule was introduced.

`status.py`, all 79 original status cases, dependencies, domain/config-entry and
stored schemas, overview unique IDs, manifest/minimum versions, supplied artwork
and CI are unchanged. All previous assertions remain. Local full validation was
repeated for the final product snapshot; no hosted result is claimed for it.

### Observed catalog UI acceptance

Verified simulator: **http://127.0.0.1:8130/alarmmesh**, HA **2026.11.1**, own
labelled container, only localhost binding, read-only product/fixture mounts and
separate ignored configuration/account. The user completed onboarding; the
agent neither read nor created passwords/tokens. These are actual visual/native
UI observations, separate from automated DOM and driver tests.

| Scenario | Observed result | Result |
| --- | --- | --- |
| Selection and validation | NL new config, required-source error; EN options prefilled A+B; invalid empty edit and explicit close during smoke preserved selection/monitoring. Changed to B while A stayed on: A stopped affecting the outcome. Selected all 16 through options. | PASS |
| Overview entities | Integration page showed exactly two entities and no device count/link. | PASS |
| Smoke/completeness | Off/complete, on/complete, on/incomplete beside unavailable B, indeterminate/incomplete after explicit A off, recovery to off/complete; active A immediately recognized after selection/reload. | PASS |
| Many models / long names | 16 mixed-brand/provider sources; D/L/M/P detection only, B/G/J prerequisites; long O name wrapped on desktop/phone/tablet. | PASS |
| Provider-specific catalog | Alias search; ZHA marketing alias unconfirmed and excluded by activation filter; MQTT external-sounder filter 21/67 rows; corrected Dutch text visible. | PASS |
| Read-only details | Battery 72%, registry firmware, changed-value disclaimer; ZHA problem/self-test on while smoke stays off. B control unavailable stayed distinct from usable smoke source. Folded requirements and technical IDs inspected. | PASS |
| Explicit linking | Only five chosen A/C/D/F/I members appeared in assignment; D stayed a source. C/F/I targets produced 12 exact preview edges and activation-only limits. No acknowledgement: rejected. Back preserved draft; explicit confirmation saved while all sources were off and request count was zero. | PASS |
| Independent failed target | A smoke plus C mock failure produced exactly three requests: C failed, F/I accepted with no automatic stop. Reopening did not retry. No physical sound/transport. | PASS |
| Themes / locales / sizes | NL/dark and EN/light desktop; browser-emulated phone 390x844 and tablet 768x1024. Original icon/title readable, long rows/dialogs fit, no horizontal overflow observed. Tablet navigation label wraps over two lines. | PASS |
| Keyboard / labels | Native selects operated with arrow/End/Return and visible focus; Escape closed detector detail. Search/provider/function/group controls had accessible labels. HA options used its explicit Close button. | PASS |
| Connection loss / recovery | Only own container stopped: panel replaced stale current result with disconnected/unconfirmed notice. Restart automatically restored actual off/complete 16/16 and cleared process-local old requests/results. | PASS |
| Final state | All mock helpers off, 16/16 usable sources, no smoke, group retained with linking **off**, zero current mock requests after restart; NL/dark, DevTools/emulation closed. | PASS |

Representative checks are not every locale/theme/viewport permutation, a formal
screen-reader audit or physical mobile-browser acceptance. Screenshots remain
local and are faithfully cropped to remove browser chrome, account sidebar and
DevTools. No user screenshots or credentials are added to Git. Historical
pre-fix/transient captures are excluded from acceptance evidence.

The mock outputs do not emulate physical sound duration. Clearing source smoke
does not invent a stop for activation-only targets. Restart of only this owned
simulator reset its process-local outputs after linking was disabled. There were
no physical self-tests, mute/stop commands, radio operations or live changes.
Existing 8124-8129 environments were left untouched.

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Catalog -Port 8130 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Catalog -Port 8130 -Action Stop
```

Stop preserves account/configuration under ignored `config/catalog-ui/`. The
guarded launcher checks owner labels, mounts, version and localhost port. This
web instance uses its own ordinary bridge (outbound access is possible), no
broker, hardware or real configuration. Only technical check runs contain their
own broker on an internal network; their temporary resources are cleaned up.

Primary API references, checked 2026-11-14:
[HA MQTT discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery),
[siren entity contract](https://contributors.home-assistant.io/core/entities/siren/),
[switch contract](https://contributors.home-assistant.io/core/entities/switch/).
Model/provider evidence uses pinned official repositories in each assessment.
