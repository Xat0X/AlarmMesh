# Linked-sounding test release — 0.1.0-beta.2

Prepared 2026-11-14 at the owner's request. Product baseline:
`c3f02ea05e504ce2caec6d84759e31100419c36f`, including the independently reviewed
incident correction. This release changes metadata/documentation only.

Manifest and release tag use **0.1.0-beta.2**. Publish only as a GitHub
pre-release, without marking it latest stable, after the exact release commit's
hosted tests, hassfest and both compatibility jobs succeed. Source-folder
installation, dependencies and minimum HA version remain unchanged.

Existing beta.1 groups migrate in memory with linking false; new groups also
default false. Only explicit administrator-confirmed configuration can enable
sounder targets. No production installation or physical activation is performed.

The product baseline passed hosted CI with 323 backend tests, 15 frontend tests
and 17 simulated scenarios on each tested HA version (2026.10.4 and 2026.11.1).
The exact release metadata commit requires its own hosted run before publication.

See [release notes](releases/0.1.0-beta.2.md) for install, default-off review,
model/provider restrictions and backup-based rollback. The older beta.1 cannot
read the new persisted group payload; replacing files alone is not rollback.

Remaining: actual MQTT/ZHA driver and physical acceptance, owner-observed upgrade
and recovery on the existing installation, and previously recorded artwork,
license/catalog and wide-logo limitations. No stable-release or certification
claim is made. Earlier dated acceptance evidence remains historical.
