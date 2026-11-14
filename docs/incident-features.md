# Incidenten, meldingen, acties en zelftests (lokale ontwikkeling)

De actuele functionele afwerking en pakket-/updatecontrole staan in de
[afrondingsreview](finish-review.md). Onderstaande eerdere meetresultaten blijven
gedateerd bewijs en vervangen de nieuwe controle niet.

De aanvraagreview van 2026-11-14 is verwerkt. De eerdere 412-testuitkomst blijft
historisch bewijs; de [actuele resultaten na correctie](#actuele-controleresultaten)
gelden voor de aangepaste werkboom. Visuele acceptatie is nog niet uitgevoerd.

Deze uitbreiding staat alleen in de werkboom boven `b2f3d719a86cffb0a533fa5650dce624fd2275f2`.
Er is niets gepubliceerd of op een echte installatie uitgevoerd. Nieuwe
meldingen en scriptacties staan uit. Bestaande expliciete koppelkeuzes blijven
behouden; bijwerken schakelt geen nieuwe uitvoer in.

## Beginnen in het paneel

1. Selecteer bestaande rookbronnen via de integratieopties. Controleer eerst
   rookmelding en bronbeschikbaarheid in **Overzicht**. `complete` betekent
   bruikbare HA-statuswaarden, geen heartbeat of fysieke gezondheidscontrole.
2. Open **Groepen**. Kies leden en afzonderlijk welke leden een incident mogen
   starten. Zonder expliciete bronbeperking blijven bestaande groepen alle leden
   als rookbron gebruiken. Kies alleen de bedoelde ondersteunde zoemers.
   Naam, HA-ruimte, provider en beperkingen blijven bij de melder zichtbaar.
3. Bewaar een ingeschakelde koppeling pas na het concrete bron/doeloverzicht en
   bevestiging. Verschillende providers mogen in dezelfde groep voorkomen;
   modelnaam alleen is nooit bedieningsbevoegdheid. Bosch-broadcast moet al uit
   staan; AlarmMesh verandert geen apparaatvoorwaarde.
4. Voor meldingen: open **Instellingen > Meldingen**. Kies uit werkelijk
   geregistreerde Companion-diensten, zet de bedoelde ontvangers aan en bevestig
   de selectie. Ontbrekende opgeslagen ontvangers blijven zichtbaar. Voorbeeldtitel
   en bericht staan in het formulier. Een testknop vraagt afzonderlijk bevestiging
   voor de genoemde ontvanger; het bewaren van instellingen verstuurt geen test.
5. Voor acties: bewerk een groep, kies **Acties bij incident**, voeg bestaande
   HA-scripts voor begin en/of bevestigd herstel toe en stel hun volgorde in.
   Bevestig de exacte configuratie. Een test van een script vraagt opnieuw
   afzonderlijke bevestiging. Een script heeft zijn eigen gevolgen; AlarmMesh
   draait die niet terug en bevestigt geen lamp, deur of andere fysieke uitvoering.

In een bestaande actieve rooktoestand kan bewust inschakelen van automatische
uitvoer direct een eerste aanvraag veroorzaken. Configureer daarom alleen met
kennis van de actuele bronwaarden. Alleen beheerders kunnen configureren en tests
starten. Geen vrije diensten, YAML, templates of uitvoerpayloads vanuit het paneel.

## Incidenten en uitvoer lezen

**Overzicht > Incidenten** en **Instellingen > Incidenten** tonen actuele
rookbronnen/ruimtes, betrokken groepen, zoemeraanvragen, ontvangers, scripts en
zelfteststatus. Een melding bevat bronnaam/ruimte waar bekend, groepen, tijd,
een lokale incidentlink en bekende zoemerproblemen. Geen fysiek geluid of
telefoonontvangst wordt bevestigd. Gewone Companion-meldingen vereisen de normale
telefoonrechten. Kritieke meldingen worden niet aangeboden zonder aangetoond
platformcontract; deze versie gebruikt gewone meldingen.

Er is één eerste melding per incident en ontvanger. Een nieuwe rookbron kan één
update veroorzaken; identieke events en overlappende groepen geven geen dubbele
melding. Mislukte aanvragen worden niet eindeloos herhaald. Een latere nieuwe
rookbron kan een betekenisvolle update geven, ook na een eerdere verzendfout.
Een ontvangerfout blokkeert andere ontvangers, scripts of zoemers niet.

Scriptaanvragen zijn per incident, groep, fase en script ontdubbeld. De volgorde
betreft het **starten** van scripts; `script.turn_on` wacht niet op voltooiing van
het script. Alle uitvoer deelt maximaal acht gelijktijdige aanvragen met tien
seconden softwarewachttijd per aanvraag. Er is geen automatische herhaling of
terugdraaien. Herstelberichten (optioneel) en herstelacties volgen uitsluitend na
expliciete rookvrije waarden van alle relevante bronnen. Onbekend, ontbrekend of
onbereikbaar is geen herstel. Elke groep heeft een onafhankelijke levensduur.

De beperkte uitvoerregistratie bewaart geen bronwaarnemingen als actuele waarheid,
geen berichttekst, tokens of ruwe providerpayloads. Er blijven maximaal één
lopende/laatste registratie per groep en één voor meldingen, elk maximaal 60
ontvangstbewijzen. Afgeronde registraties vervallen na 24 uur; lopende worden niet
op tijd rookvrij verklaard. Opnieuw laden bouwt rookstatus opnieuw op, maar herhaalt
geen reeds geregistreerde melding/scriptaanvraag. Onderbroken aanvragen worden
onbekend. Zoemereigendom blijft uitsluitend in de bestaande runtime; er wordt
geen handmatige activering overgenomen of algemeen lokaal alarm gestopt.

## Ingebouwde zelftest is geen zoemertest of simulatie

Een knop op het melderdetail verschijnt alleen bij een exact onderbouwde
model/providerroute en passende bestaande HA-entiteiten op hetzelfde apparaat.
Voor iedere aanvraag moet de beheerder de genoemde melder en mogelijk geluid
bevestigen. Één test tegelijk; geen planning of massatest. Alle gekozen bronnen
moeten expliciet rookvrij zijn, zonder actief incident, conflicterende bediening
of lopende test. Identiteit, rechten, deadline en conflicten worden opnieuw
gecontroleerd vlak vóór verzending, ook na wachten op uitvoerruimte.

| Model | Provider / bestaande HA-bediening | Wat kan worden vastgesteld? |
| --- | --- | --- |
| Heiman HS1SA-E-PLUS | Zigbee2MQTT, button `trigger_selftest` | Aanvraag en `test`-activiteit; geen expliciet geslaagd-resultaat |
| Aqara JY-GZ-01AQ, gedocumenteerde alias JY-GZ-03AQ | Zigbee2MQTT, button `selftest` | Aanvraag en `test`-activiteit; geen expliciet geslaagd-resultaat; bekende firmware 21 geblokkeerd |
| Halo Smart Labs HALO / HALO+ | Zigbee2MQTT, select `test_cycle` met `start` | Alleen na verse activiteit: expliciet `halo_test_result` geslaagd/mislukt; oude succeswaarde telt niet |
| LUMI lumi.sensor_smoke.acn03 | ZHA, bestaande Aqara `self_test`-knop | Alleen aanvraag; de gecontroleerde ZHA-versies bieden hier geen afzonderlijke resultaatentiteit |
| Overige modellen/providers of ontbrekende vereiste entiteiten | Geen vrijgegeven route | Geen zelftestknop; zoemerondersteuning is geen zelftestondersteuning |

Een verstuurde HA-aanvraag is geen geslaagde zelftest. Geen passend
apparaatresultaat binnen twee minuten, identiteitsverlies, reload of onderbreking
wordt **uitkomst onbekend**. Een geëindigde testvlag is geen succesbewijs.
Echte rook blijft zichtbaar en kan incidentuitvoer starten tijdens een test; alleen
losse testfeedback start geen rookincident. Er worden geen hush/mute/cancel,
Zigbee-clusters of MQTT-commando's door AlarmMesh zelf toegevoegd.

De bestaande [zoemerprofielen](device-compatibility.md) veranderen niet: 17/52
Zigbee2MQTT- en 10/52 ZHA-definities hebben een beoordeeld activeringsprofiel,
steeds afhankelijk van actuele HA-entiteiten en voorwaarden. Alleen het bestaande
Heiman PLUS MQTT-profiel heeft beperkte stopbevoegdheid voor aantoonbaar eigen
activering. Alle andere profielen blijven zonder automatische stop. Het catalogusveld
zelftest beschrijft de oudere uitleesdekking; de bovenstaande tabel bepaalt de nieuwe
aanvraagroute. Geen model is fysiek gevalideerd in deze opdracht.

## Bewijs en afzonderlijke simulatie

De actuele resultaten voor deze werkboom staan onderaan deze pagina. Historische
acceptatieresultaten en gebruikersrapportage blijven in de
[acceptatiematrix](acceptance-matrix.md); zij bewijzen deze nieuwe functies niet.

```powershell
pwsh -NoProfile -File ./dev/validate.ps1
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```

De afzonderlijke omgeving gebruikt HA 2026.11.1, localhost en alleen-lezen
integratie-/fixturemounts. URL: **http://127.0.0.1:8131/alarmmesh**. De gebruiker
heeft lokale onboarding voltooid. Voeg AlarmMesh toe met simulatiebronnen A+B
als dat nog niet is gebeurd. De bestaande omgevingen op 8124–8130 blijven intact.
Stop bewaart account en configuratie. De eigen bridge is geen LAN-egressfirewall;
er zijn geen cloud-, broker- of productieaccounts/apparaten ingericht.

De simulator heeft mockzoemers, twee mock-Companiondiensten, uitsluitend
eventgenererende scripts en expliciete mockzelftestfeedback. Tellerschermen zijn
**geen echte gsm-bezorging, geluid of apparaatresultaat**. Gebruik alleen de
speciaal gemaakte simulatiehelpers. Normaal eindpunt: rook- en uitvalhelpers uit,
`catalog_test` uit, testresultaat `idle`, foutinjectie uit; nieuwe automatisering uit.
Er zijn geen helpers door de agent bediend zolang browserbediening ontbreekt.

Nog visueel af te vinken: telefoon/tablet, Nederlands/Engels, licht/donker,
instellingen/ontvangers, groepen met bronbeperking en scripts, annuleren/bevestigen,
incidentstatussen, mockzelftest en echte rook apart, lange namen, offline formulier
behouden en herstel. DOM-tests bewijzen dit gedrag gedeeltelijk, geen lay-out of
native focus/contrast. Screenshots horen lokaal onder genegeerd `config/incident-ui/`.

## Officiële bronnen, gecontroleerd 2026-11-14

- [Companion-notificatiediensten en lokale links](https://companion.home-assistant.io/docs/notifications/notifications-basic/).
- [HA scripts](https://www.home-assistant.io/integrations/script/) en [scriptuitvoering](https://www.home-assistant.io/docs/scripts/): starten is geen fysieke voltooiing.
- [HA buttons](https://developers.home-assistant.io/docs/core/entity/button/).
- [Heiman PLUS expose en betekenis van test/linkage/sirene](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html).
- [Aqara expose en firmwarebeperking](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html).
- [HALO testfeedback](https://www.zigbee2mqtt.io/devices/HALO.html) en [beide HALO-definities met gedeeld testcontract](https://github.com/Koenkk/zigbee-herdsman-converters/blob/afdaa028a0972d801da762196ddfb2df631ea0cc/src/devices/halo_smart_labs.ts). De aparte HALO+-webpagina gaf 404; de converterdefinitie onderbouwt de variant.
- [Zigbee2MQTT HA-discoverymapping](https://github.com/Koenkk/zigbee2mqtt/blob/master/lib/extension/homeassistant.ts): SET-enum met één keuze wordt een button, meerdere keuzes een select.
- [ZHA AqaraSelfTestButton](https://github.com/zigpy/zha/blob/2.4.3/zha/application/platforms/button/__init__.py) en [Aqara-quirk](https://github.com/zigpy/zha-device-handlers/blob/dev/zhaquirks/xiaomi/aqara/smoke.py): testaanvraag en rookattribuut zijn afzonderlijk. Ook de werkelijk geïnstalleerde ZHA-code in de testimages is gecontroleerd.

Een zelftest bewijst geen rookdetectie; geen rook gemeld is geen veiligheidsgarantie.
Fysieke rookovergangen, daadwerkelijke verbinding, geluid, telefoonbezorging en
productieherstart blijven afzonderlijke, niet uitgevoerde acceptatie.

## Eerdere validatie vóór aanvraagreview

Datum: **2026-11-14**, exact basiscommit
`b2f3d719a86cffb0a533fa5650dce624fd2275f2` plus de hieronder genoemde lokale
wijzigingen. Geen hosted-CI-uitkomst of publicatie voor deze werkboom.

Bewijsmap **V**: `config/validation/a865ead928a943869af406f967c47856/`.
Bewijsmap **F**: `config/incident-features/429ce679bdf342d4a0ffa6f61ea5d1c2/`.
Alle gegenereerde resultaten, configuratie en accounts blijven Git-genegeerd.

| Controle / categorie | Versie en werkelijk resultaat | Bewijs / grens |
| --- | --- | --- |
| Volledige Linux-backend / geautomatiseerd | Python 3.14.10, HA 2026.10.4: **412 PASS**, geen skips; 367 bestaande + 45 nieuwe gevallen | V `baseline.log`, `pytest.xml`; 79 statusgevallen en bestaande assertions behouden |
| Frontend DOM / geautomatiseerd | Node 24.22.1, **33 PASS**, inclusief 26 vooraf aanwezige gevallen | V `frontend.log`; geen browserlay-outbewijs |
| Ruff lint + format / geautomatiseerd | **PASS**, 70 Pythonbestanden | V `baseline.log` |
| Officieel hassfest / geautomatiseerd | **PASS**, 0 ongeldige integraties | V `hassfest.log` |
| PowerShell parse + foutinjecties, Compose / geautomatiseerd | **PASS** | V `validation-result.json`, `compose.log` |
| Officieel HA-image 2026.10.4 / geautomatiseerd | Aangevraagd = werkelijk, **24 runtime + 16 driver PASS**, cleanup PASS | V `compatibility-2026.10.4.json`; eigen interne broker/synthetische discovery, geen apparaten |
| Officieel HA-image 2026.11.1 / geautomatiseerd | Aangevraagd = werkelijk, **24 runtime + 16 driver PASS**, cleanup PASS | V `compatibility-2026.11.1.json`; aparte verse configuratie |
| Nieuwe UI-configuratie / technisch | HA 2026.11.1 `check_config` **PASS**, localhost/mounts gecontroleerd, herstart met bewaard testaccount | F `ui-config-final.log`, `ui-technical-result.json`; niet gelijk aan UI-acceptatie |
| Reproduceerbaar lokaal pakket / technisch | **PASS**, 32 expliciet toegestane bestanden, twee bytegelijke ZIPs, gelijk aan gevalideerde productbron | F `package-final-result.json`; `config/release-packages/incident-429ce679bdf3-final-one/inventory.json` |
| Scope/privacy/lokale links / gerichte audit | Zie F `scope-audit.json` en `documentation-audit.json` | Geen runtimebestanden in Git; geen algemene garantie van een secretscanner |
| Nieuwe telefoon/tablet-UI, beide talen/thema's / visueel | **NIET UITGEVOERD** | Native pipe ontbreekt (`os error 2`), browser access host onbereikbaar. Ook ondersteunde Sky-appinventaris faalt. Onboarding is voltooid, geen authenticatie omzeild |
| Fysieke rook/zoemers/zelftest, gsm-bezorging, echte scripts en productieherstart | **NIET UITGEVOERD** | Alleen mocks, event-only scripts en geisoleerde simulatie; geen echte installatie benaderd |

Pakket-SHA-256:
`d6f8048e26a291979e0ea69d935808774e3a2ae07d5be255ae52d00a73ab7429`.
Dit is een lokaal testpakket, geen gepubliceerde of distributiegoedgekeurde release.

Twee gerichte regressies zijn aantoonbaar eerst gefaald: drie wachtrijgevallen
(verlopen deadline, andere test, handmatige zoemer) in F `queued-before.log` en
twee gevallen met verlies van de testbediening in F `smoke-control-before.log`.
De definitieve correcties slagen in de 412-testsuite; de gecombineerde gerichte
incident/catalogus/koppelset heeft daarnaast **131 PASS** in
F `features-control-corrected.log`. Geen bestaande test of assertion is verzwakt.

De volledige route eindigde met exitcode 0. De eerdere groene route en tijdelijke
ontwikkellogs blijven apart bewaard; zij vervangen niet het bovengenoemde eindbewijs.
Open blijft uitsluitend de nieuwe visuele acceptatie zodra de bedieningshost weer
beschikbaar is, en afzonderlijk geplande fysieke acceptatie. Lokale onboarding hoeft
niet opnieuw. Geen fysieke of productiehandeling wordt voor deze opdracht gevraagd.

## Actuele controleresultaten

Voor de verdere formulier-, incident- en installatieafwerking geldt nu de
[afrondingsreview](finish-review.md). De volgende aanvraagreview blijft historisch
bewijs voor de behouden zelftestcorrectie.

Datum **2026-11-14**, basiscommit
`b2f3d719a86cffb0a533fa5650dce624fd2275f2` plus behouden lokale wijzigingen en
de hieronder beschreven correctie. Geen hosted-CI-resultaat of publicatie voor
deze werkboom.

De onafhankelijke reviewreproductie is permanent opgenomen in
`tests/test_selftest_requests.py`. Vóór herstel verstuurden verlopen aanvraag A
en opvolger B twee mockopdrachten; verwacht was alleen één opdracht van B.
Bewijs: `config/selftest-review/f0018f3fa1094ddab032f3878606ae83/reproduction-before.log`
met `Only B may dispatch; observed 2 calls`. Dezelfde regressie slaagt na herstel.

Iedere taak heeft nu een eigen aanvraagrecord, aanvraag-ID, vaste deadline,
observatiegegevens en opruimfuncties. Alleen de actuele eigenaar mag dispatchen,
status bijwerken of opslaan. Oude timers, callbacks en uitgestelde opslag schrijven
niets naar een opvolger. Late succesvolle afloop, fout of annulering van A verandert
B niet; A retourneert uitsluitend haar eigen uitkomst. Ook een provider die de
eerste timeoutannulering negeert is nagebootst. Deadline, rechten, apparaatidentiteit,
rook en conflicten worden vlak vóór dispatch opnieuw getoetst. Geen nieuwe
zelftestfunctie, automatische retry, opgeslagen schemaverandering of statusregel.

Configuratie én opties leggen nu in Engels/Nederlands kort uit welke functies
optioneel zijn, dat nieuwe automatisering uit staat, waar deze wordt ingesteld,
welke zelftests afzonderlijke bevestiging vereisen en dat geen rook gemeld geen
veiligheidsgarantie is. De selectieuitleg blijft behouden.

Bewijsmap **R**: `config/selftest-review/f0018f3fa1094ddab032f3878606ae83/`.
Volledige validatie **V2**: `config/validation/50f8648c2d6843158a8167a4b61966f0/`.

| Controle | Werkelijk resultaat | Bewijs |
| --- | --- | --- |
| Aanvraag-, tekst- en bestaande incidentregressies | **61 PASS**; 12 aanvraaggevallen, 4 tekstgevallen en 45 behouden incidentgevallen | R `request-regressions-third.log` |
| Volledige backend | Linux Python 3.14.10 / HA 2026.10.4: **428 PASS**, geen skips; alle 412 vooraf aanwezige tests behouden | V2 `baseline.log`, `pytest.xml` |
| Frontend DOM | Node 24.22.1: **33 PASS** | V2 `frontend.log`; geen visueel bewijs |
| Ruff, format, officieel hassfest, PowerShell/foutinjecties, Compose | **PASS** | V2 `validation-result.json` en fase-logs |
| Officieel HA 2026.10.4 | Werkelijke versie gelijk aan aangevraagde: **24 runtime + 16 driver PASS**, cleanup PASS | V2 `compatibility-2026.10.4.json` |
| Officieel HA 2026.11.1 | Werkelijke versie gelijk aan aangevraagde: **24 runtime + 16 driver PASS**, cleanup PASS | V2 `compatibility-2026.11.1.json` |
| Pakket | **PASS**, 32 bestanden, twee bytegelijke builds en gelijk aan gevalideerde productbron | R `package-result.json`; `config/release-packages/selftest-f0018f3fa109-one/inventory.json` |
| Scope, beschermde bestanden en lokale links | Zie R `scope-result.json` en `documentation-result.json` | Bestaande tests/assertions en `status.py` ongewijzigd |

De volledige route `pwsh -NoProfile -File ./dev/validate.ps1` eindigde met exit 0.
Pakket-SHA-256: `d8b2ea87bbe94ac39f347a1f934b577e41c7ac5ed3da9f573abef715ca2bdfb6`.
Dit blijft een lokaal testpakket, geen gepubliceerde release.

### Visuele controle na de aanvraagcorrectie

Beide ondersteunde bedieningsroutes zijn geprobeerd: `sky.list_apps` faalt met
native pipe ontbreekt (`os error 2`); `cua.getState` meldt daarnaast
`The browser access host is unavailable`. Er is geen venster of aangemelde sessie
overgenomen, geen authenticatie omzeild en geen browserinvoer uitgevoerd.

| Taal | Thema | Formaat | Resultaat |
| --- | --- | --- | --- |
| Nederlands | Licht | 390×844 | **NIET UITGEVOERD** |
| Nederlands | Donker | 390×844 | **NIET UITGEVOERD** |
| Nederlands | Licht | 1024×768 | **NIET UITGEVOERD** |
| Nederlands | Donker | 1024×768 | **NIET UITGEVOERD** |
| Engels | Licht | 390×844 | **NIET UITGEVOERD** |
| Engels | Donker | 390×844 | **NIET UITGEVOERD** |
| Engels | Licht | 1024×768 | **NIET UITGEVOERD** |
| Engels | Donker | 1024×768 | **NIET UITGEVOERD** |

Dit omvat alle gevraagde schermcontroles: instellingen/ontvangers/preview,
bevestigen en annuleren van mockmeldingen, groepsbronnen/doelen, scriptvolgorde
en bevestiging, incidenten/fouten, mockzelftestfasen en afzonderlijke rookstatus,
lange namen, scroll, toetsenbordfocus en bereikbare knoppen, offline/herstel,
formulieren behouden en oude status wissen. De geautomatiseerde tests vervangen
deze visuele waarneming niet. Er zijn geen nieuwe screenshots gemaakt.

Het aangeleverde reviewverslag bevat een eerdere gedeeltelijke Nederlandse,
donkere telefoonwaarneming vóór deze correctie. Dat is afzonderlijk aangeleverd
reviewbewijs, geen hercontrole van deze aangepaste werkboom.

De actuele UI-matrix staat lokaal onder
`config/incident-ui/316a03fe45be4de3b789e1490bb9bed1/request-review-f0018f3fa109/ui-result.json`.
De simulator is via de bestaande tooling op eigendom, mounts en localhostbinding
gecontroleerd en herstart met werkelijke HA **2026.11.1** om de correctie te laden.
URL: **http://127.0.0.1:8131/alarmmesh**. Bestaand account en selectie blijven
behouden; onboarding is niet opnieuw nodig. Er zijn geen UI-helperstanden,
automatische instellingen of browserinstellingen gewijzigd. De helper-eindstand
kon niet opnieuw visueel worden waargenomen. Zodra de bedieningshost beschikbaar
is, blijven de bovenstaande schermcontroles en het normale eindpunt te bevestigen.
Andere simulatoren en de echte installatie zijn ongemoeid gelaten. Fysieke
detectie, geluid, zelftests, gsm-bezorging en externe scriptgevolgen zijn niet getest.

Actuele officiële [eventhelpers](https://contributors.home-assistant.io/core/integrations/events/),
[entry-opruiming](https://contributors.home-assistant.io/core/integrations/config-entries/)
en [config-/optievertalingen](https://contributors.home-assistant.io/core/integrations/translations/)
zijn gecontroleerd op 2026-11-14; de vaste testbaseline is niet opgewaardeerd.

Deze correctieronde wijzigt uitsluitend `self_test.py`, `strings.json`,
`translations/en.json`, `translations/nl.json`, voegt `tests/test_selftest_requests.py`
en `tests/test_scope_texts.py` toe en werkt deze handleiding, architectuur en changelog
gericht bij. Alle andere vooraf aanwezige lokale wijzigingen zijn behouden.

## Bestanden klaar voor review

Onderstaande lijst betreft de volledige huidige diff, inclusief de acht vooraf
bestaande bestanden met instelhulp/configuratiecontrole. Die wijzigingen zijn
behouden. Statusberekening, alle bestaande backendtests, dependencies, manifestmetadata,
CI en de originele branding zijn ongewijzigd.

Product:

- `custom_components/alarmmesh/__init__.py`
- `custom_components/alarmmesh/automation.py`
- `custom_components/alarmmesh/effects.py`
- `custom_components/alarmmesh/frontend/panel.css`
- `custom_components/alarmmesh/frontend/panel.js`
- `custom_components/alarmmesh/frontend/translations.js`
- `custom_components/alarmmesh/groups.py`
- `custom_components/alarmmesh/linking.py`
- `custom_components/alarmmesh/linking_runtime.py`
- `custom_components/alarmmesh/panel.py`
- `custom_components/alarmmesh/self_test.py`
- `custom_components/alarmmesh/strings.json`
- `custom_components/alarmmesh/translations/en.json`
- `custom_components/alarmmesh/translations/nl.json`

Tests en tooling:

- `dev/frontend/panel.test.mjs`
- `dev/incident-acceptance/configuration.yaml`
- `dev/incident-acceptance/technical-scripts.yaml`
- `dev/incident-acceptance/ui-lovelace.yaml`
- `dev/linking-simulation/alarmmesh_simulation/__init__.py`
- `dev/linking-simulation/alarmmesh_simulation/catalog_fixture.py`
- `dev/linking-simulation/alarmmesh_simulation/incident_fixture.py`
- `dev/mvp-acceptance/check_drivers.py`
- `dev/mvp-acceptance/check_features.py`
- `dev/mvp-acceptance/check_runtime.py`
- `dev/mvp-acceptance/mvp-acceptance.ps1`
- `dev/panel-ui.ps1`
- `dev/release/package.py`
- `dev/tests/test-compatibility.ps1`
- `tests/test_incident_features.py`
- `tests/test_scope_texts.py`
- `tests/test_selftest_requests.py`

Documentatie:

- `CHANGELOG.md`
- `README.md`
- `docs/acceptance-matrix.md`
- `docs/architecture.md`
- `docs/compatibility.md`
- `docs/development.md`
- `docs/device-compatibility.md`
- `docs/incident-features.md`
- `docs/linked-sounding.md`
- `docs/panel.md`
- `docs/roadmap.md`
- `docs/troubleshooting.md`
