# Troubleshooting AlarmMesh

Use the AlarmMesh entry under **Settings > Devices & services**. It has two
overview entities, not a device. Do not use test buttons, sirens or real-source
state overrides to troubleshoot AlarmMesh. See [installation](installation.md)
for installer actions and [the passive pilot](read-only-pilot.md) for observation.

In the panel, open **Set up and check** on Overview, then open a group to
see its **Configuration check**. This reads current configuration and source
values without changing assignments, enabling linking or sending sounder commands.
The guide and check are available in English and Dutch.

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
| Installer revision differs from the expected release | Record the offered/installed release or commit as well as the manifest version. A repository default-branch installation can identify a commit instead of a tagged release. Compare against the release you intended to install; neither identifier proves that untested HA versions work. |
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

## Optional linked sounding: configuration checks

| What you see | Meaning and next step |
| --- | --- |
| Linking is off | Opening the guide or group does not enable it. Keep it off when inspecting a new installation. Turning linking off does not stop a device already sounding. |
| No sounders assigned | The group organizes smoke sources only. Use **Edit group** to inspect possible assignments. Detection support alone does not establish a supported activation route. |
| Assignment changed | The saved target no longer matches the current provider/control identity or reviewed profile. Inspect the intended source and target before saving a fresh assignment. Never substitute another entity just to clear the warning. |
| A prerequisite is missing | The check explains the current provider-specific reason, including the Bosch broadcast restriction. Inspect the named upstream setting; the check never changes it for you. |
| Activation only | The assigned route has no verified automatic stop. Inspect its documented limitations before choosing whether to enable linking. |
| Failed or uncertain request | Inspect the provider entity and connection. AlarmMesh does not automatically retry the request. A sent or accepted request is not proof of audible sound. |
| Assignments match | Current reported controls match the saved assignments. This does not test radio contact, physical smoke detection or audible sound. |

New source data updates an open group detail. Unsaved group edit forms retain
their entered values; a stale save is still subject to the existing revision
check. On lost connection the panel clears current status and closes details.
The configuration check adds no retry, test, mute or stop action.


## Optional incident outputs in the working tree

If a saved phone receiver is missing, check that the corresponding Companion
`notify.mobile_app_*` service still exists in HA; disable the obsolete receiver and
select the current one. AlarmMesh stores no phone tokens. A test needs its own
named-recipient confirmation. HA acceptance does not prove phone delivery.

For a missing/replaced script, reselect the current existing script in the group
and confirm the configuration. Invalid saves/cancel do not replace the saved list.
A failed or interrupted request is not automatically retried; inspect the incident
receipt and HA's local logs before deliberately changing anything. Unknown source
information cannot produce recovery actions.

No self-test button means there is no reviewed current model/provider/entity
contract. A request-only route ending unknown is expected when no explicit result
is exposed; do not infer success from silence, elapsed time or an accepted HA call.
[Contracts and current acceptance](incident-features.md) distinguish these outcomes.
