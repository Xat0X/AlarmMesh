# Interface test release — 0.1.0-beta.1

Prepared 2026-11-13 at the owner's request for testing on an existing HA install.
The baseline is 82c9844 plus release metadata/documentation only. No product
behavior, dependencies, minimum HA version or stored config-entry schema changes.

The manifest and proposed tag both use **0.1.0-beta.1**. Publish as a GitHub
pre-release, not the latest stable release, only after the release commit's full
GitHub Actions workflow succeeds. The source-folder installer route is unchanged.

User-facing instructions and known limitations are in the
[release notes](releases/0.1.0-beta.1.md). The
[acceptance matrix](acceptance-matrix.md) retains dated test and UI observations.
Earlier installer/backup evidence validates its recorded payload and does not
claim an existing-installation upgrade test for this beta.

The interface baseline passed 277 backend tests, 11 frontend tests, hassfest and
14 compatibility scenarios on each exact HA 2026.10.4 / 2026.11.1. The metadata
release commit still requires its own hosted run before publication.

## Remaining after beta publication

- Owner pilot: update from the installed revision, inspect preserved source
  selection and identities, use all four screens, create a group and verify
  persistence after an owner-planned restart. Retain a known-good backup.
- Marketplace uninstall/re-add and differing-product upgrade coverage remain
  separate from the recorded identical-payload install/reinstall checks.
- Physical smoke transitions, actual device loss/recovery and production recovery
  are not established by simulation or by this release.
- The wide README logo's dark-renderer contrast finding remains documented.
- License selection, artwork redistribution confirmation and catalog admission
  remain owner decisions; no license or catalog approval is added by this work.

No automatic production installation, alarm action or stable release is performed.
