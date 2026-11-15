# Maintenance messages, action examples and diagnosis

Local development on beta.5 (`478c237156cedec6fe7695d20f30aae3b6cc1afd`).
The manifest/release version is unchanged. These additions are not published.
A later independent visual review and two presentation corrections are recorded
[below](#independent-visual-follow-up); the initial unperformed matrix is historical.

## Maintenance phone messages

Open **Settings > Set up maintenance messages** or **Maintenance** from Overview.
This is separate from smoke incident notifications. It starts **off**, with no
recipients selected and recovery messages off. Choose existing Companion App
services, categories and the unavailable-source waiting period: **5, 15, 30 or
60 minutes**, default **15**. Review and confirm the exact recipients/settings.
Cancel changes nothing. Disconnected forms retain their draft and cannot send.
Unavailable saved recipients remain visible until explicitly removed/replaced.

- **Battery:** a valid percentage at or below 20%, or a proven same-device binary
  low-battery flag. Invalid values/units stay unknown. Recovery requires explicit
  clear values for the indicators that caused the problem.
- **Problem:** an explicit same-device/provider binary problem report. Missing
  or unknown values never count as recovery.
- **Unavailable:** selected source information stays unusable for the chosen
  continuously observed period. Restoring current usable information can recover
  that problem. This is HA entity availability, not proof of MQTT/Zigbee traffic.
- **Recovery:** optional, only for a recipient whose earlier problem request HA
  accepted, and only with matching identity and explicit usable clear evidence.
  Missing/replaced sources never provide an old problem's recovery.

Each device/problem/recipient gets one attempt. Failed or interrupted requests
are not automatically retried. A confirmed recovery and a new problem permit a
new attempt. One failed recipient does not block another. The maintenance page
shows request receipts and why delivery is off, waiting, unknown or deferred.
HA acceptance is not proof that a phone received or displayed the message.

**Quiet restart:** maintenance waits for HA startup to complete. Newly observed
battery/problem conditions and startup recovery are recorded quietly rather than
announced in a burst. A fresh observed recovery/new problem can notify later.
Previously attempted receipts prevent replay. Unavailable-source timing starts
again after reload/startup or a delay change; downtime is not assumed to prove
continuous observation. The page explains startup suppression. Enabling the
feature explicitly in an already-running HA instance can report current problems.

Maintenance uses one separate bounded delivery lane (ten-second calls) and a
single nearest-deadline timer. Smoke and incident processing never wait for this
timer; maintenance dispatch is deferred while smoke/latched origins are active.
Turning maintenance off cancels its pending work/timer. Unload drains owned work
and removes startup listeners. No device queries, heartbeat, maintenance actions,
new transport or automatic self-tests are introduced.

Storage is a separate version-1 HA Store, with explicit schema 1, at most 256
current device records, three problem kinds and 20 recipient receipts per kind.
There is no message body, token or raw provider payload. Old unselected records
are pruned without a recovery claim. Invalid maintenance storage pauses only this
optional feature and is not silently overwritten; restore valid HA storage before
reloading. Existing smoke/group/notification settings and their schemas remain.

## What happens during an alarm?

Open a group and choose **What happens during an alarm?** Select a group member.
The banner says **Example — no commands are sent.** The example lists groups
that source may start, assigned/blocked sounders and reasons, global smoke-phone
recipients, ordered start/recovery scripts, disabled features and release rules.
Existing incident attempts are considered. Recovery scripts are future conditions,
not requests made now. A source excluded from group origins can still be a global
smoke source; that distinction is shown.

This is a read-only analysis. It creates no incident, HA state, receipt, saved
setting, command, test or executable confirmation. It shares planning, identity,
idle and receipt checks with execution. Current manual sounders are not adopted;
changed/missing mappings remain blocked. Changing settings invalidates an old
example; the example never becomes permission. It cannot promise audible sound
or physical script effects.

## Diagnosis and a support report

Open **Settings > Diagnosis**. The local snapshot shows actual manifest/HA
versions, source completeness, assignment counts, canonical catalog assessments,
missing prerequisites/targets and bounded recorded failures. Problem cards explain
the limitation and point to the existing setting. Unknown information stays unknown.

The readable JSON preview is built server-side from a field allowlist. Device,
room, group, target, recipient and script identifiers become consistent aliases
within the report. Raw names/IDs, addresses, exact location, credentials, message
bodies, script contents, full registries/configuration and provider payloads are
excluded. Canonical reviewed model names can appear; unknown raw model strings
do not. No client flag can disable anonymization. Preview before **Copy this
report**. Nothing is uploaded. If clipboard access is unavailable, select/copy
the read-only preview manually. Refresh explicitly for a new snapshot.

The panel and all new commands remain admin-only. Diagnosis/examples grant no
additional execution rights. Current smoke status, HA acceptance, device feedback
and unconfirmed physical effects remain separate. No smoke reported is not a
safety guarantee; complete is not a health check; self-test success is not smoke
detection validation.

## Local review and evidence

Use the existing simulator at **http://127.0.0.1:8131/alarmmesh** after its guarded
ownership check. Keep the existing local account. All outputs there are explicit
mock receivers/controls and event-only scripts; no real MQTT/Zigbee/cloud is set up.
The separate Overview simulation dashboard provides battery/fault/outage/failure
helpers. Finish with helpers off, result idle, maintenance/incident notifications,
scripts and linking off. Preserve the test configuration/account.

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```

The bridge permits outbound traffic and is not a LAN firewall; only simulated
data is configured. Evidence stays under ignored
`config/maintenance-features/a9877b15063146dbab3cb9dcaf0e0ab0/`.
The standard route is `pwsh -NoProfile -File ./dev/validate.ps1`, retaining Linux
Python 3.14 / HA 2026.10.4 and exact compatibility on 2026.11.1. The existing
package-update runner additionally checks a real process restart with receipts.
This is file-update/stopped-file recovery evidence, not an installer/HA backup test.

Visual matrix (NL/EN × light/dark × 390×844/1024×768): **NOT EXECUTED** in this
round. The browser host is unavailable and the native pipe reports `os error 2`.
No new screenshots or visual PASS are claimed. Form/clipboard tests are DOM tests,
not layout/phone delivery proof. Physical acceptance remains unperformed.

### Results — 2026-11-15

These results cover base `478c237156cedec6fe7695d20f30aae3b6cc1afd` **plus the
local changes**, not a new hosted CI run or published version. The machine-readable
summary, scope audit and initial failing regressions are in the evidence directory
above (`results.json`, `scope-result.json`, `recovery-before.log`,
`disable-before.log`, `preview-paused-before.log`).

| Check | Actual version / result | Local evidence under `config/` |
| --- | --- | --- |
| Full baseline / Ruff lint / Ruff format | Linux Python 3.14.10, HA 2026.10.4; **486 tests PASS**, including the unchanged 79 status tests | `validation/c16086d2f1f24028822c6f00f6589979/baseline.log`, `pytest.xml` |
| Frontend | **55 DOM tests PASS**; no visual inference | same validation directory, `frontend.log` |
| PowerShell parse + failure-path checks / Compose / official hassfest | **PASS**; zero invalid integrations | same validation directory, `validation-result.json`, `hassfest.log` |
| Compatibility | actual HA **2026.10.4** and **2026.11.1**; **27 runtime + 16 isolated provider checks PASS per version** | same validation directory, `compatibility-2026.10.4.json`, `compatibility-2026.11.1.json` |
| File update, real process restart, removal/re-addition, stopped-file snapshot recovery | HA **2026.10.4 PASS**, including preserved maintenance receipts and no replay | `update-checks/2026.10.4/8c6190e151404466b444f261456655bb/update-result.json`, `phase-restart-result.json` |
| Two deterministic ZIPs / closed inventory | **PASS**, 35 files; byte-identical to the final validated integration source | `release-packages/maintenance-a9877b15-one/` and `maintenance-a9877b15-two/`, each `inventory.json` |
| Protected files / assertions / local links / privacy / diff whitespace | **PASS**; original Python tests unchanged, original frontend assertions retained | evidence directory above, `scope-result.json` |
| Simulator | HA **2026.11.1**, owned read-only mounts and localhost binding verified; current module HTTP 200; automatic outputs off | evidence directory above, `simulator-result.json`; configuration audit after restart, not authenticated UI inspection |
| NL/EN × light/dark × phone/tablet | **NOT EXECUTED**, all eight; unavailable browser host | `results.json`, `visual_matrix`; no screenshots |
| Phone delivery, detector behavior, physical smoke / connectivity | **NOT EXECUTED**, outside simulated acceptance | No physical evidence claimed |

Both ZIP SHA-256 values are
`4dfed648428193e3149f41e0707d240457fa97349b3d53f1dc14ef4075b1503b`.
They are local test packages, not published or distribution-approved artifacts.
The restart/update runner uses an independent integration copy and stopped test
files; it does not establish Marketplace/HACS end-to-end behavior or HA backup
restore behavior for this new work. The earlier failed full run is retained under
`validation/8903427b3cf240d0976ad5022a24bcf9/`: a test-driver WebSocket ID went
backwards after adding scenarios. The driver was corrected; no product gate or
test assertion was weakened. The final complete run above passed.

The focused failures reproduced before correction were a false recovery while a
source was missing, a pending timer surviving disable, and an action example
offering phone/script eligibility while execution was paused. Their regressions
now pass in the full suite. Startup tests also cover the HA-started subscription
and quiet baseline. No smoke rule, device contract or automatic default changed.

To finish visual acceptance when the supported browser host is available, use the
existing local account at the URL above and fully refresh the panel once for the
new cached assets. Inspect each matrix combination, then exercise settings cancel
and exact confirmation, simulated delayed maintenance/recovery/failure, a blocked
example, local diagnosis copy and a populated form across disconnect. Use only
simulation helpers, restore all helpers/result to off/idle and leave automation
off. Ordinary reconnect preserves drafts; a full browser refresh does not promise
to retain an unsaved draft. No new onboarding is needed.

Official references checked 2026-11-15:
[Companion notification services](https://companion.home-assistant.io/docs/notifications/notifications-basic/),
[HA event helpers/lifecycle](https://contributors.home-assistant.io/core/integrations/events/),
[WebSocket authorization](https://contributors.home-assistant.io/core/internals/websocket-api/),
[battery sensor semantics](https://contributors.home-assistant.io/core/entities/sensor/).


## Independent visual follow-up


Datum: 15 november 2026. Basis `478c237156cedec6fe7695d20f30aae3b6cc1afd`
(beta.5) met lokale wijzigingen. Alleen de eigendomsgecontroleerde simulator
`http://127.0.0.1:8131/alarmmesh`, HA 2026.11.1, is bediend.

## Code en bestaand bewijs

- De HTTP-/zelftestcorrectie is behouden: getRandomValues, 32 hextekens,
  aanvraagcorrelatie en specifieke fout bij ontbrekende veilige willekeur.
- Alle product- en testbestanden kwamen bij aanvang bytegewijs overeen met de
  eerder geslaagde export `config/validation/c16086d2f1f24028822c6f00f6589979/source`.
  Alleen README en drie documentatiebestanden waren daarna gewijzigd. Dit was
  bewijsverificatie, geen nieuwe uitvoering van die eerdere checks.
- De nieuwe uitvoeringsroutes zijn gericht gelezen op standaard-uit, ontvanger-
  validatie, begrensde ontvangstbewijzen, expliciet herstel, pauzeren/opruimen,
  uitvoerloze preview en de diagnostische veldallowlist. Geen volledige formele
  veiligheidsaudit of fysieke apparaatvalidatie geclaimd.

## Werkelijk uitgevoerde simulatorstromen

1. Onderhoud stond aanvankelijk uit, geen onderhoudsontvangers, herstel uit,
   wachttijd 15 minuten. Alleen de twee expliciete mocktelefoons geselecteerd;
   batterij/storing/uitval en herstel met wachttijd 5 minuten exact bevestigd.
2. B-foutinjectie aan en batterij B naar 14%: twee mockpogingen, A geaccepteerd,
   B mislukt. B onbeschikbaar gemaakt: batterijprobleem bleef open bij onbekend
   bewijs; uitval wachtte zonder onmiddellijke extra aanvraag.
3. De volledige vijf minuten zijn werkelijk verstreken. De HA-helperdialoog
   toonde vijf minuten uitval; daarna telde de mockteller vier aanvragen en
   toonde Onderhoud ook voor uitval A geaccepteerd/B mislukt.
4. B weer beschikbaar en batterij normaal: uitsluitend A ontving twee
   herstelpogingen, totaal zes. B kreeg geen herstel na een mislukte
   probleempoging. Alleen foutinjectie uitzetten veroorzaakte geen retry.
5. Tijdelijke groep met lange naam, A/B als leden en A als opgeslagen doel,
   maar koppeling en scripts uit. Actievoorbeeld bekeken, inclusief verschillende
   bron-/doelrollen en geblokkeerd doel. Geen uitvoeringsknop aanwezig. De
   aparte zoemer-/apparaatuitvoerteller bleef nul. Geen rookhelper geactiveerd.
6. Diagnosepreview bevatte versies, aliassen en geregistreerde mockfouten.
   Lokaal kopiëren gaf geldige JSON; in de gekopieerde uitvoer kwamen geen
   SIMULATED/SIMULATIE-namen, binary_sensor-ID's, mobile_app-ID's of localhostadres
   voor. Geen upload. Brede ongewenste-velddekking blijft aanvullend testbewijs.
7. Na herstart bleven instellingen en ontvangstbewijzen behouden; mocktellers
   bleven na reset nul, geen replay. Onopgeslagen onderhoudsconcept (30 minuten,
   storing uit) bleef ook bij een tweede gewone stop/start behouden. Offline
   bewaren geblokkeerd; na verbinding weer beschikbaar. Annuleren herstelde de
   bewaarde 5 minuten/storing aan. Volledige browserreload is geen conceptgarantie.

De visuele mockbronnen A/B zijn Zigbee2MQTT-profielen. De providerneutrale
onderhouds-/UI-logica is bekeken; aanvullende ZHA-providerdekking komt uit de
geautomatiseerde checks en is geen nieuw fysiek of visueel ZHA-apparaatbewijs.

## Twee gevonden presentatieproblemen hersteld

- Een geblokkeerd previewdoel werd onterecht als een vastgestelde
  activering-only-capaciteit gepresenteerd. Het voorbeeld zegt nu dat stoppen
  voor dit geblokkeerde doel niet is beoordeeld. Bevoegdheden en uitvoering
  blijven ongewijzigd. Nieuwe EN/NL-regressie faalde vóór de correctie.
- Een daadwerkelijk herstelontvangstbewijs heette Herstelvoorwaarden. Dat heet
  nu Herstelaanvraag / Recovery request; de toekomstige herstelvoorwaarden in
  het actievoorbeeld behouden hun eigen label. Nieuwe regressie faalde vóór
  correctie. Beide correcties zijn visueel bevestigd.

## Acht werkelijk bekeken visuele combinaties

Nederlands/Engels (GB) × licht/donker × 390×844/1024×768, alle acht bekeken.
Per combinatie: onderhoudsdialoog, uitvoerloos actievoorbeeld met lange groepsnaam
en diagnoseoverzicht, samen 24 matrixbeelden. Geen horizontale afsnijding in de
bekeken vensters; teksten breken af en formulieren/dialogen blijven scrollbaar.
Ook ontvangers, wachttijd, bevestiging en ontvangstbewijzen zijn aanvullend bekeken.
Dit is browseremulatie, geen fysieke telefoon-/tablet- of volledige WCAG-audit.

Beelden staan onder
`C:/Users/Steven/Documents/ChatGPT/AlarmMesh/ui-maintenance-2026-11-15/`.
Matrixnamen: `{nl,en}-{light,dark}-{phone,tablet}-{settings,preview,diagnosis}.jpg`.
Enkele vroege opnamen toonden nog het vorige animatieframe; de matrix is daarom
in afzonderlijke stappen opnieuw vastgelegd en geïnspecteerd. De matrixbestanden
zijn vervangen door de correcte, stabiele schermen. `diagnosis-phone-initial.jpg`
is een losse voorlopige opname en telt niet als matrixbewijs.

## Definitieve nieuwe validatie

`config/validation/a5164124bd43418984a387f0f9b11c25/validation-result.json`: PASS.

- 486 backendtests PASS; bestaande 79 statustests behouden.
- 57 frontendtests PASS, inclusief HTTP-correctie en beide nieuwe regressies.
- Ruff/format, hassfest, PowerShell/Compose en cleanup PASS.
- Exact HA 2026.10.4 en 2026.11.1: elk 27 runtime- en 16 providerchecks PASS.

Dit is nieuwe lokale uitvoering op de uiteindelijke productcorrecties. De eerder
geslaagde run `df858c9c28f342bf91f01bde2a83eb89` dekte nog niet de laatste
herstellabelcorrectie en is alleen tussentijds bewijs.

## Eindstand en beperkingen

Oorspronkelijke A+B-selectie behouden. Tijdelijke reviewgroep verwijderd.
Onderhoud uit, herstel uit, wachttijd 15 minuten en onderhoudsontvangers verwijderd.
Rookmeldingen/automatische scripts/koppeling uit; alle gebruikte helpers uit en
resultaat idle. Nederlandse taal en automatisch thema hersteld, tijdelijke
viewport verwijderd. Simulator blijft beschikbaar; historisch mockbewijs bewaard.

Geen echte HA-installatie, melder, sirene, telefoon of externe scriptactie
benaderd of aangestuurd. Geen nieuwe commit, push, tag, publicatie of hosted CI.
De resultaten bewijzen geen fysieke rookdetectie, hoorbaar geluid, telefoonbezorging
of volledige Zigbee2MQTT-/ZHA-radioketen. Binnen de hierboven afgebakende visuele
acceptatie blijft geen browserblokkade over.
