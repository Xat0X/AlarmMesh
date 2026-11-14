# Release readiness

## Proposed next test release: 0.1.0-beta.4

The unpublished working tree adds ordinary Companion notifications, existing HA
script actions and reviewed self-test requests to the beta.3 linking/catalog base.
The [finishing review](finish-review.md) records actual checks and package identity.
Proposed source: `b2f3d719a86cffb0a533fa5650dce624fd2275f2` plus the reviewed local
diff; there is no new commit or hosted-CI result for it. Remote beta.3 was verified
at that SHA on 2026-11-14; no beta.4 tag was observed. Manifest remains beta.3.

Keep this a default-off, opt-in pre-release after explicit owner approval, visual
acceptance and CI for the eventual exact release commit. Preserve existing explicit
choices. No production or physical acceptance is claimed. Installation/update uses
the existing Marketplace/HACS route; the new checks exercise local package copies,
not installer end-to-end behavior. Rollback from group schema 3 needs the matching
pre-update configuration backup; replacing Python alone is insufficient.

Draft release text: “AlarmMesh beta.4 adds separately configured phone notifications,
ordered incident scripts, reviewed built-in self-test requests and clearer incident
details. New automation defaults off. Current reports remain separate from requested
execution and physical results. Tested HA targets are exactly 2026.10.4 and 2026.11.1.
Read the supported-device conditions and back up before updating.”

Owner decisions remain license, artwork distribution rights, version/publication
timing and any later catalog participation. No release, tag, version bump, settings
change or catalog application is performed by this preparation.

## Historical catalog test release — 0.1.0-beta.3

Prepared 2026-11-14 at the owner's request for installation review on an existing
Home Assistant. Reviewed product baseline:
`e092fd6ead2739f3603bb7583a3c57accb506048`.
This release changes only version metadata and release documentation.

Manifest and tag use **0.1.0-beta.3**. Publish as GitHub pre-release, never latest
stable, only after all hosted checks for the exact release commit succeed.
The normal source-folder installer route, dependencies and minimum HA remain
unchanged. No live HA installation or physical action is part of publication.

New groups and old groups without linking remain disabled. Explicitly enabled
configurations are preserved: the installation notes tell the owner to disable
them before updating for this review. Catalog recognition never enables linking.
BSD-2 requires its same-device broadcast setting to explicitly report off;
the changed authority requires re-review of earlier broader local assignments.

The product baseline passed hosted tests (367 backend, 20 frontend), hassfest
and both HA compatibility jobs, including 20 runtime and 14 driver checks per
version. The release metadata commit must pass its own workflow before publication.

See [release notes](releases/0.1.0-beta.3.md) for installation, default-off review,
support coverage, Bosch behavior and backup-based recovery. Technical driver
checks do not establish complete provider/radio or physical device acceptance.
Earlier dated catalog/UI evidence remains historical in the support guide.

Outstanding: owner-observed upgrade/recovery of this payload, physical acceptance,
and previously recorded license/artwork/catalog-admission decisions. This work
does not make stable-release or certification claims.
