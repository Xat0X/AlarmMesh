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

## Four screens

- **Overview** shows the shared current smoke result, usable/selected source
  counts, assigned room count, group count, attention items and room cards.
  Active smoke is prominent and names the reporting detector and assigned room.
- **Detectors** lists only selected sources. Open a row for the real HA state,
  source entity, assigned area, known device/model/manufacturer and groups. The
  Home Assistant button opens HA's entity information. No model, battery level or
  radio-contact time is guessed. Battery and floor values are currently omitted.
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
