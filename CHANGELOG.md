# Changelog

## Unreleased

### Current read-only MVP

- Select existing smoke binary sensors through configuration and options, with
  backend validation and one AlarmMesh configuration per HA instance.
- Track selected local HA states in shared memory and expose exactly two
  read-only overviews: smoke reports and source-information completeness.
- Preserve smoke priority during partial source loss; indeterminate smoke is
  unavailable, never silently off. Rebuild from current sources on load.
- Keep entity identities stable through reloads and source changes; preserve
  existing empty foundation configurations and clean up subscriptions.
- Supply English/Dutch texts and the owner's existing light/dark artwork.

### Review and release preparation

- Verify hosted CI and both compatibility artifacts for a300d39; complete a new
  English/Dutch simulation UI pass and consolidate current evidence in the
  [acceptance matrix](docs/acceptance-matrix.md), preserving historical reports.
- Add deterministic local test packaging with an explicit 18-file inventory,
  SHA-256 and five regression cases; package no accounts or runtime data.
- Add isolated file-replacement, process-restart, removal/re-add and stopped-file
  snapshot-recovery checks on both exact HA versions. Compared integration
  payloads are identical; this is neither installer end-to-end nor HA backup
  feature acceptance. Prepare a concrete 0.1.0 proposal without changing 0.0.1.
- Add the README logo header, practical troubleshooting, passive pilot evidence,
  release checklist, draft release text and a scoped roadmap.
- Provide one local validation command and a separate CI compatibility matrix
  for exact HA 2026.10.4 and 2026.11.1, retaining the pinned 2026.10.4 test suite.
- Reject stale reports, preserve local failure tracebacks and report cleanup
  failures as failures. Upload only sanitized summaries in the compatibility CI job.
- Add image/HA-serving tests and focused tooling failure regressions; existing
  status rules and tests are unchanged. See [review results](docs/review-results.md).

No release/tag is created here. The manifest remains `0.0.1`; license and release
version decisions remain with the owner. Physical smoke detection, actual device
connection failure and production restart acceptance remain open. Sirens,
notifications, alarm linking, mute/reset and device test actions are future
proposals, not included functionality.
