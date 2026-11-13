# Read-only MVP release proposal

**New local interface work:** the separate [panel package](panel.md) adds new
product code and organizational group storage after the committed bbd767a MVP.
The proposal/evidence below remains historical for that committed payload, not
a hosted or installer approval of the new local code. Review the current panel
results in the [matrix](acceptance-matrix.md) before choosing any release source.
No version/tag change is made by the interface work.

The new panel now has its own completed simulation UI pass: four screens,
group CRUD/persistence, real test-container restart, live connection loss/recovery,
source changes, Dutch/English and phone/tablet/light/dark. A narrow phone-card
layout was corrected and inspected again. The final full route passes 277 Linux
tests, eleven DOM tests and fourteen technical scenarios on each exact HA version.
See the matrix for hashes, paths and evidence limits. These local checks do not
close the historical installer/physical-release gaps or create a new hosted run.

Updated **2026-11-13** against actual checkout
**bbd767aa2766f55a2a2a62c10e9df18390d1270f**, which already contains the
earlier a300d39-based preparation. The [current acceptance matrix](acceptance-matrix.md)
is the authoritative results list; earlier dated reports remain historical.
No release, manifest bump or publication is performed here.

## Concrete candidate

Propose **0.1.0**, titled **AlarmMesh 0.1.0 — Read-only MVP**: the first explicitly
packaged pre-1.0 read-only MVP, rather than continuing the foundation's `0.0.1`
identifier. This is a proposal for the owner, not a version change. The current
manifest and generated local test ZIP still say **0.0.1**.

Product/review candidate: exact **bbd767aa2766f55a2a2a62c10e9df18390d1270f**,
now verified with 249 hosted tests and both compatibility artifacts. Its product
payload is identical to a300d39. Release source should include these reviewed
documentation corrections and a deliberately approved matching manifest/tag
version, followed by fresh hosted validation. No final release SHA can be named
before those future authorized changes are committed. Hosted success for bbd767a
does not cover new local edits. A read-only GitHub check on 2026-11-12 again found
no existing releases or tags; the proposed name/tag was unused at that time.

The candidate delivers source selection and backend validation, passive tracking,
smoke priority during partial information loss, two read-only overviews, stable
identity on reload, English/Dutch texts and the supplied artwork. There is no
schema migration or new product functionality in this preparation.

## Evidence and remaining technical boundaries

- Hosted a300d39: 244 tests, and hosted bbd767a: 249 tests; Ruff, hassfest and
  both exact-version compatibility artifacts independently inspected. The full
  simulation UI sequence is observed on the unchanged a300d39 payload in 2026.10.4;
  bbd767a's normal test UI state was separately rechecked.
- Reproducible [local package and file-update checks](release-package.md) pass
  on exact **2026.10.4** and **2026.11.1**, retaining the 2026.10.4 test baseline.
  Package inventory/hashes, separate process restarts, options/identity retention,
  removal/re-add and stopped-file recovery are recorded centrally.
- Previous 0e7ba38, a300d39 and current bbd767a integration payloads are identical.
  File replacement is tested; migration between different product versions is not.
- Actual Marketplace link installation and identical-`bbd767a` reinstall on
  **2026.11.1** are now observed in a new disposable instance, with the owner's
  own test onboarding/GitHub authorization. Downloaded files match the exact
  commit; customized entity IDs/names and the on/incomplete checkpoint survive
  the required HA restart. HACS and a differing-product-version upgrade remain
  separate; see the [current matrix](acceptance-matrix.md).
- The recovered copy of stopped test files remains **different evidence** from
  the new actual HA backup exercise. HA 2026.11.1 has now created an encrypted
  local manual checkpoint archive through its supported UI. Supported onboarding
  restore into another fresh 2026.11.1 Container succeeded: the owner entered the
  key and signed in; restored files, selection, customized identities, checkpoint
  and live source processing were then independently checked. This is not a
  manual extraction, production recovery or HA OS/Supervisor test.
- Actual Marketplace uninstall/fresh reinstall remains **NIET UITGEVOERD**:
  Computer Use's URL-confidence policy stopped browser control before deletion.
  No workaround was used. The [remaining UI-only steps](installer-acceptance.md#remaining-ui-only-steps)
  retain the source and successful backup. A future differing-version upgrade
  still needs its own acceptance.
- The icon is visually readable on light/dark integration UI backgrounds and
  appears correctly in Marketplace after restart. The actual Marketplace README
  renderer shows the light wide logo on a dark background with low contrast.
  This new visual finding remains open; it is not a status-processing defect.
- Real smoke transitions, physical loss/recovery, production restart and
  separately observed physical self-test behavior remain open. No safety
  certification, catalog approval or physical reliability is claimed.

## Installation, update and recovery

Use [the installation guide](installation.md): built-in Marketplace on HA
2026.11+, older HACS route on tested baseline 2026.10.4, repository
`https://github.com/Xat0X/AlarmMesh`. Review the offered revision, install, follow
restart prompts, then configure at least one smoke source and inspect both
overviews. Only **2026.10.4 and 2026.11.1** are technically checked; this does not
promise every future version. Adding a link is not catalog admission.

Before an owner-authorized update, retain a known-good HA backup including
integration/configuration and record the installed revision. Use one installer,
review update notes and follow its restart repair. Rollback should restore the
known-good backup using [Home Assistant's supported procedure](https://www.home-assistant.io/integrations/backup/).
The backup feature was actually exercised in a disposable Container instance;
the [matrix](acceptance-matrix.md) records exact scope and evidence. No production
recovery was tested. Do not promise that choosing an older version preserves
arbitrary future schemas.
Deleting the integration entry stops tracking; uninstall files separately through
the installer. Source integrations remain independent.

## Owner decisions before publication

| Decision | Concrete proposal / required confirmation |
| --- | --- |
| Project license | Owner chooses the license; none is assumed or added. |
| Supplied artwork | Owner confirms redistribution rights for all packaged artwork, including derivative packaged PNGs. Technical checks do not establish rights. |
| Version, revision and timing | Approve or replace 0.1.0; choose publication timing and the reviewed successor revision. Then separately authorize matching manifest/tag changes and hosted CI. |
| Catalog participation | Decide later whether to seek admission; no application or remote settings change is included. |

Physical acceptance is a separate pilot activity under the
[passive observation protocol](read-only-pilot.md), not a request to force smoke,
remove batteries, interrupt radio/MQTT or run a self-test now.

## Catalog preflight, rechecked 2026-11-12

Official rules distinguish a custom repository from catalog admission: supported
layout/metadata, README, description/topics/issues, branding, validation and a
published release are required for the catalog. Owner/contributor eligibility and
a separate catalog PR also apply. No license choice, settings change, HACS
catalog validation/submission or approval is inferred from passing hassfest.
([Catalog rules](https://contributors.home-assistant.io/marketplace/guides/catalog/),
[repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/),
[release/version rules](https://contributors.home-assistant.io/marketplace/guides/releases/))

## Draft release text — not published

> **AlarmMesh 0.1.0 — Read-only MVP** (proposed; revision pending approval)
>
> Select existing Home Assistant smoke detector entities and view combined smoke
> reports plus source-information completeness. Change sources through options.
> Active smoke takes priority during partial source loss; insufficient information
> is unavailable, never silently no smoke reported. Each load rebuilds from current
> local HA states. Exactly two overviews, stable reload identity and English/Dutch
> texts are included.
>
> Technical simulation checks cover exact HA 2026.10.4 and 2026.11.1; development
> baseline remains 2026.10.4. A fresh UI check covers 2026.10.4. Read the installation
> guide and back up before updating. Actual Marketplace installation/reinstall
> and supported HA backup/restore were checked on 2026.11.1 with simulations.
> Marketplace uninstall/fresh reinstall remains open after a browser-policy stop;
> no differing-product-version upgrade is claimed. File-copy checks are separate.
> The Marketplace-rendered wide logo has a known dark-background contrast issue.
> A default-branch installer revision can differ from the manifest version.
>
> The physical pilot confirms installation/current display/reload by user report
> only. Physical smoke transitions, real connection failure and production restart
> remain unverified. Complete means usable selected HA state values, not heartbeat
> freshness or detector health; a self-test does not prove smoke detection.
>
> AlarmMesh does not operate sirens, notify, propagate alarms, mute/reset or test
> devices. It is not a certified fire alarm system and does not replace certified
> standalone detectors. No smoke reported is not a safety guarantee. See the
> acceptance matrix, known limits and recovery guidance before use.
