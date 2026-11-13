# Changelog

## Unreleased

### Integrated local interface

- Add the packaged AlarmMesh sidebar panel: overview, selected detectors and
  details, HA areas and organizational groups, with Dutch/English text and
  phone/tablet/light/dark styling based on the supplied design and artwork.
- Push existing runtime status through HA-authenticated admin WebSocket commands;
  reuse the shared home result and the unchanged status evaluator for subsets.
- Persist entry-owned groups with stable IDs, atomic version-1 HA storage,
  bounded input and revision conflicts. Keep stale source references visible.
  No alarm/device actions, observations history or second source selection.
- Add real HA backend/auth/storage tests, light locked DOM tests, packaged-asset
  allowlisting and expanded exact-version compatibility checks. Earlier hosted
  and installer evidence remains dated and does not validate this local code.
- Complete a separate actual simulation UI pass, including group persistence
  after a real container restart, connection loss/recovery, source changes and
  Dutch/English light/dark phone/tablet layouts. Correct narrow phone cards to
  use the available width; retain dated before/after evidence in the matrix.

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

- Exercise actual Marketplace installation and identical-revision reinstall on
  HA 2026.11.1, plus encrypted HA backup and supported restore into a separate
  disposable Container. Record preserved selection/identity and live simulation
  processing. Marketplace uninstall/re-add remains open after a browser-policy
  stop; retain the precise remaining steps and the dark-background README-logo
  contrast finding, without changing product code or artwork.
- Reconcile the actual bbd767a checkout with the earlier a300d39-based review;
  verify its 249-test hosted run and both compatibility artifacts, retain dated
  prior evidence, and name the concrete reviewed candidate without publishing.
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
