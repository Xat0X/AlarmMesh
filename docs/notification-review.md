# Gsm-meldingen: lokale correctie en controle — 17 november 2026

Basis: `0.1.0-beta.10`, commit `50bfe89f83a32455fb2297a73e1fcb22db1b5128`.
Dit verslag betreft ongecommitte lokale wijzigingen. De manifestversie blijft gelijk.
Alle uitvoer ging naar registrerende nepontvangers in tests of de afzonderlijke
simulator op poort 8131. Geen echte telefoon, rookmelder of productie-installatie
is benaderd. Historische reviews blijven historische resultaten.

## Wat is gevonden en hersteld?

1. **Een eigen deadline werd ten onrechte definitief mislukt genoemd.** Zowel een
   testmelding als een incidentmelding kon na tien seconden al onderweg zijn.
   De nieuwe regressies faalden eerst beide. De eigen timeout is nu
   `outcome_unknown`; een expliciete providerfout blijft `failed`. Geen automatische retry.
2. **Een bevestiging bleef bruikbaar nadat de ontvanger/berichtcontext wijzigde.**
   Een nieuwe frontendregressie bevestigde dit. De server bindt de bevestiging nu
   aan de actuele geregistreerde dienst, instellingenrevisie en berichtinhoud.
   Hij controleert opnieuw vóór uitvoering. Alleen het verzendtijdstip mag veranderen.
   Een extra reviewregressie voor tijdstempelachtige bronnamen faalde ook eerst;
   de berichtopbouw sluit nu alleen het daadwerkelijke klokveld uit, nooit naamtekst.
3. **Een verloren testantwoord was niet herleidbaar in het geopende formulier.**
   Ook dit is eerst met een falende frontendtest vastgelegd. Iedere test heeft nu
   een aanvraag-ID en tijdstip. De UI herkent uitsluitend de bijbehorende receipt
   na reconnect, zonder opnieuw te verzenden. Zonder receipt blijft de uitkomst onbekend.

Deze fouten verklaren **niet bewezen** de oorspronkelijke gebruikersmelding
“gsm-meldingen werken niet”. De huidige tests bevestigen geen bezorging op een echte
telefoon. De productieconfiguratie, rechten op die telefoon, transport en precieze
mislukte route zijn niet onderzocht binnen deze opdracht.

## De onderzochte keten

AlarmMesh selecteert werkelijk geregistreerde `notify.mobile_app_*`-diensten.
Opgeslagen namen blijven staan als een dienst verdwijnt. De bestaande servervalidatie,
revisiecontrole, beheerderrechten, bronidentiteit en incidentontdubbeling blijven gelden.
Een testmelding vereist een actuele afzonderlijke bevestiging, maar geen ingeschakelde
automatische incidentmeldingen. De groeps-/bron- en herstelregels zijn niet veranderd.

De integratietest gebruikt Home Assistants echte `BaseNotificationService` uit
`notify.legacy`: registratie, notify-schema en targetmapping worden uitgevoerd.
Alleen `async_send_message` is vervangen door een registrerende lokale ontvanger.
Deze basisadapter wordt ook door `MobileAppNotificationService` gebruikt. De echte
mobiele pushtransportlaag, telefoonrechten en telefoonbezorging zijn **niet** getest.
De geïnstalleerde HA 2026.11.1-broncode is gelezen: een normaal teruggekeerde call
levert geen betrouwbaar eindbewijs van telefoonbezorging.

Gecontroleerde officiële documentatie, 2026-11-17:
[Companion: basisnotificaties](https://companion.home-assistant.io/docs/notifications/notifications-basic/),
[HA Notify](https://www.home-assistant.io/integrations/notify/),
[notify.send_message](https://www.home-assistant.io/actions/notify.send_message/).
Die laatste entiteitsroute vervangt niet op goed geluk de geregistreerde Companion-dienst.

## Instellen en onderzoeken

- **Instellingen → Meldingen instellen** toont gekozen en verdwenen ontvangers.
  Automatische incidentmeldingen en herstelmeldingen zijn afzonderlijke keuzes.
- **Telefoons opnieuw controleren** ververst alleen de lijst. Onverzonden keuzes
  blijven staan en de oorspronkelijke revisie blijft gelden; er gaat geen aanvraag uit.
- Het formulier toont een voorbeeld; **Testmelding sturen** toont het daadwerkelijke
  testbericht en vraagt expliciete bevestiging voor precies die ontvanger.
  De berichttaal volgt de HA-installatietaal; de paneeltaal volgt de gebruiker.
- **Melders → Bekijk alarmroute** toont per telefoon gekozen/ingeschakeld/beschikbaar,
  de reden om wel/niet een aanvraag toe te staan en een uitklapbaar berichtvoorbeeld.
  Preview en uitvoering delen de configuratiebeslissing en ontdubbelingsregels.
- Instellingen, incidenten en activiteiten maken de laatste testaanvraag herkenbaar.
  Fouten/onbekende uitkomsten verwijzen naar ontvangerinstellingen. Het bestaande
  begrensde activiteitenjournaal bewaart aanvraagcontext, geen tokens of berichtinhoud.

| Status | Betekenis |
| --- | --- |
| Nog geen telefoon gekozen | Geen ingeschakelde ontvanger opgeslagen |
| Automatische meldingen uit | Een afzonderlijk bevestigde test kan nog wel |
| Klaar om een aanvraag te versturen | Actuele configuratie/dienst staan een aanvraag toe; geen bezorgingsbewijs |
| Aanvraag bezig | De HA-aanroep loopt |
| HA verwerkt/geaccepteerd | Serviceaanroep voltooid; telefoonbezorging onbevestigd |
| Mislukt/geblokkeerd | Fout of gewijzigde voorwaarden; controleer dienst/rechten/keuze |
| Uitkomst onbekend | Deadline, onderbreking of ontbrekend antwoord; niet automatisch herhaald |

Geen rook gemeld is geen veiligheidsgarantie. `complete` is geen heartbeat of
fysieke gezondheidscontrole. Batterijgegevens en een geslaagde HA-aanroep bewijzen
geen apparaatwerking; een zelftest bewijst geen rookdetectie.

## Werkelijk uitgevoerde controles

Lokaal bewijs staat onder het genegeerde `config/notification-review/`.
De regressies blijven in `tests/test_notification_route.py` en
`dev/frontend/panel.test.mjs`; de screenshots en scripts bevatten alleen simulatorbewijs
maar blijven buiten Git, inclusief de lokale browsersessie.

| Controle | Uitkomst / bewijs |
| --- | --- |
| Backend vóór correctie | Twee timeoutregressies FAIL; echte HA-adapter PASS; `before.log` |
| Frontend vóór correctie | Verouderde bevestiging en verloren antwoord FAIL; `frontend-before.log` |
| Eerste volledige backend na correctie | 554 PASS op de vastgelegde 2026.10.4-baseline; `full-backend.log`; daarna één extra contextregressie toegevoegd |
| Extra bevestigingsregressie | Eerst FAIL, daarna zeven nieuwe tests PASS; `context-name-before.log`, `route-final.log` |
| Browserflows op HA 2026.11.1 | PASS; `flows.json`: A+B kiezen/bewaren/heropenen, annuleren/concept, preview zonder uitvoer, handmatige mocktest, fout, timeout, verdwenen dienst, verlopen bevestiging, reconnect, automatische incident-/herstelmelding |
| Verbindingsverlies bij bewaren | PASS; echte serveropslag, vervolgens bewust verloren antwoord + reconnect; formulier en opgeslagen keuze behouden; geen automatische herhaling |
| Verbindingsverlies bij test | PASS; echte browser offline/reconnect terwijl alleen de mockontvanger wacht; één aanvraag, uitkomst onbekend |
| Visuele matrix | Acht combinaties NL/EN × licht/donker × 390×844/1024×768 daadwerkelijk gerenderd en screenshots bekeken; `matrix.json`, `screenshots/` |
| Aanvullende UI | Desktop 1440×900, focus/Enter/Escape, scrollen, HTML-achtige/lange namen, lege ontvangerlijst en 512×384-reflow bekeken. Reflow is een CSS-viewportproef, geen native browserzoom |
| Gerichte gebruiksaudit | PASS; `usability.json`: alarmroute, gewone groep met opties dicht/uit, gsm-keuze/concept, tijdelijke bronuitval, herstelvoorbereiding en formulierbehoud bij echte reconnect; nul uitvoeropdrachten |
| Definitieve validatieroute | **PASS**: 555 backendtests (HA 2026.10.4 / Linux Python 3.14), 95 frontendtests, Ruff lint/opmaak, hassfest, PowerShell, Compose, beide HA-runs en cleanup; `config/validation/d95969e0087e4a0bb915b88003b89d92/validation-result.json` |
| Reproduceerbaar pakket | Twee builds, 41 integratiebestanden, identieke ZIP-hash en inventaris; `config/release-packages/notification-final-a/` en `notification-final-b/` |
| Echte telefoon / fysieke detector / productieherstart | NIET UITGEVOERD; buiten de geautoriseerde scope |

De taaloverride, lange ontvangernaam en lege lijst in de visuele matrix zijn expliciete
browser-layoutfixtures. Er wordt daarbij niets verzonden of serverselectie verwijderd.
De buitenste HA-gebruikersinterface blijft in haar bestaande taal. Screenshots zijn
werkelijk geïnspecteerd; de DOM-assertions zijn afzonderlijk technisch bewijs.

Een tussenrun (`3e92cffe8ffb4c1a850e161e77925121`) slaagde met 554 backendtests en
95 frontendtests. Na de extra contextcorrectie is de volledige route opnieuw uitgevoerd.

De eerste volledige validatie (`8d2fc5c4b7544b1d8681b16400b39020`) was **FAIL** door één
Ruff-opmaakafwijking in de nieuwe activity-code; die is hersteld. Frontend, hassfest,
PowerShell/Compose en beide HA-runs waren in die poging al groen. Een nieuwe complete
run wordt afzonderlijk vastgelegd; het eerdere falen blijft in de lokale logs staan.

Pakket SHA-256: `9c47d037ba765d9088fc7f8fdf51bb6e23fb6536b06abfbc443b5ed7bfe6d77c`.
Dit is uitsluitend een lokaal testpakket, geen nieuwe release of distributiegoedkeuring.

## Rondleiding van maximaal vijf minuten

Open <http://127.0.0.1:8131/alarmmesh> (alleen de mocksimulator).

1. **Instellingen → Meldingen instellen**: bekijk dienstbeschikbaarheid en berichtvoorbeeld;
   automatische meldingen staan uit. Opnieuw controleren verstuurt niets.
2. Kies desgewenst één **simulated** telefoon; bekijk **Testmelding sturen**. De
   bevestiging toont ontvanger en testtekst. Annuleren vóór bevestigen stuurt niets.
3. **Melders → Bekijk alarmroute**: lees waarom een telefoon wel/niet zou meedoen.
4. **Activiteiten** of **Incidenten**: open de opgeslagen aanvraagcontext en onderscheid
   HA-verwerking van fysieke resultaten. Onbekend is geen geslaagde bezorging.
5. Sluit het formulier. Laat automatische uitvoer uit en de simulatie in rust.

Stop uitsluitend deze simulator met:
`pwsh -NoProfile -File dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop`.
Account en configuratie blijven behouden. Geen productieomgeving is gewijzigd.

## Gewijzigde bestanden

- Runtime/API: `custom_components/alarmmesh/automation.py`, `effects.py`,
  `preview.py`, `activity.py`, `panel.py`.
- Paneel: `custom_components/alarmmesh/frontend/panel.js`, `translations.js`.
- Regressies: `tests/test_notification_route.py`, `dev/frontend/panel.test.mjs`.
- Alleen simulatie: `dev/linking-simulation/alarmmesh_simulation/incident_fixture.py`.
- Documentatie: `README.md`, `CHANGELOG.md`, `docs/architecture.md`,
  `docs/incident-features.md`, dit verslag.

De bestaande assertions, `status.py`, alle 79 statustests, manifestversie,
dependencies, koppeldeduplicatie en zelftestcode blijven ongewijzigd.
Er is niets gecommit, gepusht, getagd of gepubliceerd.

## Definitieve afronding

De laatste volledige validatieroute is PASS; geen tests overgeslagen of assertions
verzwakt. Beide werkelijke HA-versies komen overeen met hun aangevraagde versie:

- HA 2026.10.4: `config/compatibility/2026.10.4/ddd325677a92461a87e8a24abb6578b0/compatibility-result.json`.
- HA 2026.11.1: `config/compatibility/2026.11.1/9dc58f45459f47ab8cca390eb8adad7b/compatibility-result.json`.

De notificatiebrowserflows zijn na de laatste backendcorrectie opnieuw geslaagd
(`browser-flows-final.log`). De bronselector is geopend en geannuleerd zonder
opslag; zelftestvoorwaarden zijn bekeken zonder aanvraag (`source-options.png`,
`selftest-conditions.png`). De overige screenshots staan in `screenshots/` en `after/`.

`scope.json` bevestigt beschermde bestanden, bestaande frontendassertions, lokale
links, pakketinhoud/hashes en afwezigheid van runtimebestanden in Git. De concrete
nieuwe tekst is ook gecontroleerd op adressen en geheimpatronen; geen live identifiers
of credentials toegevoegd. De wijzigingen hebben geen nieuwe hosted CI-uitkomst.

Eindstand (`final-state.json`, `screenshots/final-calm.png`): vijf geselecteerde bronnen
expliciet off, COMPLETE, alle 107 helpers off, nul tijdelijke groepen, meldingen,
koppeling, scripts, onderhoud en herinneringen uit. Alleen eigen tijdelijke
formulierconcepten verwijderd. Accounts en configuratie behouden. Het oudere
zelftestrecord blijft eerlijk `outcome_unknown`; er is geen lopende zelftest en
in deze opdracht is geen zelftest aangevraagd. Historische mockaanvragen blijven
als bewijs in het bestaande begrensde journaal; zij zijn geen actuele incidenten.
De simulator op 8131 blijft draaien; eigen technische testcontainers zijn opgeruimd.

Open blijft uitsluitend het verklaren van de oorspronkelijke live gsm-klacht en
het afzonderlijk vaststellen van echte telefoonbezorging. Dat vereist een nieuwe,
expliciet geautoriseerde praktijkcontrole; er is geen poging naar echte telefoons
gedaan. De simulatie bewijst geen fysieke rookdetectie, zelftest of alarmwerking.

## Onafhankelijke review en aanvullende correctie — 17 november 2026

De volledige notificatieketen is opnieuw in de browser uitgevoerd op de
gecontroleerde simulator 8131, met uitsluitend mobile_app_simulated_phone_a/b.
De geregistreerde uitvoer gaat naar de lokale incident_fixture, zonder telefoontransport.

Aanvullend gevonden: een vertraagd antwoord op Telefoons opnieuw controleren kon
invoer van na de klik overschrijven, een heropend formulier vervangen, een nieuwe
testbevestiging verwijderen of na reconnect verouderde data toepassen.
Vier permanente regressies faalden eerst (`independent-before.log`: 95 PASS, 4 FAIL).
Na correctie slagen alle 99 frontendtests. De verversing controleert nu formulier,
dialoogidentiteit, verbindingsgeneratie, aanvraagvolgorde en actieve bevestiging;
ze leest de onverzonden keuzes pas bij verwerking van het geldige antwoord.

Deze vier gevallen zijn ook in de echte browser doorlopen met een vertraagd
leesantwoord; nul uitvoeropdrachten. Bewijs: `independent-refresh.json`,
`independent-refresh.cjs`, `screenshots/independent-refresh-*.png` onder
`config/notification-review/`. De eerste browserproeven liepen vast op het scherm
voor bestaande concepten; het testscript is daarvoor aangepast. Dit was geen
extra productfout. De definitieve vier browserproeven zijn geslaagd.

De bestaande flows.cjs is na code-inspectie opnieuw uitgevoerd: kiezen/bewaren,
annuleren/concept, uitvoerloze preview, afzonderlijke bevestigde mocktest,
providerfout, eigen timeout, verdwenen dienst, vervallen bevestiging, rook in het
formulier, reconnect, verloren opslagantwoord en automatische incident/herstel-
aanvragen naar beide nepontvangers slagen. Geen automatische dubbele verzending.

Alle acht taal/thema/schermcombinaties zijn opnieuw gerenderd. Beelden van de vier
telefooninstellingenschermen, vier tabletbevestigingen met lange naam en de
mobiele verwerkt/fout/timeout/verbindingsverlies-resultaten zijn daadwerkelijk
bekeken. Desktop/focus/reflow en lege-lijstcontrole zijn ook opnieuw uitgevoerd.
De berichttaal blijft de HA-installatietaal; paneeltaal is apart getest via fixture.

Volledige nieuwe validatie: `config/validation/4231bf94dcb14288a741dbc325fd0b09/`:
555 backendtests, 99 frontendtests, Ruff, opmaak, hassfest, PowerShell, Compose,
HA 2026.10.4 en HA 2026.11.1, cleanup: allemaal PASS. Geen skips.
status.py, de 79 statustests, manifestversie en CI zijn ongewijzigd.
Twee nieuwe lokale pakketten bevatten 41 bestanden en dezelfde SHA-256:
`7c4e9a7439f1354b022003f8fcee636f15db7a438c690f6501e3aa49e7320859`.
Dit is de actuele aanvullende validatie; eerdere resultaten blijven historisch.

Eindstand opnieuw bevestigd: vijf bronnen off, 107 helpers off, nul groepen,
notificaties/onderhoud/herinneringen/koppeling/scripts uit, geen lopende zelftest.
De oorspronkelijke klacht over echte gsm-bezorging is hiermee niet bewezen
opgelost. Geen productie-installatie, echte telefoon of melder gebruikt. Niets
gecommit, gepusht of gepubliceerd.
