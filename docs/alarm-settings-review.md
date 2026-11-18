# Mijn alarminstellingen en zelf beoordeelde telefoontests

Lokale review van 18 november 2026, basis `c6fdfb32b6c60b9da5c5e6980a6967dcd02ef762`
(main, 0.1.0-beta.12) plus de wijzigingen in deze werkmap. Geen release of
nieuwe hosted CI-uitkomst. De werkmap was vooraf schoon.

## Wat is uitgebreid?

De bestaande instelhulp, alarmroute, telefoonprofielen, groepsacties, onderhoud,
activiteiten en bronherstel blijven hun eigen taak houden. **Mijn
alarminstellingen** bundelt de bestaande backendbeoordeling per geselecteerde
melder: groepen, gedeelde zoemers, globale telefoons, profielen en scriptacties.
Het overzicht verstuurt niets. Problemen leiden naar de bestaande melder-,
telefoon- of groepsinstelling; bewust uitgeschakeld is geen storing.

**Tests die je zelf hebt beoordeeld** voegt ontvangen en gehoord afzonderlijk
toe aan een concrete testaanvraag. Alleen beheerders kunnen registreren. Datum,
profiel en registratie-identiteit blijven gebonden aan die aanvraag. Een
profielwijziging maakt eerdere waarnemingen historisch; onbekende telefoonrechten
blijven onbekend. In deze review zijn alle waarnemingen expliciet simulaties.

De bestaande opslagbevestigingen tonen wat wordt toegevoegd, gewijzigd of
uitgeschakeld. Er is geen extra bevestiging voor bekijken. Een gewijzigde
serverrevisie maakt een oude toestemming ongeldig. Na een verloren antwoord
leest de interface terug zonder opnieuw te verzenden; latere edits gelden niet
als opgeslagen. Incidenten tonen de actuele rook apart van het werkelijk
vastgelegde verloop, nieuwste waarneming eerst. Ontbrekende historie wordt niet
aangevuld. Aanvraag, HA-verwerking, gebruikerswaarneming en fysieke werking
blijven verschillende begrippen.

## Correcties en grenzen

- Een gerichte test faalde doordat een geopende samenvatting na een externe
  revisiewijziging nog een opslagpoging toeliet. De backend weigerde deze al;
  ook de interface controleert nu de revisie vóór uitvoering.
- Screenshotinspectie vond `55.00000000000001%` bij een volume van 55%.
  De regressie faalde vóór normalisatie van de percentageweergave en het
  invoerveld. Opgeslagen telefoonprofielen en payloadsemantiek blijven behouden.
- Na een verloren opslagantwoord bleef in het bevestigingsvak ten onrechte
  "Aanvraag bezig" staan. De falende regressie en nieuwe browsercontrole tonen
  nu een onbekende uitkomst, gevolgd door het werkelijk teruggelezen resultaat;
  er blijft geen fictieve voortgang staan.
- Een oude aanvraag-ID kon na herladen opnieuw bij een andere telefoon worden
  gebruikt. De mockregressie faalde vóór de correctie; bewaarde aanvraag-ID's
  worden nu vóór uitvoer geweigerd. De eerdere waarneming blijft aan haar
  oorspronkelijke aanvraag/telefoon gebonden, zonder tweede opdracht.
- De begrensde lokale waarnemingsopslag bewaart maximaal 100 aanvragen met vijf
  waarnemingen per aanvraag. Het zichtbare venster is 30 dagen; opschonen wordt
  bij laden/schrijven opgeslagen, zonder extra timer. Beschadigde opslag levert
  geen actuele bevestiging op en blokkeert de bestaande meldingsroute niet.
- Er zijn geen nieuwe alarmacties, herhaalberichten, veiligheidsscores,
  telefoonknoppen voor stoppen of wijzigingen aan de rookregels.

## Bewijs

Bewijsbestanden en screenshots staan uitsluitend lokaal, genegeerd door Git,
onder `config/alarm-settings-review/`. De testomgeving is alleen
`http://127.0.0.1:8131/alarmmesh`, HA **2026.11.1**. Naam, labels, localhostpoort,
alleen-lezen mount en mockimplementatie zijn gecontroleerd. De afzonderlijke
bridge is geen firewall voor het LAN; er zijn geen productieconfiguraties,
apparaten of echte notificatiediensten gebruikt.

| Controle | Soort | Resultaat / bewijs |
|---|---|---|
| Nieuw alarmoverzicht, tijdelijke bronuitval, detailnavigatie en herstel | Interactieve simulator | PASS, `flows.json`, `problem-help.png` |
| Kritiek profiel, wijzigingssamenvatting en annuleren | Interactieve simulator | PASS, `flows.json`, `change-confirmation.png` |
| Mocktest, ontvangen/gehoord registreren zonder nieuwe uitvoer | Interactieve simulator | PASS, `flows.json`, `simulation-observation.png` |
| Profielwijziging bewaart eerdere waarneming als historie | Interactieve simulator | PASS, `flows.json`, `historical-profile.png` |
| Opslagantwoord verloren, reconnect en readback; concept heropenen | Echte serveropslag met browser-foutinjectie | PASS, `flows.json`, `lost-reply-readback.png` |
| Twee rookbronnen, rook zichtbaar in formulier, incidentverloop | Interactieve simulatiehelpers, uitvoer uit | PASS, `flows.json`, `smoke-in-form.png`, `multiple-sources-timeline.png` |
| NL/EN × licht/donker × 390×844/1024×768 | Browserbeelden daadwerkelijk bekeken | PASS, `matrix.json`, `screenshots/{nl,en}-{light,dark}-{phone,tablet}-*.png` |
| Desktop, toetsenbordfocus/Escape, lange gelijke namen, lege toestanden | Browser; lange/lege gegevens zijn fixtures | PASS, `desktop-overview.png`, `keyboard-focus.png`, `long-identical-names.png`, `empty-*.png` |
| Reflow | Browser op 512×384 CSS-pixels | PASS, `reflow-observation.png`; geen native browserzoomclaim |
| Echte herstart van alleen de simulatorcontainer | Technisch + aangemelde simulatorbrowser | PASS, `restart-result.json`: vier waargenomen simulatieaanvragen en instellingen behouden; nul mockopdrachten na herstart |
| Automatische tests, pakket en eindtoestand | Technisch | Zie de definitieve resultaten hieronder |

De taal is in de browserfixture gekozen; thema's via Home Assistants thema-event.
Op telefoon scrollen de dialogen verticaal; er is geen horizontale overloop.
Alleen lokale mockaanvragen zijn door de echte HA-servicelaag verwerkt. Een
simulatie-waarneming is geen bewijs van aflevering of geluid op een telefoon.

De reproduceerbare pakketbouw leverde twee identieke lokale test-ZIP's met 43
integratiebestanden op, onder
`config/release-packages/alarm-settings-verified-{a,b}/` (met inventaris).
SHA-256: `41de2901c139d469e7a074fa9b72e7dbe8fb591c15e4e84004297ba0d1439c40`.
Dit is geen gepubliceerde release of wijziging van de manifestversie.

### Definitieve technische resultaten

De volledige bestaande route `pwsh -NoProfile -File dev/validate.ps1` is na
de laatste codecorrectie opnieuw uitgevoerd en geslaagd. Het centrale bewijs
staat in `config/validation/7dfb9c830a17416ab7d022ed8ebcf479/`:

| Controle | Omgeving | Resultaat | Bewijs in die map |
|---|---|---|---|
| Volledige backend | Linux Python 3.14, HA 2026.10.4 | PASS, 602 tests | `baseline.log`, `pytest.xml` |
| Frontend | Node 24.22.1, bestaande Linkedom-tests | PASS, 117 tests | `frontend.log` |
| Ruff lint en format | Bestaande vastgezette dependencies | PASS | `baseline.log` |
| Officiële hassfest | Bestaande Docker-route | PASS | `hassfest.log` |
| PowerShell-parse, foutafhandelingstests, Compose | Bestaande lokale route | PASS | `validation-result.json`, `compose.log` |
| Compatibiliteit | Aangevraagd en werkelijk HA 2026.10.4 | PASS | `compatibility-2026.10.4.json` |
| Compatibiliteit | Aangevraagd en werkelijk HA 2026.11.1 | PASS | `compatibility-2026.11.1.json` |
| Opruimen eigen tijdelijke validatiemiddelen | Controle op naam/labels | PASS | `validation-result.json` |

De aanvankelijk falende regressies staan lokaal in `stale-before.log`,
`volume-before.log`, `progress-before.log` en `request-reuse-before.log`;
de laatste heeft ook een gerichte `request-reuse-after.log`. Een tussenronde
faalde terecht op Ruff-opmaak; die afwijking is gecorrigeerd, niet uitgezonderd.
De definitieve route hierboven bevat alle bestaande tests en nieuwe regressies.
`scope.json` legt de bytegelijke pakketbouw, behouden beschermde bestanden,
ongewijzigde bestaande assertions en lokale link-/privacycontrole vast.
`visual-observations.json` bevat de werkelijk bekeken beelden. Een DOM-test
telt hier niet als visuele waarneming. Er zijn geen resterende lokale blokkades.

De simulatorcontainer `alarmmesh-incident-ui-316a03fe45be` blijft draaien.
De eigen ontwikkel-/regressiecontainers zijn verwijderd; andere omgevingen zijn
ongemoeid gelaten. Later gecontroleerd stoppen kan vanuit de repo met
`pwsh -NoProfile -File dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop`.
De lokale configuratie wordt daarmee behouden.

## Gebruikersrapportage en open fysieke acceptatie

De gebruiker meldt dat een kritieke melding op zijn iPhone met de geteste
instellingen succesvol werkte. Dit is gebruikersrapportage, niet zelfstandig
geïnspecteerd en niet van toepassing op alle iPhones, Android, geluiden of
Focus/Niet storen. Het zet geen opgeslagen telefoon automatisch op getest.
Historische reviewverslagen blijven historische simulatorresultaten.

Echte rookovergangen, verbindingsuitval van fysieke melders, hoorbaarheid van
zoemers, andere telefoons en productieherstart zijn hier niet getest. Een
zelftest bewijst geen rookdetectie; complete broninformatie is geen heartbeat of
veiligheidsgarantie. Telefoonrechten kunnen buiten AlarmMesh veranderen.

## Rondleiding (maximaal vijf minuten)

1. Open de lokale simulator en kies op Overzicht **Mijn alarminstellingen**.
   Klap een melder open: groepen/zoemers zijn optioneel en de telefoons gelden
   globaal. Bekijken stuurt niets.
2. Ga via **Telefoonmeldingen instellen** naar het bestaande formulier. Bekijk
   gewoon/kritiek en de samenvatting; annuleer zonder iets te activeren.
3. Open bij Instellingen **Tests die je zelf hebt beoordeeld**. Bekijk de
   simulatieaanvraag: ontvangen en gehoord zijn losse antwoorden, met datum en
   het oude profiel. Een eerdere test is geen actuele garantie.
4. Bekijk Incidenten: **Nu** is actueel; **Waargenomen verloop** is historie met
   echte opgeslagen tijden. Technische correlatie staat uitgeklapt beschikbaar.
5. Sluit het formulier. Automatische uitvoer blijft uit en helpers blijven in
   rust. Voor deze rondleiding is geen nieuwe testaanvraag nodig.

## Contracten

Op 18 november 2026 geraadpleegd: officiële
[HA WebSocket API](https://contributors.home-assistant.io/frontend/extending/websocket-api/)
en [Companion critical notifications](https://companion.home-assistant.io/docs/notifications/critical-notifications/).
De bestaande vastgezette HA-API's en profielcontracten zijn behouden. Zie
[architectuur](architecture.md), [telefoonhandleiding](phone-alerts.md) en de
[bestaande validatieroute](development.md#complete-local-validation).

## Gewijzigde bestanden

- Backend: `custom_components/alarmmesh/__init__.py`,
  `custom_components/alarmmesh/activity.py`, `custom_components/alarmmesh/effects.py`,
  `custom_components/alarmmesh/panel.py`, `custom_components/alarmmesh/preview.py`
  en nieuw `custom_components/alarmmesh/phone_evidence.py`.
- Interface: `custom_components/alarmmesh/frontend/panel.js`,
  `custom_components/alarmmesh/frontend/panel.css`,
  `custom_components/alarmmesh/frontend/translations.js`.
- Tests/verpakking: nieuw `tests/test_alarm_settings_evidence.py`,
  `dev/frontend/panel.test.mjs`, `dev/release/package.py`.
- Documentatie: `README.md`, `CHANGELOG.md`, `docs/architecture.md`,
  `docs/phone-alerts.md`, `docs/panel.md`, dit `docs/alarm-settings-review.md`.

De oorspronkelijke backendtests en frontendassertions zijn behouden. `status.py`,
de 79 statustests, manifestversie, dependencies, CI en branding zijn ongewijzigd.
Er is niets gecommit, gepusht, getagd of gepubliceerd; de echte installatie is
niet benaderd. De simulator blijft draaien met automatische uitvoer uit,
helpers in rust en zonder lopende zelftest.
