# Optional linked sounding — 0.1.0-beta.2

This extension is included in the opt-in **0.1.0-beta.2** test release. The two
read-only overviews and their status rules remain unchanged. Existing and new
groups default to **linking off**, including groups upgraded from beta.1. Nothing was installed on a real system and no
physical detector was commanded or tested.

Before installing/updating, preserve a suitable HA backup. Leave linking off
during the installation review; physical activation requires a separate test. An older build cannot read
the new group payload; rollback requires the matching pre-update configuration
backup, not merely replacing Python files. No rollback/installer acceptance for
this new feature is claimed.

## Configure deliberately

In **AlarmMesh > Detectors**, inspect the provider, capability and proposed
control. **Detection only** can still be a smoke source. **Setting needed** or
**Not confirmed** cannot be used as a sounder target. Model names alone are not
enough: the source and control must share verified registry/device metadata,
with the required action, options and features present.

In **Groups**, choose at least two selected sources. Enable **Sound together**
(Dutch: **Samen laten afgaan**) and explicitly choose the proposed control for
each intended target. A source without a control can remain a member. Save first
opens a preview of the exact source-to-target pairs, stopping limitations and
unperformed physical acceptance. Review and acknowledge it before confirming.
Cancelling changes nothing. Every save rechecks admin rights, current identity,
capabilities and the edit revision; failed disk writes do not activate changes.
AlarmMesh never enables a device prerequisite itself.

## Reviewed profiles

All profiles below were tested in software only. “Linkable” means an eligible HA
control exists, not that a device sounded or that full automatic recovery is proven.

| Exact model | Provider | Activation through existing HA entity | Automatic stop |
| --- | --- | --- | --- |
| Heiman HS1SA-E-PLUS | Zigbee2MQTT/MQTT | `select.select_option`: `siren_for_automation_only`, `smoke_siren` | `stop`, only for an activation owned by the current runtime, with origins explicitly cleared and target smoke explicitly off |
| Aqara JY-GZ-01AQ / lumi.sensor_smoke.acn03 | Zigbee2MQTT/MQTT | `select.select_option`: `buzzer`, `alarm`; existing `linkage_alarm` must already be on | **None**: `mute` can hush local smoke. This is activation-only support |
| Develco/frient SMSZB-120 | Zigbee2MQTT/MQTT | `siren.turn_on`, explicit `burglar` tone and one 60-second duration request; required features/tones must exist | **None**: separation from local detection is unproven; no renewal |
| Develco/frient SMSZB-120 | ZHA | Existing basic IAS warning `siren.turn_on`, duration 60; older tone-capable entity must explicitly offer `Burglar` | **None**: activation-only support, no renewal |
| Aqara / Heiman above | ZHA | **Not confirmed**, no action profile | None |
| Other models, variants or generic MQTT metadata | Any | Detection only unless an exact reviewed profile matches | None |

Known Aqara firmware 21 (`21`, `0021`, `0.0.0_0021`) is blocked because the official
documentation retracts its alarming support. Unidentified firmware is not evidence
of physical compatibility. SMSZB-120 support does not imply support for every
frient product or the separate 94430 identifier. Legacy alarm switches are not
guessed into modern siren support. No direct MQTT, cluster or device adapter is used.

## Incident and lifecycle behavior

- A selected raw smoke `on` starts an incident, including the initial snapshot.
  An observed self-test does not start one. Manual sounder/linkage states are not
  smoke sources. An unreported test cannot be inferred from an ordinary smoke `on`.
- Each origin remains independently active until its source explicitly reports
  `off`. Unknown, unavailable or missing never means the smoke ended. This
  remembered incident is separate from the unchanged current-state overviews.
- Enabled groups target only their explicitly mapped members. A locally
  alarming target receives no extra activation. Overlapping groups deduplicate
  targets; repeated events do not repeat dispatched requests within an incident.
- A blocked, not-yet-dispatched target may receive its first request after its
  prerequisite/control recovers. Dispatched failures are not retried. At most
  eight action calls run concurrently, each with a ten-second software timeout.
  One failure does not block other targets. **Sent** confirms only the HA action
  completed, never audible sound or delivery to a physical detector.
- Disabling, deleting or remapping a group stops future dispatch and relinquishes
  its ownership; it sends no blanket stop/mute. Removing a selected group member
  blocks that group's execution until reviewed. Renames are not followed.
- Successful unload cancels/drains pending work and detaches observations. Failed
  platform unload leaves action execution paused and visibly reported; it does
  not falsely claim teardown. Resolve the fault and restart HA using HA's normal
  lifecycle. An already dispatched external request cannot be recalled.
- Reload/restart rebuilds from current sources. Still-active smoke is recognized
  again; unknown history and previous action ownership are not restored. An
  already active sounder is not adopted or stopped. Activation-only profiles may
  remain sounding according to their own device behavior after disable/reload.

An existing manual CO tone is also treated as already active. A later observed
manual tone change, stop or lost target feedback relinquishes Heiman ownership;
returning to the same tone does not reclaim it. Unknown control state blocks new
dispatch until usable information recovers. These cases have dedicated regression
tests, observed failing before their corrections and passing afterward.

There is no generic mute, self-test action, test-all button, notification,
escalation or heartbeat. Complete means usable current HA values, not recent
radio traffic, health or fire safety. No smoke reported is not a safety guarantee.

## Reproduce the simulation

Run the [complete validation route](development.md#complete-local-validation).
The same compatibility runner retains its original checks and adds mixed-provider
linking, independent target failure and lifecycle checks: **17 scenarios** per
exact HA version. The new fixture supplies registry metadata and local mock HA
action handlers; actual MQTT/ZHA integrations, transports and radios are absent.
This proves AlarmMesh's HA contract, not native-driver or hardware end-to-end behavior.

For an independent browser environment:

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Linking -Port 8129 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Linking -Port 8129 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Linking -Port 8129 -Action Stop
```

Open **http://127.0.0.1:8129/alarmmesh** after local test onboarding. Select
**SIMULATED A/B/C/D**; A is a mock Heiman MQTT target, B a mock Aqara MQTT target,
C a mock SMSZB-120 ZHA target and D an unsupported source. The **Overview**
dashboard contains only clearly named simulation helpers. B's prerequisite starts
off; change only that mock helper to demonstrate readiness. The request sensor
shows local mock calls. The C failure helper demonstrates independent failure.
No broker, coordinator, production configuration or cloud account is required.

Finish with smoke, unreachable, test and failure helpers off. Mock action states
and the request list are process-local; they are not physical feedback or retained
history. Ordinary HA helper state persistence is separate. The launcher checks
ownership/labels/mounts, localhost binding and exact version. Stop preserves its
ignored configuration under `config/linking-ui/`; older acceptance environments
are not touched. Its own bridge permits outbound traffic, not a LAN firewall.

## Primary sources reviewed 2026-11-13

- [Aqara model, prerequisite and firmware warning](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html).
- [Heiman automation-only control versus other properties](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html).
- [SMSZB-120 model](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) and
  [current official converter](https://github.com/Koenkk/zigbee-herdsman-converters/blob/afdaa028a0972d801da762196ddfb2df631ea0cc/src/devices/develco.ts).
- [ZHA Develco quirk](https://github.com/zigpy/zha-device-handlers/blob/b07fa76876e081d48744968f9fb806e7f1fee0ee/zhaquirks/develco/smoke_alarm.py),
  [Aqara quirk](https://github.com/zigpy/zha-device-handlers/blob/b07fa76876e081d48744968f9fb806e7f1fee0ee/zhaquirks/xiaomi/aqara/smoke.py) and
  [ZHA siren implementation](https://github.com/zigpy/zha/blob/2da1a5b5676158ac7b603ce6b9f42641cb90e7a0/zha/application/platforms/siren/__init__.py).
- HA [select actions](https://www.home-assistant.io/integrations/select/),
  [siren actions](https://www.home-assistant.io/integrations/siren/),
  [subscriptions/cleanup](https://contributors.home-assistant.io/core/integrations/events/)
  and [config-entry lifecycle](https://contributors.home-assistant.io/core/integrations/config-entries/).

Physical activation, stopping, local-alarm separation and real-device recovery
remain **NOT EXECUTED** for every profile. No physical test instruction is given here.

## Historical implementation review evidence — 2026-11-13

Base **9ff6df277c2f4ec411b374cfff8c1be7dfb6ff7c**, with the local changes in this
working tree. No hosted CI or released-version result is claimed for these changes.
Historical read-only acceptance records remain intact.

| Check | Actual environment and result | Local evidence under ignored `config/` |
| --- | --- | --- |
| Full backend suite, original assertions retained | Linux Python 3.14 / HA 2026.10.4: **316 PASS**, including unchanged 79 status cases | `validation/3e42c4e8c7ae4909aff73ed3ba4ffaef/baseline.log`, `pytest.xml` |
| Frontend DOM regressions | Node 24.22.1: **15 PASS** | Same validation run, `frontend.log` |
| Ruff lint/format, PowerShell parse/fault checks, Compose, official hassfest | **PASS** | Same run, `validation-result.json` and phase logs |
| Real HA bootstrap/flows and mock-action compatibility | Exact HA **2026.10.4**, **17 PASS** | `compatibility/2026.10.4/05dee1d5c68b4cc184fb2e60fe1e8511/technical-result.json` |
| Same compatibility contract | Exact HA **2026.11.1**, **17 PASS** | `compatibility/2026.11.1/b8970b4c80144efa9205494bc2d233d5/technical-result.json` |
| Repeatable integration-root ZIP, exact closed inventory | **PASS**, 26 files, identical SHA-256 across two builds; local test packages only | `release-packages/linking-final-ui-first/inventory.json`, `linking-final-ui-second/inventory.json` |
| Browser simulation | HA **2026.11.1**, native Chrome; NL/dark desktop and EN/light desktop, phone **390×844** and tablet **820×1180** observed | `linking-ui/fc03ec61249947f1909e8ad4729f180b/screenshots/` |
| Physical detectors, actual MQTT/ZHA drivers, audible feedback | **NOT EXECUTED**; mocks deliberately replace all transports/actions | Requires separate acceptance, no live access in this task |

The UI observations include prerequisites/unsupported targets, default-off state,
exact confirmation pairs, acknowledgement errors in both languages, keyboard
navigation/Escape cancellation, one failed target beside a sent request, two
independent origins, source outage retaining its incident, explicit recovery,
three mixed mock targets, and only the owned Heiman receiving stop. A real stop/start
of this container retained the group/mappings. Disconnect visibly cleared current
results; reconnect rebuilt them. Supplied logo/background and responsive controls
were visually inspected; this is browser emulation, not physical phone/tablet testing.

Review also corrected manual-CO adoption, subsequent manual-tone ownership and
unknown-control dispatch, with failing-before/passing-after HA regressions.
A mobile dialog inherited the previous detail's scroll/focus; an added DOM
regression and native-browser recheck verify that a newly opened form starts at
its heading. Original tests were retained. All relevant checks were rerun afterward.

The prepared **8129** environment remains running for review, in Dutch/dark mode,
with A/B/C/D selected and **SIMULATIE gemengd** explicitly enabled for the three
mock controls. All smoke, outage, test and failure helpers are off; B's mock
prerequisite is on. A final controlled restart cleared process-local mock outputs
and request records. The observed final panel reports no smoke, **4/4** usable
sources, one group and no old incident results. The other 8124–8128 environments
were left untouched. Stop only this environment with the Linking-mode command
above; its account/configuration is retained.

## Incident correction and beta.2

The later incident correction tracks suppression per target and relevant active
origins. A new incident in one group rearms independently of an unrelated active
group; overlapping origins retain suppression without retries. Seven permanent
regressions increased the backend suite to 323 cases. Frontend coverage remains
15 cases and compatibility remains 17 scenarios on each tested HA version.
The correction's base commit is c3f02ea05e504ce2caec6d84759e31100419c36f;
release metadata does not alter this behavior. The dated 316-case evidence above
is retained as historical evidence, not the final beta.2 result.

See [beta.2 notes](releases/0.1.0-beta.2.md) for installation, rollback and support
limits. Actual MQTT/ZHA drivers, physical activation and existing-installation
upgrade acceptance for this beta remain unperformed.
