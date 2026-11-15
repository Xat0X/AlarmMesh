# Activity, reminders and faster organization

Local work on beta.6, base `5ce5ee1410c9893d26374a6de0872a4eb3e2651a`.
The release version, smoke rules, source options and overview identities are unchanged.

## Activity

Open **Activity / Activiteit** from Overview or Incident details. Newest observations
appear first. Combine detector, group, category, event type and result filters.
Open an event for its source/context, time **observed by AlarmMesh**, request or
incident correlation, and links to the existing detector/group/incident views.
Closing details retains the filters and the underlying reading position.

The journal starts with a quiet baseline. It does not turn initial source values,
old receipts or retained device-test results into new historical events. Observed
source transitions, request states, device-test feedback and maintenance conditions
remain separate. A restored usable source value is not necessarily a smoke-free
release: only explicit off can release a previously involved source. Acceptance by
HA does not establish sound, phone delivery or external script effects. An explicit
device-test result does not establish physical smoke detection.

The separate version-1/schema-1 HA Store `alarmmesh.activity.<entry_id>` keeps at
most **30 days / 1,000 events**. The pending queue holds at most 128 observations;
one background worker writes it. Retention prunes only this journal, including on
load, without changing action receipts. Overflow, invalid storage or failed writes
mark the history incomplete. Invalid storage is preserved; recording failures
cannot start/clear incidents or stop existing smoke processing. There are no raw
provider payloads, message bodies, script contents or tokens. Detector/target/group
references are local administrative data. Diagnosis exports only explicit aggregate
counts/issue codes and aliases, never the raw journal.

Where the execution route already has an ID, activity uses the existing episode,
cycle or self-test request ID. Sounder records have no persisted incident ID; the
journal gives each newly observed runtime record its own observation correlation,
without changing action ownership or deduplication. The journal is not an audit of
unobserved radio/device behavior and cannot reconstruct time spent offline.

## Check reminders

Open **Maintenance / Onderhoud > Set up reminder**, or open a detector's details.
Reminders start **off**, including after updating an existing installation. Choose
the exact detector, an existing Companion recipient and a calendar date. Delivery
is scheduled at **09:00 in the HA time zone**. Date scheduling uses the local
calendar across daylight-saving changes. Optional repeat preferences are **30, 90,
180 or 365 days after explicit handling**; zero means no repeat. These intervals
are user preferences, not manufacturer advice.

Review the exact settings and acknowledge before saving. Cancelling leaves stored
settings unchanged. Ordinary reconnect preserves a populated draft and blocks
offline submission; concurrent edits are rejected through the stored revision.

- **Remind later:** choose a future date and confirm it. This creates one new due
  reminder. It does not operate or test the detector.
- **Reminder handled:** records only your acknowledgement. With an enabled repeat
  preference it schedules the next date; otherwise it remains handled. Existing
  self-test records are untouched.
- **Remove:** explicitly deletes only this reminder.

Each due cycle/recipient receives at most one attempt. Saving the same date and
recipient, or changing just the repeat preference, does not retry it. Intent is
persisted before delivery; failure, cancellation or uncertainty is terminal for that
cycle. One broken receiver does not block the next reminder. HA acceptance is not
confirmed phone delivery. A missing receiver stays visible until explicitly fixed.
Missing/unselected/replaced detector identity blocks delivery; no reassignment is
automatic. Confirm a current identity when intentionally replacing a reminder.

An overdue reminder at startup/reload is shown as suppressed rather than sent in a
burst. Choose a new future date explicitly. Future reminders keep their date and
receipt state. Smoke and latched incidents defer reminders; their processing uses
a separate bounded worker and never waits for the reminder timer. There is one
nearest-date timer and owned startup listener, both cancelled on unload. This
version introduces **no automatic self-test, sound, stop or test-success action**.

Settings and cycle receipts use a separate version-1/schema-1 HA Store
`alarmmesh.reminders.<entry_id>`, at most 256 detector records. Corrupt/unwritable
storage pauses reminders without overwriting damaged data or blocking smoke.
Explicit integration removal deletes both new entry-owned stores.

## Find detectors and copy groups

Detectors combine name, room, group, provider, smoke/unusable/unknown status and
known maintenance attention filters. No selection, no filter results and unknown
metadata are distinct. The global smoke/completeness badge stays visible even
when a filter hides an active source. Clear filters to show the whole selection.

The group editor searches detector names/rooms without clearing hidden checked
members; member and incident-source counts stay visible. **Copy group** in group
details previews its name, selected members and incident sources. Old unselected
references are explicitly omitted. After confirmation the new group gets a new
identity, **linking off, no target bindings and no script actions**. The original
group and global phone settings are unchanged. The backend constructs this safe
copy; browser payloads cannot copy executable permissions.

## Review environment and evidence

Use only **http://127.0.0.1:8131/alarmmesh**, with the existing local test account.
Fully refresh once for the new module version. Never use production devices or
phone services for this review. The fixture provides mock targets/phones and
event-only scripts. Keep all simulation helpers off, self-test result idle and
automatic linking/messages/scripts/reminders off after testing.

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```

The guarded commands check ownership/mounts and localhost binding, preserve the
account/configuration and leave other environments alone. The existing bridge
permits outbound traffic; it is not a LAN firewall. No real driver/cloud is configured.
All generated evidence, packages and logs remain ignored under
`config/activity-tools/4b0d721f1d0240599fe5a6cd1cec8ee4/` and the standard validation
directories. Results below distinguish technical simulation from visual acceptance.

All eight **NL/EN × light/dark × 390×844/1024×768** visual combinations are
**NOT EXECUTED** for these new screens: the supported browser host is unavailable;
the native pipe reports `os error 2`. No screenshot or visual PASS is claimed.
When access returns, inspect activity/details, reminder forms, detector filters,
copy/confirmation, empty/error states in each combination. In the simulator run an
incident/request/failure/recovery, a mock reminder with later/handled, combined
filters/detail return, an organizational copy, and reconnect with unsaved input.
Restore the idle/off state. DOM tests do not replace these observations.

### Current results — 2026-11-15

All results below are **local simulation on the base commit plus these uncommitted
changes**, not hosted CI or a published release. The machine-readable summary is
`config/activity-tools/4b0d721f1d0240599fe5a6cd1cec8ee4/results.json`; the complete
changed-file list/protected-file/link/privacy checks are in `scope-result.json`
beside it.

| Check | Result | Evidence under `config/` |
| --- | --- | --- |
| Full Linux baseline, Ruff lint and format | **PASS**, Python 3.14.10 / HA 2026.10.4; **508 tests**, including 22 new cases and the unchanged 79 status tests | `validation/a94d9c9eff6c4299bfb5223f63467c45/baseline.log`, `pytest.xml` |
| Frontend | **62 DOM tests PASS**, including five new cases; no visual claim | same validation directory, `frontend.log` |
| PowerShell parse/failure paths, Compose, official hassfest | **PASS**, zero invalid integrations | same validation directory, `validation-result.json`, `hassfest.log` |
| Actual HA **2026.10.4** and **2026.11.1** | **29 runtime + 16 isolated driver checks PASS per version**, including activity, safe copy and mock reminders | same validation directory, `compatibility-2026.10.4.json`, `compatibility-2026.11.1.json` |
| Two deterministic packages | **PASS**, 37 files; equal to each other and to the current/full-validated integration source | `release-packages/activity-4b0d721f-one/inventory.json` and `activity-4b0d721f-two/inventory.json` |
| Scope, original assertions, privacy, links, whitespace | **PASS**, 53 protected files byte-identical; original frontend file retained as a prefix | task evidence directory, `scope-result.json` |
| Review simulator | HA **2026.11.1**, guarded restart, localhost/RO mounts, mock/event-only configuration, outputs off; current module HTTP **200** | task evidence directory, `simulator-result.json`; configuration/serving proof, not UI inspection |
| Eight visual combinations / screenshots | **NOT EXECUTED**, unavailable supported browser host; no screenshots generated | task evidence directory, `results.json` |
| Physical detector/phone/external script behavior | **NOT EXECUTED** | No physical evidence claimed |

Both package SHA-256 values are
`542afee11f09748e5a967a6be194d16253f68d7944753ef796961dd61e3d94d2`.
These are local test packages, not approved/public release artifacts.

The original failing evidence is retained locally: saving an unchanged due
reminder retried it; a journal write generated an extra transport push; retention
timers survived interrupted unload; a newly reported battery cause incorrectly
retained a cleared old cause. Focused regressions now pass, followed by the full
route. Failed earlier results are not overwritten. The first image run correctly
refused a copy fixture containing deliberately unselected old members; the checker
now explicitly omits them, as the UI does, and verifies the original remains equal.
The validation assertion was preserved. The final checker also passed Ruff after
that fixture correction; all 37 product files match the full baseline export.

The simulator remains running, with the existing account/configuration preserved,
86 helpers configured off, result idle, no groups, and linking, scripts, smoke
notifications, maintenance messages and reminders off. This is a configuration
audit after restart; current authenticated screens/states were not independently
inspected. Other test environments and the real installation were untouched.

Official references checked **2026-11-15**:
[HA event helpers](https://contributors.home-assistant.io/core/integrations/events/),
[HA async/task guidance](https://contributors.home-assistant.io/core/internals/asyncio/),
[Companion notification route](https://companion.home-assistant.io/docs/notifications/notifications-basic/).
The fixed HA 2026.10.4/2026.11.1 environments verify the actual storage/helper APIs.


### Independent browser follow-up — 2026-11-15

The earlier NOT EXECUTED visual result above is historical. The reminder, copy
and source-event detail dialogs have now been inspected from actual browser
screenshots in all eight NL/EN × light/dark × phone/tablet combinations (24 images).
Browser emulation is not physical device validation. Independent flows covered
simulated smoke/recovery, journal filter/detail return, combined detector filters,
disabled reminder save/later/handled, organizational copy, and cleanup.

Corrected detector-search and reminder save/remove/recipient wording, complete
reminder confirmation (enabled and repeat settings, using saved settings for
non-save operations), copy-name field styling, and explicit self-test wording in
activity result filters. Four frontend regressions preserve the prior assertions;
the initial two checks were observed failing before correction.

Final standard validation `28236ea08ad84f9992fdd2c170cbf82e`: **508 backend + 66 frontend tests PASS**,
all tooling checks PASS, and **29 runtime + 16 provider checks per HA version**
(2026.10.4 and 2026.11.1) PASS. All 37 current product files match the validated
source export. Two corrected packages have identical SHA-256:
`091167a1d5589d0fd2235d26277a22d00610c022d659556aa86e1aea20f33094`.
Earlier package hashes above remain tied to the earlier snapshot.

Observed reconnect boundary: the unsaved date stayed visible and submission was
blocked while offline. A complete HA process restart then caused HA to reload the
page and discard that draft. Durable preservation across a page reload is not
implemented or claimed; the ordinary transport-reconnect DOM test is separate.

The simulator was restored: no groups/reminders, A+B smoke-free, helpers off,
result idle, outputs off, Dutch/Auto preferences and normal viewport. Only local
simulation was used. Evidence: `config/activity-review/28236ea08ad84f9992fdd2c170cbf82e/review.json`;
the user-workspace review and 24 inspected images are referenced there. No real
device/phone acceptance, hosted CI, commit, push or publication was performed.
