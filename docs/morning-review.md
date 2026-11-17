# Lokale ochtendversie — 17 november 2026

Referentie: `0.1.0-beta.9`, commit `eb2c61ea8621c05558b98421fcfb1f3751ebae4f`.
Dit verslag betreft de lokale, ongecommitte wijzigingen bovenop die referentie.
Alle browserbediening gebeurde op de afzonderlijke simulator op poort 8131,
Home Assistant **2026.11.1**. Geen echte apparaten, telefoons of productieaccounts.
Dit is een eigen simulatorcontrole, geen gebruikersonderzoek.

## In maximaal vijf minuten bekijken

Open <http://127.0.0.1:8131/alarmmesh>.

1. **Overzicht → Broninformatie** of **Melders**: de eerste melder is bereikbaar
   zonder eerst zes filters door te lopen. **Bekijk alarmroute** staat direct op de rij.
2. **Groepen → Groep maken**: naam en melders kiezen. Zoemers en scripts staan onder
   **Optioneel samen afgaan en acties**; een gewone groep vereist geen uitvoerinstellingen.
   Gebruik **Annuleren** als je niets wilt bewaren.
3. **Instellingen → Meldingen instellen**: ontvangers, moment en berichtpreview staan
   samen. Laat incidentmeldingen uit; een preview verstuurt niets.
4. **Overzicht → Onderhoud → melder**: huidige informatie, tijdelijke uitval,
   batterij-/zelftestbeperkingen en eventuele herinneringen bekijken.
5. **Melders → melder → Technische details → Bron herstellen**: vier voorbereidingsstappen,
   gekozen groepslidmaatschappen en afzonderlijke bevestiging. Sluit zonder overdracht.
   **Overzicht → Activiteit / Incidentdetails** toont het verloop en uitvoerbewijs.

## Vijf concrete knelpunten en de wijziging

Beginstand voor de vergelijkbare beelden: dezelfde vijf fictieve bronnen, allemaal
`off`, geen groepen of ruimte-toewijzingen, automatische uitvoer uit, telefoon 390×844.
Kliktellingen zijn navigatieklikken vanaf Overzicht, geen gemeten voltooiingstijden.

| Taak / oorspronkelijke waarneming | Wijziging en opnieuw waargenomen verschil |
| --- | --- |
| Rustige woning: uitgeklapte installatiechecklist nam de hoofdrol over | Checklist standaard dicht; status, directe tellingen en navigatie staan erboven. Eerste gebruik heeft één bronselectieknop. |
| Alarmroute zoeken: Melders → melder → alarmroute, drie klikken | Melders → Bekijk alarmroute, twee klikken. Vernieuwen blijft alleen-lezen; Escape keert terug. |
| Gewone groep maken: naam, leden, oorsprongen, koppeling en scripts in één lange stroom | Nog steeds twee klikken om het formulier te openen; alleen naam en leden zijn nodig. Een groep daadwerkelijk opgeslagen met één lid en uitvoer uit. Optionele bediening is ingeklapt; bewaren/annuleren blijven bereikbaar. |
| Gsm instellen: zoeken onder algemene hulp en checklist | Eerste kaart van Instellingen; twee navigatieklikken tot het formulier, preview standaard open. Mockontvanger opgeslagen terwijl globale verzending uit bleef. Annuleren en concept heropenen behouden de juiste afzonderlijke waarden. |
| Uitval onderzoeken: ontbrekende bron pas onder samenvattingen; technische gegevens domineerden melderdetail | Naam, ruimte en oorzaak staan in de bovenste statuskaart. Eén klik opent uitleg over tijdelijke uitval. Bronherstel is afzonderlijk en heeft vier stappen met behoud van revisie en bevestiging. |

## Werkelijk bekeken browserbewijs

Lokale beelden staan uitsluitend onder de genegeerde map
`config/morning-review/`. Vergelijkbare bestanden:
`before/overview.png` ↔ `after/overview.png`, `detectors.png`, `detector.png`,
`group-form.png`, `settings.png`, `notifications.png`, `maintenance.png`, `activity.png`.

De matrix bevat per combinatie zes werkelijk gerenderde beelden: rustig,
eerste gebruik, onvolledig, rook, rook met geopende instellingen, bronherstel.
Alle acht combinaties **NL/EN × licht/donker × 390×844/1024×768** zijn bekeken,
plus desktop 1440×900. `after/<taal>-<thema>-<phone|tablet>-sheet.jpg` zijn lokale
contactbladen; de gelijknamige afzonderlijke PNG's behouden de volledige resolutie.

- Rook, tijdelijke uitval en herstel kwamen uit echte simulatorhelpers. Er waren
  twee fictieve ruimtes en twee overlappende groepen, een lange naam en twee gelijke
  namen. Tijdelijke namen, ruimtes en groepen zijn na de matrix hersteld/verwijderd.
- Eerste gebruik was een browser-layoutfixture met lege bronnen; de opgeslagen
  HA-selectie bleef intact. De paneeltaal was een gecontroleerde `hass.language`-
  fixture die updates overleeft. Het omliggende HA-profiel bleef Nederlands.
  Een aanvankelijke taalfixture bleek terug te springen; die beelden zijn opnieuw
  gemaakt met een expliciete taalassertie.
- `after/zoom-200-reflow.png` en `after/zoom-200-form-reflow.png` controleren een 512×384 CSS-viewport, equivalent aan
  de beschikbare ruimte bij 200% zoom van 1024×768. Dit is een reflowcontrole,
  geen claim dat de native browserzoomknop is getest. De eerste CSS-zoomproef
  vergrootte ook de HA-zijbalk en is niet als geslaagde controle meegeteld.
- `flows.json` registreert daadwerkelijke UI-opslag van een fictieve groep en
  mockontvanger, annuleren, concept heropenen, tijdelijk onbereikbare bron,
  herstelvoorbereiding, reconnect, Enter/Escape en terugkerende focus.
  `offline-form.png` toont behoud van invoer en geblokkeerd bewaren zonder verbinding.
- Bronherstel is in de browser tot de bevestiging doorlopen, zonder overdracht.
  De daadwerkelijke overdracht, conflictcontrole en verloren opslagantwoord blijven
  gedekt door bestaande backend/frontendtests en compatibiliteitsscenario's.
- Er zijn nul `alarmmesh/test`-aanvragen verstuurd. Geen zoemer, zelftest, gsm-test
  of script aangevraagd. Zelftest en herinneringen blijven afzonderlijk van rookstatus.

## Validatie

De volledige route is `pwsh -NoProfile -File ./dev/validate.ps1`.
De eerste run (`b3961fc126b8414b8e869732e29f183f`) had 548 backendtests, Ruff,
hassfest en beide compatibiliteitsversies geslaagd, maar één frontendassertion
verwachtte de vervangen eerste-gebruiktekst. Alleen die tekstverwachting is aangepast;
de controles op lege/offline status zijn behouden. Het oorspronkelijke FAIL-rapport
blijft lokaal bewaard. Een volgende run (`42a9821186bf4a6595274079aaa9a767`) eindigde tijdens
installatie van dezelfde dependencies met een segmentation fault (exit 139), v??r
Ruff/pytest. Ook dat FAIL-bewijs blijft bewaard; de oorzaak is niet vastgesteld.
De ongewijzigde route slaagde vervolgens volledig. Geen dependency aangepast,
geen test uitgeschakeld.

Definitieve run: `config/validation/7404251af4a8438ba474e41a7ce1900d/`.

| Controle | Versie / resultaat | Lokaal bewijs in die map |
| --- | --- | --- |
| Backend | Linux Python 3.14 / HA 2026.10.4: **548 PASS** | `baseline.log`, `pytest.xml` |
| Frontend | Node 24.22.1: **89 PASS** | `frontend.log` |
| Ruff lint en format | **PASS** | `baseline.log` |
| Offici?le hassfest | **PASS** | `hassfest.log` |
| PowerShell-parse en foutafhandeling | **PASS** | `validation-result.json` |
| Compose-configuratie | **PASS** | `compose.log`, `validation-result.json` |
| HA-compatibiliteit | werkelijk **2026.10.4**, **PASS** | `compatibility-2026.10.4.json` |
| HA-compatibiliteit | werkelijk **2026.11.1**, **PASS** | `compatibility-2026.11.1.json` |
| Eigen tijdelijke middelen opgeruimd | **PASS** | `validation-result.json` |

De vijf nieuwe frontendtests bewaken rustige navigatie, dubbele groepssubmit,
rook tijdens instellingen zonder formulierverlies, dubbelzinnige meldernamen en
onvolledige informatie in de bovenste kaart. Drie bestaande UI-verwachtingen zijn
gericht aangepast: de nieuwe eerste-gebruiktekst, de paginatitel en de locatie van
de ingeklapte instelhulp. Alle overige assertions blijven behouden; de activiteitstest
krijgt extra assertions. De 79 statustests en alle backendtests zijn ongewijzigd.

Pakketbouw tweemaal uitgevoerd via `dev/release/package.py`: 41 integratiebestanden,
identieke SHA-256
`12811043d1e5f89251a540963e38b60b0d5ee7664ea56733e51bf4cc8d4f7e64`.
Lokale testpakketten: `config/release-packages/morning-final-a/` en `morning-final-b/`,
met `alarmmesh.zip` en `inventory.json`. Geen versie- of releasewijziging.
De productiebronnen en frontendtests komen byte voor byte overeen met de
gevalideerde bronkopie. `git diff --check`, lokale documentatielinks en controle op
beschermde bestanden/runtimegegevens zijn uitgevoerd; zie `config/morning-review/scope.json`.

## Grenzen en eindstand

Geen veiligheidsclaim: complete betekent bruikbare HA-waarden, geen heartbeat,
gezonde batterij of fysiek werkende melder. Een ontvangen opdracht is geen bewijs
van geluid, telefoonbezorging of geslaagde rookdetectie. Fysieke acceptatie blijft open.
Geen schema-/identiteits-/statusregels gewijzigd; de 79 statustests blijven ongewijzigd.
Geen nieuwe afhankelijkheden of publicatie. Alleen `panel.py` krijgt buiten de
frontend een gewijzigde assetcachecode.

De simulator blijft draaien. Eigen tijdelijke groepen en namen zijn opgeruimd,
bronhelpers en automatische uitvoer zijn uit. Gecontroleerd stoppen kan met:
`pwsh -NoProfile -File dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop`.
Dit raakt andere acceptatieomgevingen niet.


Aanvullende beelden: `after/selftest-review.png` (vernieuwde bevestiging, niet
uitgevoerd), `notification-preview.png`, `long-name.png`, `maintenance-evidence.png`
en `activity-final.png`. Onderhoud geeft geen gezond/geslaagd-label voor ontbrekende
informatie; activiteiten zijn zichtbaar v??r de ingeklapte filters. De eindstand in
`config/morning-review/final-state.json` vermeldt vijf bruikbare off-bronnen en 107
uitgeschakelde helpers. Een oudere zelftest met onbekende uitkomst blijft eerlijk
als historie bestaan; er loopt geen test. Er is geen nieuwe hosted CI-run of
fysieke acceptatie geclaimd.

## Onafhankelijke herstelreview — 17 november 2026

De ochtenddiff, het bestaande validatierapport en de acht bestaande visuele
contactbladen zijn beoordeeld. De herstelroute is aanvullend in de browser op
simulator 8131 uitgevoerd, inclusief daadwerkelijke opslag van tijdelijke groepen.

Aanpassing: Overzicht toont bij een ontbrekende, onbereikbare of van identiteit
gewijzigde bron direct **Bron herstellen**, met de meldernaam in het toegankelijke
knoplabel. Tijdelijke uitval houdt de uitleg dat vervangen niet nodig is.
Identiteitswijzigingen worden ook bij een bruikbare rookwaarde getoond.

Drie browserproeven met telkens drie tijdelijke groepen:

- Normaal: alleen gekozen groepen A en B bevatten daarna de vervanger; C blijft oud.
- Verbinding weg voordat de aanvraag verzonden is: A, B en C blijven oud.
- Verbinding weg na backendopslag maar voor ontvangst van het antwoord: A en B
  bevatten de vervanger; C blijft oud. De reconnectsamenvatting toont de werkelijke
  groepsleden. Geen automatische herhaling.

Per proef exact één bevestigde aanvraagpoging. Na volledig herladen is de
backendindeling opnieuw gecontroleerd. Geen bedieningsbevoegdheid of oorsprong
naar de vervanger overgedragen; koppeling en acties bleven uit. Beide fictieve
bronnen waren vooraf al geselecteerd in HA. Toevoegen/verwijderen van HA-bronnen
is geen onderdeel van deze aanvullende browserproef.

Nieuwe screenshots van de probleemkaart en beide reconnectuitkomsten zijn
werkelijk bekeken. Bewijs: `config/morning-review/recovery-review/results.json`,
`normal-problem.png`, `before-result.png`, `after-result.png` en `final.json`.
Het reproduceerbare lokale browserscript staat naast deze bestanden als `check.cjs`.
WebSocket-foutinjectie sluit de browsersocket vóór verzending of onderdrukt
berichten tot het opslagantwoord en sluit dan; de backendopslag blijft echt.

Frontend opnieuw uitgevoerd: **92 PASS**, inclusief drie nieuwe regressies voor
ontbrekend/onbereikbaar/gewijzigde identiteit en behoud van alleen-lezen openen.
`git diff --check` geslaagd. Backend/statuslogica is in deze correctie ongewijzigd;
548 backendtests en beide compatibiliteitsresultaten zijn bestaande ochtendbewijzen,
geen nieuw uitgevoerde volledige validatie. De oude pakketbestanden zijn niet
opnieuw opgebouwd en bevatten deze aanvullende knopwijziging nog niet.

Alle negen eigen tijdelijke groepen zijn verwijderd, de uitvalhelper is terug uit.
Geen echte apparaten of telefoons aangestuurd. Niets gecommit of gepubliceerd.

## Releasevalidatie beta.10

De volledige testreeks is opnieuw uitgevoerd op de releasebestanden inclusief de
herstelknop en manifestversie 0.1.0-beta.10. Run:
`config/validation/435d2b78017947b5979ea42629da2992/validation-result.json`.
548 backendtests en 92 frontendtests PASS; Ruff, format, hassfest, PowerShell,
Compose, beide HA-versies (2026.10.4 en 2026.11.1) en opruiming PASS.
Twee nieuwe pakketten bevatten elk 41 bestanden met identieke SHA-256:
`11fb6b42689fae539a0f77c521af3219623dd1c16d2fb0547791043b32e3e47e`.
Dit vervangt voor beta.10 de eerdere pakket- en testresultaten hierboven.
De eerdere vermeldingen over niet publiceren beschrijven de lokale reviewfase;
publicatie van beta.10 is daarna afzonderlijk door de eigenaar opgedragen.
