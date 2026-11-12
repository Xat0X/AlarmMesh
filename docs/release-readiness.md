# Read-only MVP release readiness

Prepared **2026-11-12**, base **0e7ba380de2cc1a267580de8973ab3b9515f21a3** plus
the local review changes. This is release preparation, not publication approval.
The current manifest is `0.0.1`; no version, minimum, dependency or schema changes
are proposed merely to publish. [Review evidence](review-results.md) records the
actual checks and limits. [Changelog](../CHANGELOG.md) is intentionally Unreleased.

## Ready for code/document review

- Two read-only overviews, fixed source selection and shared status calculation.
- English/Dutch forms and state labels; supplied branding and local serving tests.
- One reproducible [validation route](development.md#complete-local-validation)
  and exact-version [compatibility matrix](compatibility.md).
- [Installation/update/removal](installation.md), [troubleshooting](troubleshooting.md)
  and [passive pilot record](read-only-pilot.md), without production identifiers.
- No alarm actions, physical commands, automatic source selection or stale-report
  threshold. No smoke reported is not a guarantee of safety.

## Still open

| Item | Required next action / owner |
| --- | --- |
| License and artwork distribution rights | Owner chooses a license and confirms rights to distribute the supplied artwork. No license is selected here. |
| Release revision/version | Owner chooses whether/when to release, the reviewed revision and version/tag policy. A future tag must agree with the manifest version. |
| New UI smoke test | Complete onboarding in the fresh disposable instance, then execute the pending checklist in review results. Browser controls were blocked in this task. Historical UI acceptance is retained separately. |
| GitHub workflow execution | After a separately authorized commit/push, observe the workflow on GitHub. Local commands/static validation do not prove hosted execution. |
| Physical pilot | Real smoke transitions, physical connection failure/recovery and production restart remain unvalidated. Plan any future physical acceptance separately under manufacturer instructions. |
| Public catalog | Separate owner decision and future submission; no listing or approval claimed. No repository settings changed. |

## Installation and rollback notes

Use the built-in Marketplace on HA 2026.11+, or the documented HACS route on the
older 2026.10.4 baseline. Review the installed revision, update through that
installer and follow its restart repair/prompt. Back up HA before any future
owner-authorized update. No automatic production update occurs here.

Rollback should restore the owner's known-good HA backup including integration
files and saved configuration, following Home Assistant's supported restore
procedure. Do not promise a downgrade will preserve arbitrary future schemas or
use the install-another-version dialog as a backup substitute. To stop using this
MVP, remove the AlarmMesh configuration and uninstall its files through the
installer; selected source integrations remain separate. No storage edits or
live commands are part of this document.
([Official Marketplace version/update guidance](https://www.home-assistant.io/integrations/marketplace/))

## Catalog preflight, checked 2026-11-12

The official catalog requires the supported repository layout/metadata, README,
description/topics/issues, branding, successful HACS validation and hassfest, and
a full GitHub release. Owner/major-contributor eligibility and a separate catalog
PR also apply. Locally present files and a passing hassfest are not proof that
remote settings, HACS validation or catalog review have passed. No catalog PR,
GitHub settings change, release or branding submission is performed here.
([Official catalog rules](https://contributors.home-assistant.io/marketplace/guides/catalog/),
[repository requirements](https://contributors.home-assistant.io/marketplace/reference/repository-structure/))

## Draft release text — not published

> AlarmMesh read-only MVP — version and revision pending owner decision.
>
> Select existing smoke detector entities in Home Assistant and view combined
> smoke reports plus source-information completeness. Configure sources later
> through options. Active smoke takes priority during partial source loss;
> insufficient information becomes unavailable, never silently no smoke reported.
> The integration rebuilds from current local HA states and offers English/Dutch
> texts and light/dark branding.
>
> Technically checked with simulated sources on exact HA 2026.10.4 and 2026.11.1.
> Development baseline remains 2026.10.4. Follow the installation/update guide and
> back up before updating. A branch installation revision can differ from the
> manifest version. Real-device evidence is limited to the user-reported pilot;
> physical transitions, connection loss and production restart remain unverified.
>
> This version does not operate sirens, notify, link alarms, mute/reset or test
> devices. It is not a certified fire alarm system and does not replace certified
> standalone detectors. No smoke reported is not a safety guarantee. See known
> limits, troubleshooting and rollback guidance before use.
