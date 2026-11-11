# Read-only pilot registration and passive observation

Recorded **2026-11-11**. This register describes a limited pilot, not physical
smoke-detection validation or a safety certification. No access to the real
installation, its credentials, MQTT or Zigbee devices was made for this package.
Installation-specific identifiers are intentionally omitted; use local aliases
such as `<smoke_source_entity_id>` and `<overview_entity_id>` in private notes.

## Evidence categories

| Category | Evidence and limit |
| --- | --- |
| Reported by the user | AlarmMesh **0.0.1** installed through the built-in Marketplace on **Home Assistant OS, Core 2026.11.1**. Selected pilot: **Heiman HS1SA-E-PLUS**, Zigbee2MQTT, reported firmware **2.2.0**. Source selection and current display work. |
| Reported by the user | Current display: **“Niet gedetecteerd”** and **“Alle bronnen melden een status”**. Selection and correct current display survive an integration reload. After instructions to remove an extra source from selection, the user confirmed the checks were correct. The saved live selection was not independently inspected. |
| Visible in screenshots | No screenshots were supplied or inspected in this documentation task. No additional screenshot-based claim or screenshot file is included. |
| Independently checked with simulated sources | [Reproducible technical checks](compatibility.md) pass on exact **2026.10.4** and **2026.11.1**, using repository base **1c9aae2** plus the documented local tooling changes. This is not inspection of the pilot device or production configuration. |
| Historical manual UI simulation | [Twelve UI scenarios](mvp-acceptance.md) were completed in the separate 2026.10.4 environment, including its actual container restart. This does not prove a production restart. |
| Not performed | Real smoke transition and recovery; physical connection loss and recovery; actual restart of the production installation; separately observed behavior during this model's physical self-test. |

The user-reported installed version does not identify an independently verified
production Git commit. No physical test result is inferred from a self-test,
current `off` state, reload or simulated result.

## Model semantics

Checked on **2026-11-11** against the
[official Zigbee2MQTT HS1SA-E-PLUS page](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html).
`smoke` represents the detector's smoke-alarm decision. `test` reports a self-test
in progress; it is not interchangeable with `smoke`. A self-test alone does not
establish smoke-sensing performance. `interconnectable` and `link_available`
are linkage-event reports and can occur during tests or alarms. They are not
extra smoke sources. `siren_for_automation_only` is a sounder control, not evidence
of local detection. AlarmMesh adds no support for these extra properties, mute,
linkage or self-test controls. Reported firmware does not verify every behavior
on this particular device.

## Passive observation protocol

Only observe naturally occurring changes or normal operation already undertaken
by the owner. No smoke generation, battery removal, interruption of Zigbee2MQTT
or MQTT, source-state overrides, siren commands or self-test commands form part
of this protocol. Future physical tests require separate planning according to
the manufacturer's instructions; this document gives no physical test order.

1. Compare the selected HA smoke source and the two AlarmMesh overviews when a
   natural change is noticed. Record the time with timezone and the source state
   as observed (`on`, `off`, `unknown`, `unavailable` or absent).
2. Record smoke outcome and source availability, including other selected
   sources if they explain the combined result. Active smoke must take priority;
   incomplete information without smoke must never silently become `off`.
3. When the source naturally recovers, record its actual state, both outcomes and
   recovery time. Mark missed observations as unobserved, not PASS.
4. If the results disagree, retain a sanitized observation and expected/actual
   behavior as a review finding. Do not change the live installation for this
   documentation task. Keep private logs outside Git; share aliases only.

| Time + timezone | Source alias/state | Smoke overview | Source availability | Recovery time/state | Evidence / expected vs actual |
| --- | --- | --- | --- | --- | --- |
| `<observed time>` | `<alias>: <state>` | `<state>` | `<state>` | `<observed or not observed>` | `<user report or direct observation>` |

`complete` means every selected source currently provides a usable HA `on` or
`off` value. It does **not** mean each detector recently sent a new message or
physically detects smoke correctly. An unchanged source is not automatically
defective; AlarmMesh has no heartbeat or ageing threshold.

HA entity availability is what AlarmMesh reads. Zigbee2MQTT's device availability
is a separate, configurable upstream mechanism; whether it is enabled and how it
reaches HA has not been inspected for this pilot. A usable cached HA value alone
does not prove a recent radio report. Do not add a timeout or alter that setup to
complete this observation record.
([Official Zigbee2MQTT availability documentation](https://www.zigbee2mqtt.io/guide/configuration/device-availability.html))

The four physical/production items in the table remain **NOT PERFORMED**. The
pilot is open for passive observations; simulated compatibility and user reports
do not close them. No smoke reported is not a guarantee of safety.
