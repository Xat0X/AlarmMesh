# Matter support — local review, 2026-11-16

This unpublished working tree extends beta.7 (`8522584942b136f5c919525c5d0040e7e4bf2c0e`).
Use the existing HA Matter integration first, then select its smoke entity in
AlarmMesh. AlarmMesh is not a Matter controller, commissioning tool or Thread
Border Router. It neither reads network credentials nor sends cluster commands.
All execution evidence below uses mocks; no physical device was operated.

## Setup and interpretation

1. Add the detector through [HA Matter](https://www.home-assistant.io/integrations/matter/).
   Matter-over-Thread needs a suitable [Thread Border Router](https://www.home-assistant.io/integrations/thread/).
2. Check that HA exposes a smoke binary sensor. A CO entity is a separate function.
3. Select that existing smoke entity in AlarmMesh's integration options.
4. Inspect **Detectors > detector details** for its actual functions and limitations.
5. Optionally configure groups and explicitly supported targets, recipients and scripts.
   New automatic configuration stays off; existing explicit choices are retained.
6. Use the group's output-free action example before enabling anything.

The panel includes this help route from setup and settings. **Matter** identifies
the provider. **Via Thread / via Wi-Fi** requires matching registered diagnostic
entity metadata; no diagnostic network values are read. A bridged child is shown
separately. Otherwise it says **transport unknown**. Neither a product logo nor
the Matter provider establishes transport or network health.

Smoke semantics remain unchanged: `on` takes priority, only explicit `off` from
all selected sources means no smoke reported, and insufficient information is
`unavailable`. Complete means usable current HA values, not recent radio contact,
physical health or a safety guarantee. CO-only values never become smoke, even
in invalid previously saved selections. No CO incident engine is added.

## Function contracts

These contracts were checked against the actual HA **2026.10.4 and 2026.11.1**
entity descriptions. Optional entities must exist at the exact selected endpoint;
model recognition never grants execution authority.

| Function | Actual HA route and current behavior |
| --- | --- |
| Smoke | Local SmokeState binary sensor, read-only; separate from test and CO |
| Battery | PowerSource percentage, SmokeCoAlarm battery warning, or PowerSource charge warning; absent/unknown stays unknown |
| Hardware fault | HardwareFaultAlert binary sensor, read-only |
| End of service | EndOfService binary sensor, read-only; separate maintenance field and activity observation |
| Test activity | TestInProgress binary sensor, read-only; not evidence of successful testing |
| Explicit test request | HA's `button.press` on its SmokeCoAlarm SelfTestRequest button, only when HA actually exposes it |
| Correlated terminal test result | Not exposed by this reviewed HA route; completion/timeout remains **outcome unknown** |
| Remote sounder activation | No reviewed HA Matter route; no Matter sounder target offered |
| Stop own sounder activation | No reviewed HA Matter route; no stop or mute command offered |
| Native interconnect | Separate InterconnectSmokeAlarm report, read-only; visible alarm but not an independent execution origin |
| Mute | DeviceMuted read-only information, never an action |

Identify, self-test, mute and sounder activation are distinct. Self-test is not
used to make a group sound. Explicit confirmation names one current device;
availability, identities, current smoke and conflicts are rechecked before the
existing dispatcher calls its HA button. A real smoke report during a test is
still an incident. A successful HA call or an activity flag returning off is not
a successful physical self-test. No unfinished request is restored as success.

## Models and evidence

All rows have **upstream descriptions**, **offline HA-class checks** and
**HA registry/behavior fixture checks**. None has physical acceptance. Fixtures
exercise generic endpoint contracts; they do not establish actual firmware
exposes or validate the manufacturer identity of a connected device.

| Model / variant | Identity and region evidence | Conditional HA functions | Explicit limitations |
| --- | --- | --- | --- |
| Heiman HS1SA-M | Manufacturer's HS1SA Matter variant, EU/China; numerical vendor/product pair not established here | All read-only rows above if exposed; exact HA self-test button if exposed | Other HS1SA variants are not inherited; no remote sounder/stop/result contract |
| Heiman S1-M | Manufacturer's S1 Matter variant, US; numerical vendor/product pair not established here | Same endpoint-based conditional functions | S1-M on MQTT is a different provider contract; no inferred Matter sounder route |
| Sensereo MS-1 / MS1 | CSA vendor `0x1596`, product `1`; official HA material also names LZ-1956Z | Same conditional functions | Original MS-1 and newer MS-1 Interlink are distinct; no promised cross-generation interlink |
| Sensereo MSC-1 | CSA vendor `0x1596`, product `2`; official HA material also names AK-960SCM | Smoke portion and optional separate CO information; same conditional test route | CO never triggers smoke behavior; not an MS-1 Interlink member |
| Sensereo MS-1 Interlink | Separately documented newer variant; no invented numerical product ID | Same conditional functions plus separately exposed interconnect information | If HA lacks separate origin information, alarm remains visible but outgoing propagation is blocked |

See the [review data](../dev/catalog/review.json) for per-row links, checked date,
identity gaps, region and exact tested HA versions. The existing Zigbee catalog
denominators (52 definitions / 67 rows) remain unchanged; these are five additional
Matter review rows, not five tested physical devices.

## Identity, groups and lifecycle

Function binding requires the Matter provider, owning Matter config entry, device,
opaque HA identity prefix and **the same endpoint**. Friendly names and entity-ID
suffixes grant nothing. Bridges and multiple endpoints are explicitly tested.
HA's opaque prefix is compared/hashed, never decoded or exported as network data.
Battery information from a different endpoint is intentionally not guessed.

A small versioned HA store pins selected source identities as hashes. It does not
replace source options or change their schema. Replaced sources still show their
current report, but execution is blocked until an administrator reviews the exact
new identity. Missing-at-start sources are not silently adopted when they appear.
Corrupt identity storage blocks Matter execution. Other providers and read-only
smoke remain independent. Source removal prunes pins; entry removal clears the store.

A verified local Matter source can start the existing mixed-provider group engine
and activate explicitly selected, supported Zigbee2MQTT/ZHA targets. Forwarded
interconnect reports stay visible but do not create independent output origins.
Unproven origin separation blocks new output rather than hiding an alarm. No
secondary interconnect entity is automatically selected. Existing deduplication,
independent incident lifetimes, failure isolation and limited stop authority remain.

## Local unsent drafts

Group editing, phone/maintenance settings and check reminders can retain necessary
input in browser local storage for up to two hours. Buckets are separated by HA
origin, user, integration entry and form target; at most five drafts are retained.
Expired drafts are removed on the next access (a closed browser runs no cleanup).
Private-mode/storage restrictions may prevent retention. This is a convenience,
not an HA backup or a place for secrets.

Continue or discard explicitly after reload. Restored input retains its original
server revision and current identity/choice checks. Stale revisions are rejected
normally; no automatic substitution with a fresh revision occurs. Confirmations,
request IDs, tokens, messages and HA snapshots are never persisted. Restoring
cannot execute anything; enabled configurations still need a fresh confirmation.
Successful saving, explicit discard and account switching clear the relevant draft.

## Primary sources checked 2026-11-16

- [HA Matter](https://www.home-assistant.io/integrations/matter/),
  [Thread](https://www.home-assistant.io/integrations/thread/) and
  [Heiman](https://www.home-assistant.io/integrations/heiman/).
- HA source: [2026.10.4](https://github.com/home-assistant/core/tree/2026.10.4/homeassistant/components/matter)
  and [2026.11.1](https://github.com/home-assistant/core/tree/2026.11.1/homeassistant/components/matter),
  particularly `binary_sensor.py`, `button.py`, `sensor.py`, `entity.py` and unique-ID generation.
- [Heiman HS1SA series](https://www.heimantech.com/product/smart-mini-smoke-sensor-heiman-hs1sa-series)
  and [S1 series](https://www.heimantech.com/product/smart-smoke-fire-alarm-s1-series).
- [HA Sensereo announcement](https://www.home-assistant.io/blog/2026/05/28/sensereo-joins-works-with-home-assistant/),
  [MS-1 product page, currently Interlink](https://sensereo.com/product/ms-1/),
  [MSC-1](https://sensereo.com/msc-1/), CSA [MS1](https://csa-iot.org/csa_product/ms1/)
  and [MSC-1](https://csa-iot.org/csa_product/msc-1/).
- [Matter Smoke/CO cluster definition](https://github.com/project-chip/connectedhomeip/blob/v1.4.2.0/src/app/zap-templates/zcl/data-model/chip/smoke-co-alarm-cluster.xml).

Commissioning, firmware behavior, real Thread connectivity, audibility and physical
smoke/test results remain untested. The [current Matter review results](matter-review.md)
separate automated evidence from the unavailable new visual matrix and physical work.
