# AlarmMesh panel

The local interface organizes existing Home Assistant smoke reports. The local
review build also offers explicitly confirmed, default-off [linked sounding](linked-sounding.md)
through supported existing HA controls. No smoke reported is not a safety guarantee.

## Open and choose sources

After configuring AlarmMesh, administrators see **AlarmMesh** in the HA sidebar
at `/alarmmesh`. The panel uses your existing HA session and profile language
(Dutch/English), light/dark HA theme and local packaged assets. Other users keep
their normal access to the two overview entities; the management panel is admin-only.

Choose **Detectors > Choose sources** to open AlarmMesh's existing integration
page, then **Configure**. This is the original entity selector and backend
validation. Saving changed options reloads the integration. Cancelling or invalid
input leaves the saved selection unchanged. No second source selection is stored.

## Panel screens

- **Overview** shows the shared current smoke result, usable/selected source
  counts, assigned room count, group count, attention items and room cards.
  Active smoke is prominent and names the reporting detector and assigned room.
- **Detectors** lists only selected sources. Open a row for the real HA state,
  source entity, assigned area, known device/model/manufacturer and groups. The
  Home Assistant button opens HA's entity information. No model, battery level or
  radio-contact time is guessed. Available cached diagnostics are shown when HA exposes them; missing data stays unavailable.
- **Rooms** uses HA assignments, with entity assignment before device assignment.
  Only areas containing selected sources appear; others are under **No area**.
  Change assignments in HA, not in a second AlarmMesh room registry.
- **Groups** lets administrators create, rename, edit memberships and delete an
  organizational group. A detector can belong to several groups. Deleting asks
  for confirmation and does not delete any source. Empty groups are allowed.
  **Sound together** is optional and off by default. Choose exact controls, review
  the source-to-target preview and acknowledge its limits before saving. The
  [linking guide](linked-sounding.md) lists profiles and stopping restrictions.

Names are trimmed, nonempty and at most 64 characters. A group can contain at
most 256 distinct references; at most 100 groups are stored. If another browser
saved first, the stale form is rejected: close it and reopen before reviewing
and saving again. No background overwrite happens. Unsaved form input is retained
while ordinary status pushes arrive. Escape or Close exits a dialog.

## Understand incomplete information

Smoke always takes priority, including when a different source is unavailable.
Only explicit usable off reports from every selected source mean **No smoke
reported**. Unknown, unavailable or missing information without active smoke
means **Smoke status indeterminate**, never silently off.

Source completeness is separate: complete / incomplete / not configured.
Complete describes current usable HA values, not a heartbeat, recent radio
message or detector health. Self-test behavior is not proof of smoke detection.
The panel shows current reports only, without invented events/history.

Removing a source from AlarmMesh options leaves its group references visible as
**No longer selected**. A renamed source is not followed automatically. Edit the
group to remove stale references or select the intended new source through the
existing integration options first. A temporarily missing selected source stays
selected and can recover under the same ID. Groups are never silently deleted.

Groups persist through HA restart and entry reload, in versioned HA storage
separate from options. Explicit deletion of the AlarmMesh configuration removes
its group storage. Keep a suitable HA backup before deleting wanted configuration.
Connection loss or unloaded integration hides the current status; reconnect
loads fresh backend data. It does not reuse an old green result as current truth.

## Local simulation and evidence

For the new linked-sounding controls use the separate **Linking** mode on port
**8129**, documented in the [linking guide](linked-sounding.md#reproduce-the-simulation).
The existing 8128 environment and the historical observations below are separate.

With PowerShell 7 and Docker, from the repository root:

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Action Stop
```

The default new instance uses exact HA **2026.11.1**, loopback port **8128** and a
read-only integration mount. Start first checks the port/configuration and writes
owned resource metadata to ignored `config/panel-ui/current-run.json`. Existing
instances are verified before use; stop preserves configuration/account/groups.
No installer/backup environment is reused. The ordinary bridge permits outbound
traffic and is not a LAN-egress firewall; no real device, account or MQTT is configured.

Open **http://127.0.0.1:8128/**, complete local test onboarding, add AlarmMesh with
**MVP Smoke A+B**, then choose **AlarmMesh** in the sidebar or open
**http://127.0.0.1:8128/alarmmesh**. The separate **Overview** simulation dashboard
contains four helpers for simulated smoke/unreachability. They do not operate
devices. Use only those helpers for acceptance and finish with all four off.

The current prepared instance is already onboarded and configured. Open the
panel directly; do not repeat onboarding. It has A+B, one assigned HA room and
one unassigned source, plus a saved two-member **Simulatiegroep**, with all helpers
off. Its actual UI/restart results and local phone/tablet screenshots are in the
central matrix below. The commands above also document a new clean setup.

The [central acceptance matrix](acceptance-matrix.md) distinguishes automated
checks, actual UI observations and unperformed items. Earlier hosted CI covers
the old committed payload, not this new local interface. Physical smoke detection,
real connection failure and production restart remain separate unperformed acceptance.


## Device support in the current working tree

**Compatibility** searches the offline catalog by brand/model and filters provider
and function; it never discovers/selects/enables devices. **Detectors** separates
smoke reporting from sounder availability, with activation-only labels where no
safe stop is established. Details show available battery/fault/test/firmware
values; missing values stay unavailable. Value-change timestamps are not recent
radio contact. Requirements and troubleshooting IDs are folded away.

Target assignment shows only checked group members while retaining unsaved
choices when checking/unchecking a member. Non-controllable detectors can remain
smoke sources. Exact confirmation, actual control validation and existing source
selection rules remain in force. Read the [device guide](device-compatibility.md)
for model/provider conditions, reproducible evidence and the separate review URL.

## Guided setup and group troubleshooting (local development)

Open **Set up and check / Instellen en controleren** on Overview or Settings.
The same guide links to seven existing settings: detectors, HA rooms, groups and
incident origins, supported sounder targets, phone recipients, start/recovery
scripts, and a final configuration review. Each step shows its server-derived
state and count. Configured means saved/current metadata, not physically tested.
Optional-off and unsupported are distinct from attention needed. You can skip
steps, navigate away and return; saved configuration determines progress. There
is no second progress store or finish button that enables actions.

Open a group for a **Configuration check / Configuratiecontrole**. It distinguishes
disabled linking, no assigned sounders, stale source references, unavailable or
active smoke reports, changed mappings, model prerequisites, activation-only
limits and recorded request failures. Buttons open the existing detector details
or group form; there is no test, retry, mute or automatic enable action. Edits
still require the original validation and explicit confirmation before saving.

The check reads current pushed data and updates an open group detail. Existing
unsaved edit forms remain untouched. Losing the connection closes the detail and
clears current checks. Matching assignments do not prove that a device will sound
or that smoke detection/radio communication is healthy. Disabling a group does
not stop a sounder that is already active.

### Maintenance

Open **Maintenance / Onderhoud** from Overview or Settings. **Configuration to
review** lists missing sources/rooms, changed sounder mappings, missing scripts
and saved phone recipients, with a button to the existing editor or detector
details. Disabled options stay off; a stale saved assignment remains visible
until you explicitly replace/remove it. A saved phone recipient can be removed
in its form; cancelling discards that draft.

**Device reports** lists battery percentage, binary low-battery/fault indications,
source/control availability and the retained self-test request. The links must
belong to the same device/provider/configuration; unrelated entities are never
matched by their names. Missing, invalid and unsupported values remain Unknown.
At or below **20%** is a clearly labelled display threshold only. It changes no
smoke status, incident rule, command or notification. Off means no problem
reported in the available value, not that a detector is healthy. HA timestamps
do not establish radio contact. The retained self-test request, activity and
explicit device result remain distinct; absence of a result never means success.

### Incident details

Incident details show current smoke sources and rooms, involved groups and
sources still awaiting explicit no-smoke values. Request summaries separate
sounder, phone and script requests from device self-test results. Recorded start
and confirmed recovery times come from the existing bounded ledger; source
arrival order and individual command times are not recorded and are not invented.
An old recovery receipt is not current smoke truth. No new history is stored and
the existing retention period is unchanged. HA acceptance never confirms physical
sound, delivery or external script effects.

Current implementation evidence, the eight-combination visual checklist and the
existing onboarded review URL are in the [usability review](usability-review.md).


## Incident features in the current working tree

**Settings** now contains Companion recipients, per-recipient toggles, previews and
separately confirmed test notifications. The compatibility catalog is accessible
there. **Groups** adds explicit incident origins and ordered existing HA scripts
for start/recovery, with exact configuration confirmation. **Incidents** separates
current smoke, sounder requests, deliveries, scripts and device-test outcomes.
Detector details offer a built-in test only for an actual reviewed control.

Read the [incident guide and current evidence](incident-features.md) for supported
models, limits, receipt retention and the separate simulation on port 8131.
New automation defaults off. The existing guided setup/configuration checks above
remain; a read-only navigation button never performs an action. Background pushes
preserve forms; disconnect removes current status and disables submission while
retaining configuration drafts. Visual acceptance of these new screens is open.

Saved assignments that become unavailable or change identity are now retained and
marked in the editor. Choose a current control explicitly to replace one, or
remove it deliberately. Script ordering has Up/Down controls with contextual
keyboard labels. A confirmation locks the reviewed choices until Back/Cancel;
disconnect disables execution without losing the draft. Self-test confirmations
follow only their own request's activity/result. Incident details also show groups
and sources still awaiting explicit no-smoke values. See the
[finishing review](finish-review.md) for current evidence and open visual checks.
