# Alarmroute en bronherstel — lokale review

Basis: `5447aaa1421b462d2f63602798d6a3474643b621` (beta.8), schone main bij aanvang.
Geen commit, push, tag, publicatie of productie-installatie in deze ronde.

## Gebruikersstromen

- **Melders > melder > Bekijk alarmroute** toont alle betrokken groepen. Dezelfde
  zoemer komt eenmaal voor met redenen per groep; gsm-meldingen zijn globaal en
  scripts behouden hun volgorde per groep. Ook bereikbaar vanuit het groepsvoorbeeld.
- **Onderhoud > Bron herstellen** begeleidt afzonderlijke opslagstappen. Eerst
  betrokken uitvoer uitschakelen, dan de vervanger via bestaande HA-bronopties
  selecteren met behoud van de oude bron. Daarna gekozen lidmaatschappen beoordelen
  en atomair opslaan. Vervolgens oorsprongen, doelen, scripts en meldingen opnieuw
  beoordelen. Bronopties en historie worden door deze groepsstap niet aangepast.
- **Zelftest > Gegevens vernieuwen** leest een vers backendoverzicht, verwijdert
  oude toestemming en controleert het actuele doel. Het veroorzaakt geen aanvraag.

Een tijdelijk onbereikbare bron wordt apart beschreven en hoeft niet vervangen te
worden. Bij ontbrekende of gewijzigde identiteit toont onderhoud de ruimte en groepen.
Er wordt geen fysieke gezondheid afgeleid uit batterij, bereikbaarheid of zelftest.

## Grenzen en bewijs

De herstelroute maakt bewust geen gezamenlijke transactie van HA-opties en groepen.
De gebruiker ziet welke afzonderlijke stap is opgeslagen. Organisatorische overdracht
vereist uitgeschakelde betrokken uitvoer; de vervanger krijgt geen incidentoorsprong
of oude zoemerbinding. Andere groepen blijven behouden. Bij verloren bevestiging
moet opgeslagen toestand worden vernieuwd, niet een rollback worden aangenomen.
Actieve rook blijft zichtbaar; verwijderen, vervangen en sluiten zijn geen vrijgave.

De simulator is uitsluitend `http://127.0.0.1:8131/alarmmesh`, gecontroleerd met
`dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Status`. Het account blijft
behouden. Opstartaudit: 107 helpers uit, testresultaat idle, vijf geselecteerde
bronnen off, automatische uitvoer uit, geen echte Matter-controller.

## Werkelijk bekeken in de simulator ? 2026-11-16

HA **2026.11.1**, bovengenoemde basis plus deze lokale wijzigingen. De native
browserhost was niet beschikbaar (`native pipe unavailable`, fout 2). Daarom is
conform de opdracht lokaal Playwright/Chromium gebruikt met een afzonderlijk
profiel en de door de eigenaar aangemelde simulatiesessie. Geen tokens gelezen.
De echte HA-pagina en backend zijn gebruikt; schermgegevens zijn niet vervangen
met DOM-fixtures. Taal werd als paneelinvoer gezet, thema via HA's `settheme`.
Dit is een visuele paneelcontrole, geen test van de HA-profielinstellingen.

| Taal | Thema | Formaat | Bekeken | Resultaat |
| --- | --- | --- | --- | --- |
| NL | Licht | 390 ? 844 | Alarmroute en bronherstel | PASS |
| NL | Donker | 390 ? 844 | Alarmroute en bronherstel | PASS |
| NL | Licht | 1024 ? 768 | Alarmroute en bronherstel | PASS |
| NL | Donker | 1024 ? 768 | Alarmroute en bronherstel | PASS |
| EN | Licht | 390 ? 844 | Alarmroute en bronherstel | PASS |
| EN | Donker | 390 ? 844 | Alarmroute en bronherstel | PASS |
| EN | Licht | 1024 ? 768 | Alarmroute en bronherstel | PASS |
| EN | Donker | 1024 ? 768 | Alarmroute en bronherstel | PASS |

Alle zestien opnamen zijn daadwerkelijk bekeken. Lange bronnamen en groepsnamen
lopen door; geen ruimte wordt expliciet benoemd. Het gedeelde Zigbee-doel komt
??n keer voor, met de twee groepsredenen. De automatische uitvoer bleef uit.
Op telefoon zijn bevestiging en annuleren na scrollen bereikbaar. Een lege groep
wordt onbepaald/niet geconfigureerd getoond, niet groen als rookvrij bewezen.

[Schermmatrix](../config/route-review/visual-matrix.json) en
[screenshots](../config/route-review/screenshots/) blijven lokaal genegeerd.
Voorbeelden: [NL donker telefoon](../config/route-review/screenshots/nl-dark-phone-route.png),
[EN licht tablet](../config/route-review/screenshots/en-light-tablet-recovery.png).

Aanvullend werkelijk doorlopen:

- Alarmroute vanuit melderdetails, met overlappende uitgeschakelde groepen.
- Herstel van organisatorische lidmaatschappen van een Matter-simulatiebron naar
  een al geselecteerde Z-Wave JS-simulatiebron. Een wijziging via een tweede
  backendaanvraag maakt het open formulier verouderd: begrijpelijk conflict,
  keuze blijft behouden, geen automatische retry. Daarna opnieuw openen,
  expliciet bevestigen, opslaan en heropenen. Geen oorsprong of doelbevoegdheid
  overgedragen. Dit bewijst de groepsstap; HA-bronopties blijven een aparte stap.
- Zelftestvenster vernieuwen: naam en gevolgtekst ??n keer, toestemming weer uit,
  geen zelftestaanvraag. Een eerder onbekend testresultaat wordt geen succes.
- Rookhelper tijdens herstel aan/uit: actuele rook zichtbaar binnen de dialoog;
  invoer blijft staan. Alleen de lokale simulatiehelper is bediend.
- Werkelijke websocketonderbreking met offline browser: melding over verbroken
  verbinding, opslaan uit, keuzes behouden en terugkeer na reconnect. Er is geen
  automatische aanvraag gedaan. Verloren bevestiging tijdens een daadwerkelijk
  lopende schijfopslag is niet afzonderlijk in de browser ge?njecteerd; opslagfout,
  dubbele aanvraag en herladen zijn backendregressies.

[Herstelstroom](../config/route-review/ui-flow-result.json),
[rook en reconnect](../config/route-review/live-smoke-reconnect.json),
[conflict](../config/route-review/screenshots/recovery-conflict.png),
[opgeslagen stap](../config/route-review/screenshots/recovery-saved.png),
[rook zichtbaar](../config/route-review/screenshots/recovery-live-smoke.png) en
[zelftest vernieuwd](../config/route-review/screenshots/selftest-refreshed-no-request.png).

## Gevonden en gecorrigeerd

1. Rook op de onderliggende pagina kon achter het herstelvenster verdwijnen.
   Een blijvende regressie faalde eerst; nu staat er een actuele, vaste rookmelding
   in het venster, zonder de keuzes opnieuw te tekenen.
2. Herstel was nog niet opgenomen in het bestaande offline-formuliergedrag.
   Een echte disconnect sloot het venster. De regressie faalde eerst; herstel
   behoudt nu de invoer, blokkeert opslaan offline en slaat niet vanzelf op.

[Voor/na rook](../config/route-review/smoke-regression-before.log) en
[voor/na reconnect](../config/route-review/reconnect-before.log) bewaren de fouten;
[82 geslaagde frontendtests](../config/route-review/reconnect-after.log) bewijzen
het herstel. Bestaande assertions zijn behouden. Een eerdere volledige run had
??n Docker-geheugenfout (`Cannot allocate memory` bij directory-lezen); die run
blijft FAIL in zijn eigen rapport en wordt niet als productfout of PASS herlabeld.

## Technische eindcontrole

De definitieve route is vastgelegd in
[validatiebewijs](../config/validation/9f87619397864217809de5198f7dbe73/).
548 backendtests op Linux Python 3.14 / HA 2026.10.4 en 82 frontendtests slagen.
Ruff-lint, Ruff-format, hassfest, PowerShell-parse en Compose-controle slagen.
Beide compatibiliteitsruns slagen: [2026.10.4](../config/validation/9f87619397864217809de5198f7dbe73/compatibility-2026.10.4.json) en [2026.11.1](../config/validation/9f87619397864217809de5198f7dbe73/compatibility-2026.11.1.json).
De twee compatibiliteitsrapporten bevatten de werkelijk geladen HA-versie en
29 runtime- plus 22 providerchecks per versie; uitsluitend ge?soleerde simulatie.
De oorspronkelijke 26 backendtestbestanden, waaronder de 79 statustests, zijn
byte-inhoudelijk behouden (afgezien van genormaliseerde regeleinden bij vergelijking).
 De verpakking bevat 41 bestanden inclusief `recovery.py`;
twee onafhankelijke builds leveren identieke SHA-256:
`59a9ad74e579424b4819150c95dd6ae8ade3df70c9903193c47389f1740bdf5e`.
[Pakketinventaris](../config/release-packages/route-review-verified-a/inventory.json)
en [scopecontrole](../config/route-review/scope-audit.json).

Geen fysieke werking onderzocht. Een batterijwaarde, HA-beschikbaarheid,
zelftestaanvraag of complete status bewijst geen rookdetectie of fysieke gezondheid.
Geen nieuwe hosted CI-run en geen publicatie. De simulator blijft beschikbaar;
eigen reviewgroepen zijn verwijderd en de rookhelpers zijn weer uit.

## Gewijzigde bestanden

- Backend: `preview.py`, `recovery.py` en `panel.py` onder `custom_components/alarmmesh/`.
- Interface: `frontend/panel.js`, `frontend/panel.css`, `frontend/translations.js`.
- Regressies: `tests/test_route_recovery.py` en `dev/frontend/panel.test.mjs`.
- Verpakking: `dev/release/package.py` (allowlist voor de nieuwe module).
- Documentatie: `CHANGELOG.md`, `docs/panel.md`, `docs/architecture.md` en dit verslag.

## Reproduceren

```powershell
pwsh -NoProfile -File ./dev/validate.ps1
python dev/release/package.py --output config/release-packages/route-review-a
python dev/release/package.py --output config/release-packages/route-review-b
```

De pakketallowlist bevat `recovery.py`. Manifest, dependencies, status.py en de
79 oorspronkelijke statustests blijven ongewijzigd. Alleen eigen tijdelijke
reviewbestanden staan onder genegeerde config-mappen.

Gecontroleerd stoppen met behoud van account/configuratie:

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```
