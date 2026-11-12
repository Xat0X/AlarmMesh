# Local package and file-update/recovery checks

Reviewed **2026-11-12**, base **a300d39b7eac4ef80ebb971e859b9866f2145c15**.
See the [current acceptance matrix](acceptance-matrix.md) for actual outcomes.
This tooling never publishes, tags, changes metadata or accesses a live instance.

## Build a reproducible local test package

With Git and Python 3.14, from the repository root:

```powershell
$destination = "config/release-packages/$([guid]::NewGuid().ToString('N'))"
python dev/release/package.py --output $destination
if ($LASTEXITCODE -ne 0) { throw 'Package check failed' }
```

The destination must be new and Git-ignored. The builder uses only Git-visible
files in the reviewed integration inventory, rejects extras/missing files and
checks manifest/translation metadata. File order, timestamps and permissions are
fixed; stored ZIP entries avoid compressor-version differences. It validates
archive contents and writes `inventory.json` with the full base commit, local
change paths, manifest version, each file's size/hash and archive SHA-256.
`--revision <commit>` instead packages exact Git bytes without checking out or
altering that revision. Failures exit nonzero; existing output is never replaced.

The ZIP has integration-root contents. Extract **only into a separate test
installation's `custom_components/alarmmesh/`**. It contains these 18 files:

| Group | Exact paths inside ZIP |
| --- | --- |
| Python | `__init__.py`, `binary_sensor.py`, `config_flow.py`, `const.py`, `entity.py`, `runtime.py`, `sensor.py`, `status.py` |
| Metadata/text | `manifest.json`, `strings.json`, `translations/en.json`, `translations/nl.json` |
| Supplied brand assets | `brand/icon.png`, `brand/icon@2x.png`, `brand/logo.png`, `brand/logo@2x.png`, `brand/dark_logo.png`, `brand/dark_logo@2x.png` |

No repository metadata, tests, development tools, accounts, configuration,
databases, logs, `.git` or runtime data enter the ZIP. Root `README.md` and
`hacs.json` remain repository/installer metadata, outside the integration payload.
Original artwork provenance is in [branding](../assets/branding/README.md).

Current tested package (manifest **0.0.1**, local test only):

```text
config/release-packages/044f9c0c5cbf4c09aa14e8fd6e27aa38/current/alarmmesh.zip
SHA-256: 456534877ab1646ba84c6753057b3cb7f2ef46698074044388b592dd8dbfea19
```

The adjacent inventory records the working changes present when built. Those
changes are tooling only; integration bytes match a300d39 and 0e7ba38 exactly.
Independent package builds for both HA runs produced the same hash. Final review
inventory is `config/release-packages/review-a300d39-final/inventory.json`.
No file is a published or legally cleared release artifact.

## Relationship to the supported installers

Official guidance rechecked **2026-11-12**: the normal repository route installs
the self-contained integration folder. An optional release ZIP must contain the
files to extract into that folder, and requires explicit `zip_release`/`filename`
metadata and an attached release asset. **This repository keeps its existing
source-folder route; `hacs.json` is unchanged.** The local ZIP is for verification,
not a newly enabled installer channel. A future published release tag must match
the manifest version; no release currently exists.
([Repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/),
[official releases and ZIP format](https://contributors.home-assistant.io/marketplace/guides/releases/))

Owners should use [installation/update/removal](installation.md), not these
developer commands on their live system. Installer end-to-end acceptance remains
separate from the manual-file lifecycle below.

## Reproduce update, removal and recovery

Requires PowerShell 7, Git, Python 3.14 and Docker with Linux containers. Run the
[complete standard validation](development.md#complete-local-validation) as well:

```powershell
pwsh -NoProfile -File ./dev/release/check-update.ps1 -HaVersion 2026.10.4
pwsh -NoProfile -File ./dev/release/check-update.ps1 -HaVersion 2026.11.1
```

Only these exact versions are accepted and asserted inside each HA process.
Each run allocates new ignored `config/update-checks/<version>/<run-id>/` and
`config/release-packages/<run-id>/` directories. It builds previous **0e7ba38** and
current packages, extracts into its own installation copy, and runs:

1. A fresh simulated HA setup with A+B, customized names/entity IDs and known
   `on/incomplete` source conditions; normal stop flushes saved configuration.
2. A separate copy of those stopped test files as a recovery checkpoint. Verify
   the previous installation's exact files/hashes before replacing with the new
   package; boot a new HA process and assert preserved selection/all identities,
   exactly two entities and current source states. Exercise recovery, six-file
   brand loading, entry removal/detached old runtime and successful re-add.
3. Restore the checkpoint into **another new directory** and boot another HA
   process; assert the original customized identity/selection/state, then verify
   current changes and return helpers to off/complete.

The selected comparison commits contain **identical integration bytes**. This
proves replacement/restart persistence for this payload, not a migration or
upgrade between differing product versions. No stored HA files are edited to
force a result. The snapshot is not created/restored through Home Assistant's
backup feature, so it cannot prove that feature or a production recovery.
The owner's eventual recovery route should use
[Home Assistant backups](https://www.home-assistant.io/integrations/backup/)
and needs separate acceptance.

No web port is published. Each run has an owned internal Docker network and
read-only installation/tool mounts, with no host networking, privileged mode,
hardware, Docker socket, account or real HA configuration. Reports contain version,
commit, package hashes, stages and PASS/FAIL; original failures stay in ignored
logs. Assertion, process or cleanup failures make the command exit nonzero.
Only containers/networks with this run's exact name and ownership label are
removed; configurations, packages and snapshots remain for review. The port-8124
and port-8125 web environments are never used or changed by these checks.
