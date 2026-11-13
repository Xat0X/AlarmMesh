# Disposable Marketplace and HA backup acceptance

This procedure uses **Home Assistant Container 2026.11.1**, simulation sources
only, and an independent writable installation. Actual outcomes are recorded once
in the [acceptance matrix](acceptance-matrix.md). Earlier file-copy checks in
[release packaging](release-package.md) remain separate evidence.

## Isolation and preparation

Use a new `config/installer-acceptance/<run-id>/` directory (Git-ignored), a unique
container/network name and labels `org.alarmmesh.purpose=installer-acceptance`
and `org.alarmmesh.run=<run-id>`. Record these values, the exact image, actual HA
version, configuration path, mounts and URL in local `current-run.json`.

Copy the existing [simulation configuration](../dev/mvp-acceptance/configuration.yaml)
and [dashboard](../dev/mvp-acceptance/ui-lovelace.yaml) into that new configuration;
give the instance an unmistakable simulation name and enable `backup:`. Run
HA's configuration check before starting the web environment. Check that the
chosen loopback port is free, then publish only `127.0.0.1:<port>:8123`.

The only mount is that run's writable configuration directory at `/config`.
**Do not mount the repository integration:** Marketplace must download its own
files into `/config/custom_components/alarmmesh`. Use the official
`ghcr.io/home-assistant/home-assistant:2026.11.1` image without host networking,
privileged mode, hardware, Docker socket or other installations' configuration.
Assert the version inside the container before using the browser.

The installer needs outbound Internet for GitHub. Its dedicated ordinary Docker
bridge is **not a firewall against LAN egress**. No real devices, production
configuration, discovery setup or MQTT connection belong in this environment.
A separate restore target uses its own new config and loopback port. The first
attempt with an **internal** Docker network served HA inside the container but
could not expose localhost through this Docker Desktop setup. The owner then
explicitly authorized an owned ordinary bridge for this restore only. It also
permits outbound/LAN reachability. Keep the original stopped while the restored
external installer connection runs; never use both concurrently.

## Installer and checkpoint

1. Verify the browser origin belongs to the new localhost instance. The owner
   completes test-account onboarding and GitHub authorization in HA's own
   Marketplace flow. Never read or record passwords, authorization codes or tokens.
2. Follow [installation](installation.md), adding the repository link and
   installing the revision actually offered. Do not copy an integration payload.
   Verify downloaded Python, manifest, translations and brand files against that
   exact Git revision; retain only file paths and hashes in a local inventory.
3. Select simulated A+B. Observe exactly two overviews, no associated device,
   off/complete, on/complete, on/incomplete, unavailable/incomplete and recovery
   using only the four simulation helpers.
4. Customize both overview names and entity IDs through their HA settings.
   Record these and the selected sources in a local checkpoint. Set A smoke on
   and B unreachable on: the expected checkpoint is **on/incomplete**.
5. Inspect the installer's reinstall/version menu. If only the current branch
   revision is offered, reinstall that revision and follow its HA restart repair.
   Check selection, customized identities and the checkpoint after restart. This
   is **identical-payload reinstall**, not an upgrade between product versions.

## Real HA backup and separate restore

Use **Settings > System > Backups**. Let the owner handle backup setup and keep
the emergency kit/key privately; do not open or capture its contents. Configure
local storage only, then create a named manual backup of the recorded checkpoint
through HA. Record the successful UI outcome, local archive path, size and
SHA-256 without unpacking private configuration or authentication data.

Container backups contain HA settings and optionally history, including the
integration files and saved test configuration. They do not back up the Docker
image or host. Logs, caches and nested backup archives are excluded. Preserve
the source configuration and original archive throughout the exercise.

Start the second, fresh 2026.11.1 target and use onboarding's **Upload backup**
route. Upload only this test archive. The owner enters any required key and
later signs in using the restored test account. Let HA perform the restore and
restart; never edit `.storage` or unpack the archive into place yourself.
Verify version, installed files, selection, customized names/IDs, entity count,
checkpoint source values, subsequent helper changes and branding. Stop that
target before resuming the original installer connection.

After preserving the backup checkpoint, test entry deletion and Marketplace
uninstall in the original. Check that the two overviews disappear, integration
files are removed and simulation helpers remain. Reinstall through Marketplace,
configure A+B again and check current processing. A new entry can have new
identities. Finish with all four helpers off and off/complete.

This is a supported HA backup exercise only when HA actually creates and restores
the archive. A stopped-file copy is different evidence. Neither proves a
production recovery, physical smoke detection or a differing-version migration.

## Controlled start/stop, keeping local data

From the repository root, select **one exact** retained `current-run.json`:

```powershell
$run = Get-Content -Raw 'config/installer-acceptance/<run-id>/current-run.json' | ConvertFrom-Json
$instance = docker inspect $run.container | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $instance.Count -ne 1) { throw 'Container not found' }
if ($instance.Config.Labels.'org.alarmmesh.purpose' -ne 'installer-acceptance' -or
    $instance.Config.Labels.'org.alarmmesh.run' -ne $run.run_id) {
    throw 'Installer ownership mismatch'
}
docker stop $run.container
if ($LASTEXITCODE -ne 0) { throw 'Container did not stop' }
```

After the same ownership check, `docker start $run.container` resumes it. Do not
start source and restored external installer sessions together. Do not prune,
delete configuration/keys/backups, or apply these commands to the older port-8124
and port-8125 environments. Screenshots and all runtime evidence remain ignored.

## Remaining UI-only steps

The actual run's installer/backup/restore results are in the central matrix.
Computer Use stopped before entry deletion because it could not confidently
verify the browser URL. Do not bypass that policy. The following is the minimum
remaining manual sequence, **only on the disposable source at
http://127.0.0.1:8126/**:

1. Confirm the source container/run from its `current-run.json`. Keep the restored
   8127 container stopped. The original's current simulated checkpoint is A
   smoke on, B unreachable on, AlarmMesh on/incomplete. Its successful encrypted
   HA checkpoint backup remains retained; do not delete it.
2. Open **Settings > Devices & services > AlarmMesh > entry ⋮ > Delete** and
   confirm for this disposable entry only. Refresh its entity list: both
   overviews must disappear. On the simulation dashboard, change a simulation
   helper and check that no old overview returns or keeps processing. Record
   this as UI evidence; it does not inspect an in-memory callback directly.
3. Open **Settings > Marketplace > AlarmMesh > ⋮ > Uninstall** (the encountered
   Dutch repository menu calls this **Verwijderen**); follow the actual
   confirmation and restart repair. Verify the integration files are absent
   from this run's own `config/custom_components/alarmmesh/`, while the four
   simulation helpers and two template sources still work.
4. Install AlarmMesh again through that same Marketplace repository and record
   the actual offered revision. Follow its restart prompt if shown. Configure
   A+B again; require exactly two new overviews and correct current processing.
   Deletion/re-add may intentionally generate a new entry identity. The retained
   dashboard references the old customized IDs; replace those references only
   in this disposable dashboard, or customize the new entities through HA.
5. Turn **all four simulation helpers off**. Confirm source A/B clear, smoke
   off and availability complete. Retain dated screenshots locally without
   account/key information. Report observed outcomes before marking the central
   matrix PASS; none of these steps was performed after the policy stop.

A separate differing-version installer upgrade must wait for an actually
offered, approved distinct product version. Do not publish one solely to complete
this checklist. HACS and physical-device checks are not covered by this run.

Official procedures checked **2026-11-13**:
[Marketplace](https://www.home-assistant.io/integrations/marketplace/),
[backup integration](https://www.home-assistant.io/integrations/backup/),
[backup creation and restore](https://www.home-assistant.io/common-tasks/general/backups/),
[Container common tasks](https://www.home-assistant.io/common-tasks/container/).
