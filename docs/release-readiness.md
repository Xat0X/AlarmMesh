# Read-only MVP release proposal

Prepared **2026-11-12** against **a300d39b7eac4ef80ebb971e859b9866f2145c15**,
plus the local release-preparation changes. The [current acceptance matrix](acceptance-matrix.md)
is the authoritative results list; earlier dated reports remain historical.
No release, manifest bump or publication is performed here.

## Concrete candidate

Propose **0.1.0**, titled **AlarmMesh 0.1.0 — Read-only MVP**: the first explicitly
packaged pre-1.0 read-only MVP, rather than continuing the foundation's `0.0.1`
identifier. This is a proposal for the owner, not a version change. The current
manifest and generated local test ZIP still say **0.0.1**.

Product candidate: exact a300d39, whose integration payload is unchanged by this
review. Release source should be the **reviewed successor of a300d39 containing
this preparation**, with a deliberately approved manifest/tag version and a fresh
hosted validation result. No successor SHA can be named before those changes are
authorized and committed. Hosted success for a300d39 does not cover new local
tooling. A read-only GitHub check on 2026-11-12 found no existing releases or tags;
the proposed name/tag was unused at that time.

The candidate delivers source selection and backend validation, passive tracking,
smoke priority during partial information loss, two read-only overviews, stable
identity on reload, English/Dutch texts and the supplied artwork. There is no
schema migration or new product functionality in this preparation.

## Evidence and remaining technical boundaries

- Hosted a300d39: 244 tests, Ruff, hassfest and exact-version compatibility
  artifacts independently inspected; fresh simulation UI now observed on 2026.10.4.
- Reproducible [local package and file-update checks](release-package.md) pass
  on exact **2026.10.4** and **2026.11.1**, retaining the 2026.10.4 test baseline.
  Package inventory/hashes, separate process restarts, options/identity retention,
  removal/re-add and stopped-file recovery are recorded centrally.
- Previous 0e7ba38 and current a300d39 integration payloads are identical.
  File replacement is tested; migration between different product versions is not.
- Marketplace/HACS installation/update/uninstall **end to end remains untested
  in the disposable instance**. No installer authorization was configured.
  User-reported production installation is a separate evidence category.
- The recovered copy of stopped test files is **not HA backup-feature acceptance**.
  A supported HA backup/restore exercise remains separate.
- The icon is visually readable on light/dark UI backgrounds. The inspected
  screens do not display the wide logo; its theme selection in a live screen is
  unobserved. Exact six-file serving is technical evidence only.
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
This task did not test that backup feature or any production recovery. Do not
promise that choosing an older version preserves arbitrary future schemas.
Deleting the integration entry stops tracking; uninstall files separately through
the installer. Source integrations remain independent.

## Owner decisions before publication

| Decision | Concrete proposal / required confirmation |
| --- | --- |
| Project license | Owner chooses the license; none is assumed or added. |
| Supplied artwork | Owner confirms redistribution rights for all packaged artwork, including derivative packaged PNGs. Technical checks do not establish rights. |
| Version, revision and timing | Approve or replace 0.1.0; choose publication timing and the reviewed successor revision. Then separately authorize matching manifest/tag changes and hosted CI. |
| Installer acceptance | Arrange a disposable installer/GitHub session for end-to-end install/update/uninstall and a supported HA backup/restore check before claiming that coverage. No production credentials. |
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
> guide and back up before updating. File replacement/restart and stopped-file
> recovery were tested with identical old/new integration payloads; installer
> end-to-end and HA backup-feature acceptance remain separate. A default-branch
> installer revision can differ from the manifest version.
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
