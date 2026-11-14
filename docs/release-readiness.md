# Catalog test release — 0.1.0-beta.3

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
