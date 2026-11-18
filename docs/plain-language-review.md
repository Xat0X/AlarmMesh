# Begrijpelijke instellingen: lokale review

18 november 2026. Basis `7061cd0c17122e53c717708080fb78557551c9fa`, met
behouden lokale kritieke telefoonprofielen en deze aanvullende wijzigingen.
Manifest blijft `0.1.0-beta.11`. Dit is een ontwikkelaarsreview met simulatie,
geen gebruikersonderzoek of bewijs van fysieke rookdetectie, geluid of aflevering.

## Audit en uitgevoerde verbeteringen

| Oorspronkelijk obstakel | Verbetering en plaats | Controle |
|---|---|---|
| Instellingen waren vooral een lange telefoonlijst | Vijf herkenbare taken met huidige keuze, ontvangers en technische hulp ingeklapt | Werkelijke instellingenpagina in acht schermvarianten |
| Groepsopties kwamen tegelijk in beeld | Begin met naam en melders; aparte onderdelen voor starters, samen afgaan en scripts; actieve keuzes blijven samengevat | Groep maken en aanpassen in simulator; bestaande bevestigingstests |
| Telefoonroute herhaalde informatie en onduidelijke testknoppen | Korte stappen, platformgebonden geluid/hulp, verwijderen ingeklapt; voorbereiden en werkelijk aanvragen hebben verschillende knoppen | Stil opslaan, twee mockprofielen, bevestiging, fout en onbekende uitkomst |
| Tijdelijke uitval verwees naar vervangen | Verbinding controleren opent melderinformatie; vervangen blijft een afzonderlijk proces | Echte gesimuleerde uitval, ontbrekende bediening en ontbrekende-melderweergave |
| Veel vaktaal in details en herstel | Gewone NL/EN-teksten; technische gegevens achter uitleg; duidelijke gevolgen bij bevestigingen | Effectieve vertalingen nagekeken, screenshots en bestaande fout-/autorisatietests |
| Historische incidenten konden als huidige toestand worden gelezen | Actuele toestand eerst; eerdere bronnen en herstelmoment apart | Incident- en activiteitenscherm bekeken; statusberekening ongewijzigd |
| Lange waarschuwingen overheersten onderhoud | Korte samenvatting, uitgebreide grenzen openklapbaar; onbekende gegevens blijven onbekend | Onderhoudsscherm bekeken; geen fysieke test of veiligheidsbewijs geclaimd |
| Na gecontroleerd opslaan kon de oude knop weer actief worden | Formulier blijft na readback geblokkeerd, ook na reconnect of annuleren van de bevestiging | Twee regressies eerst rood, daarna groen |

De laatste twee gedragsfouten zaten in het opnieuw vrijgeven van knoppen na een
verbindingsherstel of gesloten bevestiging. De bestaande leescontrole had de
oude formulierkeuze al als opgeslagen vastgesteld. Een afzonderlijke markering
houdt die opslagknop geblokkeerd totdat het formulier opnieuw wordt geopend.
Servervalidatie, aanvraagidentiteit, standaard-uitgedrag en profielbinding blijven
behouden. Ook een onderbroken aanvraag wordt niet automatisch herhaald.

## Benamingen

| Nederlands | Engels | Betekenis |
|---|---|---|
| Melders kiezen | Choose detectors | Bestaande HA-rookmelders selecteren |
| Samen afgaan | Sound together | Expliciet toegestane zoemerbediening |
| Telefoonmeldingen | Phone alerts | Ontvangers en hun afzonderlijke instellingen |
| Wat gebeurt er bij rook? | What happens during smoke? | Alleen bekijken welke acties zijn ingesteld |
| Testmelding voorbereiden / versturen | Prepare / send test notification | Voorbeeld tegenover afzonderlijk bevestigde aanvraag |
| Zelftest aanvragen | Request self-test | Aanvraag; geen belofte van een geslaagd apparaatresultaat |
| Verbinding controleren / Melder vervangen | Check connection / Replace detector | Tijdelijke uitval tegenover een andere melder toewijzen |
| Controleherinneringen | Check reminders | Herinneren, geen automatische zelftest |

De telefoonhulp is opnieuw vergeleken met de officiële
[kritieke meldingen](https://companion.home-assistant.io/docs/notifications/critical-notifications/)
en [geluidsinstellingen](https://companion.home-assistant.io/docs/notifications/notification-sounds/)
op 18 november 2026. iPhone-geluid/volume en Android-kanaalinstellingen blijven
verschillend; toestemming en hoorbaarheid zijn niet automatisch vastgesteld.

## Werkelijk gecontroleerd

De bestaande simulator `alarmmesh-incident-ui-316a03fe45be`, HA **2026.11.1**,
is vooraf gecontroleerd op labels, lokale binding `127.0.0.1:8131`, mounts en
mocktransporten. Alleen gesimuleerde telefoondiensten en helpers zijn gebruikt.
De bestaande testaccountgegevens zijn niet gelezen of in bewijs opgenomen.

| Controle | Uitkomst en bewijs onder genegeerd `config/plain-language-review/` |
|---|---|
| NL/EN × licht/donker × 390×844/1024×768 | PASS; alle acht daadwerkelijk bekeken, telkens instellingen en iPhone/Android; `matrix.json`, `screenshots/matrix-*.png` |
| Desktop 1440×900, lange namen, lege telefoons, eerste gebruik | PASS; screenshots `desktop-settings`, `long-name`, `empty-phones`, `first-use` |
| Groep zonder acties, bewerken, annuleren, concept, toetsenbord | PASS; `usability.json`, `final-ui.json`; Enter/Escape, focus terug, geen uitvoer |
| Kritieke keuzes opslaan zonder verzending, platformhulp, specifieke testaanvragen | PASS met mocktransport; `flows.json`; iPhone-geluid/75%, Android alarm_stream/high/ttl=0 |
| Fout, timeout, gewijzigde dienst, rook in formulier, reconnect | PASS; `beta11-regression-flows.json`; onbekend blijft onbekend, geen automatische retry |
| Verloren opslagantwoord controleren | PASS; echte serversave met verloren antwoord als browserfixture; alleen teruglezen, `save-verified.json` |
| Ontbrekende bediening en melderherstel | PASS voor presentatie/voorbereiding; `final-ui.json`. Bediening via echte simulatorhelper verwijderd; ontbrekende rookmelder alleen browserweergavefixture, geen nieuwe HA-verwijder-/migratieacceptatie |
| Vergrote/reflow-weergave | PASS voor 512×384 CSS-viewport, geen horizontale dialoogscroll; geen native browserzoom- of screenreadertest |
| Ruststand | `final-state.json`: vijf bronnen off, 107 helpers off, nul groepen, automatische meldingen/onderhoud/herinneringen uit; geen actieve zelftest |

De taal wordt in de browser aan het paneel aangeboden; de omringende HA-sessie
blijft Nederlands. Thema's gebruiken de echte HA-themawisseling. Lege en lange
namen zijn uitsluitend browserfixtures, niet een verwijderde echte configuratie.
Screenshots zijn werkelijk bekeken, niet afgeleid uit DOM-tests. Een onbekende
historische zelftest blijft onbekend; hij wordt niet gewist of als geslaagd getoond.

Voor/na-beelden staan lokaal in `before-images/` en `screenshots/`, met vergelijkingen
`comparison-settings.png`, `comparison-phone.png` en `comparison-maintenance.png`.
Ze blijven buiten Git. Sidebar/accountinformatie is afgeschermd.

## Tests en wijzigingsgrens

De volledige bestaande route is `pwsh -NoProfile -File ./dev/validate.ps1`.
De eerste volledige run `e0c338480b6845a38ec9e14d0e80e824` slaagde met
**586 backendtests** (Linux Python 3.14, HA 2026.10.4), **105 frontendtests**
(Node 24.22.1), Ruff, format, hassfest, PowerShell, Compose en compatibiliteit op
exact **2026.10.4** en **2026.11.1**. De definitieve run na de laatste kleine
schermtekstcorrecties is **`165096efea874499ad6a01cb63a472c5`**, eveneens volledig
PASS: 586 backendtests, 105 frontendtests en alle genoemde controles. Het rapport
staat lokaal in `config/validation/165096efea874499ad6a01cb63a472c5/validation-result.json`.
De bijbehorende compatibiliteitsruns zijn `18fd42b1593c411b9cf31cf9df8f12ed`
(2026.10.4) en `78a88f564bbf45b4b626999af9e026f3` (2026.11.1). Dit is geen
nieuwe hosted CI-run. `scope.json` en `visual-observations.json` leggen de
bestandsgrens en daadwerkelijke screenshotinspectie vast. Relatieve links,
privacycontrole en `git diff --check` slagen.

Rode regressiebewijzen: `reconnect-before.log` en `confirm-before.log`.
De 102 bestaande frontendtests blijven bestaan; drie gerichte tests zijn toegevoegd.
Tekstassertions zijn aangepast aan de bedoelde labels. De uitvaltest controleert nu
expliciet dat tijdelijke uitval informatie opent zonder de vervangings-API aan te
roepen, terwijl vervangen toegankelijk blijft. Er zijn geen assertions verwijderd
om een defect te verbergen. Backendtestaantal blijft gelijk.

Deze opdracht wijzigt exact:

- `custom_components/alarmmesh/frontend/panel.js`, `panel.css`, `translations.js`.
- `custom_components/alarmmesh/panel.py` (uitsluitend assetquery in deze opdracht).
- `custom_components/alarmmesh/strings.json`, `translations/en.json`, `translations/nl.json`.
- `dev/frontend/panel.test.mjs`, `tests/test_scope_texts.py` (bestaande tekstclaims).
- `README.md`, `CHANGELOG.md`, `docs/panel.md`, `docs/phone-alerts.md`, dit document.

De eerdere lokale wijzigingen zijn apart bewaard in `before/` en `before.diff`.
`status.py`, de 79 statustests, kritieke-profielbackend, afhankelijkheden, branding,
manifestversie en CI zijn in deze opdracht ongewijzigd.

## Rondleiding in maximaal vijf minuten

1. **0:00–0:45 — Overzicht:** lees de actuele rookstatus. Open een probleem voor
   de betreffende melder; geen rook gemeld is geen veiligheidsgarantie.
2. **0:45–1:30 — Instellingen:** bekijk de vijf taken en hun huidige waarden.
   Bij **Melders** zie je namen/ruimtes; **Wat gebeurt er bij rook?** verstuurt niets.
3. **1:30–2:15 — Groepen:** geef een groep een naam en kies melders. Bekijk de
   afzonderlijke optionele acties; laat ze voor deze rondleiding uit.
4. **2:15–3:30 — Telefoonmeldingen:** kies een mocktelefoon, bekijk platform,
   geluid en hulp. Opslaan verstuurt niets. Voorbereiden toont alleen een voorbeeld;
   versturen vereist aparte bevestiging. Een aanvraag bewijst geen hoorbaar geluid.
5. **3:30–4:30 — Onderhoud en Incidenten:** bekijk gemelde informatie, ontbrekende
   gegevens en actuele toestand tegenover eerdere aanvragen. Een batterijwaarde
   of afgehandelde herinnering bewijst geen goede rookdetectie.
6. **4:30–5:00 — Sluiten:** annuleer een wijziging en heropen het concept. Controleer
   dat automatische uitvoer uit blijft. De simulator blijft lokaal beschikbaar.

Geen echte telefoonrechten, geluid, fysieke rooktest of productie-installatie is
gecontroleerd of bediend. Er is niets gecommit, gepusht of gepubliceerd.
