# AlarmMesh panel

The local interface organizes existing Home Assistant smoke reports. The local
review build also offers explicitly confirmed, default-off [linked sounding](linked-sounding.md)
through supported existing HA controls. No smoke reported is not a safety guarantee.

The current local changes add **My alarm settings** to Overview and Settings,
with per-detector routes and links to the existing configuration screens.
Phone test observations are explicitly user-reported; incident chronology stays
separate from current smoke. See the [five-minute tour and local evidence](alarm-settings-review.md).

## Open and choose sources

After configuring AlarmMesh, administrators see **AlarmMesh** in the HA sidebar
at `/alarmmesh`. The panel uses your existing HA session and profile language
(Dutch/English), light/dark HA theme and local packaged assets. Other users keep
their normal access to the two overview entities; the management panel is admin-only.

Choose **Detectors > Choose detectors** to open AlarmMesh's existing integration
page, then **Configure**. This is the original entity selector and backend
validation. Saving changed options reloads the integration. Cancelling or invalid
input leaves the saved selection unchanged. No second source selection is stored.

## Panel screens

The current local additions are [activity, optional check reminders, detector
filters and safe group copies](activity-reminders.md), within existing navigation.

Local development adds [separate maintenance messages, read-only group action
examples and anonymized diagnosis](maintenance-tools.md) within the existing
navigation. All new automatic delivery starts off; no existing setting is enabled.

- **Overview** starts with one **Choose detectors** action when no detector is selected.
  Once configured, **Set up and check** is collapsed. The source, room and group
  counts are direct navigation buttons; missing sources are named in the status card.
  It shows the shared current smoke result, usable/selected source
  counts, assigned room count, group count, attention items and room cards.
  Active smoke is prominent and names the reporting detector and assigned room.
- **Detectors** lists only selected sources. Search is immediately available;
  additional filters are under **More filters**. Each row has **What happens during smoke?**.
  Each detector row also shows its available battery percentage, including zero,
  or an explicit unknown/low-battery indication. Values are not inferred from smoke status.
  Technical details are collapsed in the detector dialog; duplicate names in the
  same area include their source ID so they remain distinguishable. Open a row for the real HA state,
  source entity, assigned area, known device/model/manufacturer and groups. The
  Home Assistant button opens HA's entity information. No model, battery level or
  radio-contact time is guessed. Available cached diagnostics are shown when HA exposes them; missing data stays unavailable.
- **Rooms** uses HA assignments, with entity assignment before device assignment.
  Only areas containing selected sources appear; others are under **No area**.
  Change assignments in HA, not in a second AlarmMesh room registry.
- **Groups** lets administrators create, rename, edit memberships and delete an
  organizational group. A detector can belong to several groups. Deleting asks
  for confirmation and does not delete any source. Empty groups are allowed.
  A new group starts with its name and members. **Optional smoke actions**
  summarizes enabled choices. Its separate sections let you choose which detectors
  start actions, which sound together and which existing scripts run.
  **Sound together** is optional and off by default. Choose exact controls, review
  the source-to-target preview and acknowledge its limits before saving. The
  [linking guide](linked-sounding.md) lists profiles and stopping restrictions.

**Settings** presents five tasks: choose detectors, set up groups, choose phones,
choose extra actions and review maintenance. Each shows its current setting.
**Set up phone alerts** opens the phone form with separate iPhone/Android controls,
permission help, save and test steps. Saving sends nothing. **Prepare test
notification** previews the request; only separate confirmation sends it.
Saving a recipient while automatic alerts are off does not enable delivery.
Installation, catalog and diagnostic tools remain available under the help section.

**Incidents** starts with the current smoke status, then previously observed
incidents and requests. **Maintenance** and **Activity** summarize what is known;
their detailed evidence limits remain under an expandable explanation. Battery
information, a request receipt or a handled reminder never proves physical safety.
For temporary loss of a detector, use **Check connection**. **Replace detector**
is a separate, confirmed process; it never inherits permission to sound automatically.
See the [five-minute walkthrough and review](plain-language-review.md).

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
The guide has five task entries: detectors, HA rooms, groups and actions, phone
alerts, and problem review. Groups have one destination, with separate server-derived
assessments for linked sounding and scripts inside that entry. No backend state
is merged or enabled by this presentation. Configured means saved/current metadata, not physically tested.
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
At or below **20%** is a maintenance threshold. The display changes no smoke
status or incident rule. In this local build, separately enabled
[maintenance messages](maintenance-tools.md) can use that same threshold;
they default off. Off means no problem
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

The [usability review](usability-review.md) records the published baseline's visual
checks. The new maintenance/example/diagnosis screens have separate
[current evidence and outstanding visual checks](maintenance-tools.md#local-review-and-evidence).


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

## Matter and local drafts — current unpublished review

Matter smoke entities can join the existing source selection and mixed-provider
groups. Detector details show endpoint functions, honest transport information,
separate CO/interconnect information and optional explicit HA self-test requests.
There is no reviewed Matter sounder, stop or mute action. A completed request is
not a passed physical test. Follow [Matter setup, model matrix and limitations](matter-support.md)
and [current automated/visual evidence](matter-review.md).

The main configuration forms can keep an unsent local draft through a full browser
reload. Continue or discard it explicitly; it expires after two hours and never
restores confirmation. If identities changed, discard and reopen; if another
browser saved first, the original revision is still rejected. Private browser
storage may not retain drafts. See the guide for exact fields and privacy limits.

## Alarm route and guided source recovery (local review)

In **Detectors > detector details > View alarm route**, inspect all associated
groups at once. Shared sounder targets show one eligible request and each group's
reason. Phone recipients follow their global incident rules; scripts retain each
group's start/recovery order. Opening, refreshing and closing perform reads only.
The same route is reachable from the group's existing action example.

**Maintenance > Recover source** distinguishes temporary unavailability, a missing
entity and changed identity. Temporary outages need provider investigation, not
replacement. Recovery uses explicit separate saved steps because HA options and
groups have no shared transaction:

1. Disable affected group linking/scripts and global incident notifications.
2. In the existing HA source options add the replacement, retaining the old source.
3. Reopen recovery, choose the already selected replacement and explicitly choose
   memberships. Review old/new source and groups, then confirm.
4. Review origins, controls, scripts and notifications separately. The replacement
   inherits no origin permission or sounder binding. Remove the old source through
   HA options only when appropriate. History/reminders are never reassigned.

The group step saves all chosen memberships atomically. Failed writes leave groups
unchanged; stale or repeated submissions conflict. Active affected smoke, any
running self-test, a changed identity or missing/non-clear candidate blocks it.
Reload/reopen derives progress from stored options and groups. If the acknowledgement
is lost, refresh to see saved state; never assume a failed connection rolled back a save.
Closing the guide or removing a source is not proof of smoke clearance. Existing
independent groups remain unchanged. Replacing an identity under the same entity ID
continues to use its existing identity review, available in detector details.

The self-test dialog's **Refresh data** fetches a fresh authenticated snapshot,
rechecks whether the test is available and clears the previous acknowledgement.
It never sends a test request. Only the dialog's own request ID can display a result.
These are software controls, not physical-device validation.

## Local usability review

See the [morning review](morning-review.md) for the five-minute simulator tour,
before/after evidence, actual browser coverage and automated validation. No physical
smoke detection, phone delivery or sounder output was tested in this UI review.

## Clearer sound roles and phone routes (local development)

The group choice **Do not sound along / Niet laten meeklinken** leaves smoke
reporting intact and does not disable the detector's own smoke alarm. The other
choice explicitly allows supported remote sound when another detector reports
smoke. Existing confirmation, capability checks and default-off behavior remain.
Provider-specific stop limitations are available under Technical information.

Both the single-detector route and My alarm settings use phone cards. Selected
phones appear first, including unavailable selections and their reason. Unselected
phones are collapsed under a counted list. Critical profiles and sound settings
remain visible; readiness is not a claim of receipt or audible delivery.
See the [local clarity review](clarity-review.md) for evidence and limits.

## Family drill, incident links and dashboard card

Open **Overview → Silent practice** or **Detectors → a detector → What happens if smoke is reported?**. The drill reads the configured routes. Press **Next step** to reveal the sounders, phones and actions together. Open a destination for its groups and limitations. On a live smoke report the drill closes and the incident screen takes priority.

Smoke alerts carry the incident's relative HA URL in both mobile notification fields. Opening it requires the usual panel permissions. Incident observations follow the activity history limit of 30 days and 1,000 entries. A missing reference opens an explanation. [Companion notification links](https://companion.home-assistant.io/docs/notifications/notifications-basic/#opening-a-url)

In a UI-managed dashboard, register `/alarmmesh-assets/dashboard.js` once as a **JavaScript module** under **Settings → Dashboards → Resources** (advanced mode). Then **Edit dashboard → Add card → AlarmMesh**. For a manual card, use `type: custom:alarmmesh-family-card`. In YAML-managed dashboards declare the same URL under `lovelace.resources` with `type: module`. The card uses the panel's administrator permissions. [Home Assistant custom dashboard cards](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/)

For maintenance, open **Detectors → a detector → Record maintenance**. Choose a date and the type of entry. After a lost reply, use **Check saved entry**. The journal retains the latest 500 entries per integration and binds each to the registered detector identity. The [five-minute family tour and local evidence](family-review.md) cover all four tasks.
