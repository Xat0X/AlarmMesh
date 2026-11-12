# Troubleshooting the read-only MVP

Use the AlarmMesh entry under **Settings > Devices & services**. It has two
overview entities, not a device. Do not use test buttons, sirens or real-source
state overrides to troubleshoot AlarmMesh. See [installation](installation.md)
for installer actions and [the passive pilot](read-only-pilot.md) for observation.

| What you see | Meaning and next step |
| --- | --- |
| A source is absent from the selector | It must be an existing `binary_sensor` with device class `smoke`. Inspect its entity details and the upstream integration. AlarmMesh's own overview cannot be a source. A temporarily unavailable detector can remain valid if its smoke identity is still in HA's metadata. Do not change a different kind of sensor's class just to make it selectable. |
| A source was renamed or deleted | Selection stores fixed IDs. The old ID becomes missing; AlarmMesh does not follow the new ID automatically. Open **Configure**, replace the old selection with the intended smoke entity and save. |
| Smoke overview is `unavailable` | Without an active smoke report, some selected source information is unknown, unavailable or missing, or no sources are configured. This is an indeterminate result, not an explicit no-smoke report. Inspect the selected sources and the availability overview. |
| Source availability is `incomplete` | At least one selected source lacks a usable current `on`/`off` value. Active smoke from another source still takes priority. Inspect HA source availability; do not infer physical health or recent radio traffic from a cached state. |
| Source availability is `not_configured` | An older empty foundation configuration remains valid. Open **Configure**, select at least one existing smoke source and save. |
| You changed sources | A successful save of changed options reloads AlarmMesh automatically. Cancelled/invalid edits keep monitoring the previous selection; saving the same selection does not force a reload. If a source's ID changed, explicitly select the new ID. Ordinary source-state changes need no reload. |
| An overview is missing | Inspect the entry's entity list for a disabled entity. One disabled overview does not stop the other. HA may apply its normal delay when re-enabling an entity; do not add timers or duplicate the integration. |
| Logo is missing or old | Check the installer revision and whether an update/restart is pending. A local repository edit does not update a separate installation. Refresh the frontend after following the installer's restart guidance; image caches can retain an older image. No separate brands-repository submission is needed for the supplied local files. |
| Installer revision differs from `0.0.1` | The manifest version is integration metadata. A custom repository without a release can be installed at a default-branch commit hash. Record the offered/installed revision as well as the manifest version; neither proves that all later HA versions work. |
| Reload reports an error | Do not claim successful teardown. Retain a sanitized error and expected/actual behavior for review. The baseline's failed platform-unload state can require an owner-planned HA restart after the underlying fault is resolved; this task performs no live restart. |

`complete` means usable current values from all selected sources. It is not a
heartbeat, a freshness guarantee or proof of physical smoke detection. In Dutch,
“Niet gedetecteerd” must be understood as **geen rook gemeld**, not guaranteed
safety. Zigbee2MQTT's reporting/availability and HA entity availability are
separate observations; AlarmMesh only reads the latter.

Installation and cache guidance was rechecked on **2026-11-12** against the
[official Marketplace](https://www.home-assistant.io/integrations/marketplace/),
[HACS custom repositories](https://hacs.dev/docs/faq/custom_repositories/) and
[HA image guidance](https://contributors.home-assistant.io/core/integrations/brands/).
Share only aliases and sanitized details; keep identifiers, addresses, accounts,
tokens and raw logs out of public issues.
