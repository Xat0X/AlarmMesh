# Install and remove AlarmMesh

[![Install AlarmMesh in Home Assistant](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Xat0X&repository=AlarmMesh&category=integration)

AlarmMesh is listed in both the Home Assistant Marketplace and HACS. Use an administrator account and set up your smoke detectors in their own Home Assistant integration first.

## Install from the catalog

| Your Home Assistant version | Where to find AlarmMesh |
| --- | --- |
| 2026.11 or later | Open **Settings → Marketplace**, search for **AlarmMesh**, open it and choose **Install**. |
| 2026.10.4 or a later 2026.10 patch, with HACS installed | Open **HACS**, search for **AlarmMesh**, open it and choose **Download**. |

The button at the top opens the listing in your own Home Assistant. If the Marketplace asks you to connect GitHub, follow its sign-in prompt. Choose the stable release for a regular installation. If the installer asks you to restart Home Assistant, do so before continuing.

If the Marketplace listing has a blank icon, you can still find **AlarmMesh** by name. The Marketplace fetches artwork from a separate index that syncs periodically. After installation, Home Assistant uses the images bundled with AlarmMesh. [How Marketplace icons work](https://github.com/home-assistant/brands#marketplace-icons)

## Configure AlarmMesh

1. Open **Settings → Devices & services → Add integration**, search for **AlarmMesh** and select it.
2. Select the smoke detector entities you want to monitor. Choose a Home Assistant binary sensor with the `smoke` device class, or the matching Zigbee2MQTT source below.
   - **Alecto SMART-SMOKE10** — select **Smoke state**.
   - **AVATTO ZSD20** — select **Smoke sensor state**.
   - **Sunricher SR-ZG9070A-SS** — select **Smoke alarm 1** and **Smoke alarm 2**. When creating a group, include both inputs so that a smoke report on either one is visible.
3. Open **AlarmMesh** in the sidebar. Check that the detector names and areas are recognizable. Use **Silent practice** to see how a smoke report would reach the rest of your home. Linked sound and automatic actions are off by default.

AlarmMesh supports one configuration entry. To change the selected detectors later, use **Configure** on that entry. If you rename a source entity ID, select its new ID there.

### Check the overview entities

| Detector state | Smoke overview | Source availability |
| --- | --- | --- |
| Every selected source explicitly reports clear | `off` | `complete` |
| At least one source reports smoke | `on` | Depends on whether every selected source is available |
| A source is unknown, unavailable or missing, and none reports smoke | `unavailable` | `incomplete` |

AlarmMesh is a supplementary tool. “No smoke reported” describes the readings available to Home Assistant. Keep certified smoke alarms in service and follow their manufacturer's instructions. For more on interpreting the readings, see the [simulated acceptance guide](mvp-acceptance.md) and [passive pilot](read-only-pilot.md).

## Update or uninstall

- **Marketplace** — Updates appear in **Settings → Updates**. To uninstall, remove the AlarmMesh configuration entry in **Settings → Devices & services**, then open **Settings → Marketplace → AlarmMesh → ⋮ → Uninstall**. Follow any restart prompt. [Marketplace instructions](https://www.home-assistant.io/integrations/marketplace/)
- **HACS** — Open AlarmMesh in HACS to download an offered update. To uninstall, remove the AlarmMesh configuration entry in **Settings → Devices & services**, then choose **⋮ → Remove** on the AlarmMesh page in HACS. Follow any restart prompt. [HACS repository dashboard](https://www.hacs.xyz/docs/use/repositories/dashboard/)

## Back up and recover

Before an owner-authorized update, create a known-good backup in **Settings >
System > Backups** and keep the emergency kit privately. Container's local
backups are under its own configuration's `backups/` directory. They include HA
settings and installed custom integrations, optionally history; they do not
preserve the Docker image or host. Use the supported backup upload/restore flow
on a separate suitable destination, then sign in with the restored account.
Never post archives, keys, account data or `.storage` in an issue.

The [actual disposable exercise](installer-acceptance.md) used an encrypted
HA-created archive and onboarding restore on exact **2026.11.1**, checking saved
selection, customized names/IDs and current simulation-source processing. It did
not test production recovery, a differing-version migration or HA OS/Supervisor.
Record the installed revision before updating and retain the backup until the
replacement is checked. Selecting an older installer revision is not a promise
that arbitrary later schemas can be downgraded.
([Official backup and restore procedure](https://www.home-assistant.io/common-tasks/general/backups/))

For developer installation in a disposable instance, see the [development guide](development.md). For detector selection or display issues, see [troubleshooting](troubleshooting.md).
