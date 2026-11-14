# Functionele afronding — 2026-11-14

Basis: `b2f3d719a86cffb0a533fa5650dce624fd2275f2` plus behouden lokale wijzigingen.
Dit pakket staat lokaal voor review; geen nieuwe commit, publicatie of installatie
op een echt systeem. Manifest, minimumversie, dependencies, statusregels en de
aanvraaggebonden zelftestcorrectie zijn ongewijzigd.

## Afgewerkt

- Gewijzigde of niet meer geselecteerde zoemertoewijzingen blijven bewaard bij een
  gewone groepsbewerking; vervangen of verwijderen vereist een bewuste keuze.
  Namen/ruimtes en providerbeperkingen staan bij de keuze; IDs achter details.
- Gewijzigde/ontbrekende scripts zijn herkenbaar, blijven bewaard en kunnen niet
  als het oude script worden getest. Scripts zijn omhoog/omlaag te ordenen.
- Bevestiging vergrendelt de exacte configuratie. Annuleren herstelt de bediening
  zonder schrijven; offline bevestigen kan niet en onverzonden invoer blijft staan.
- Zelftestbevestigingen volgen uitsluitend hun eigen aanvraag-ID. Incidentdetails
  tonen ook groepen zonder meldingen/scripts en onderscheid tussen actuele rook
  en bronnen waarvoor expliciet rookvrij herstel nog ontbreekt.
- Voorbeelden behouden berichtregels, nieuwe knoppen hebben gerichte labels en
  de standaard dialoogwaarschuwing op wit heeft berekend contrast 6,51:1 in plaats
  van 3,56:1. Dit is geen visuele controle van alle HA-thema's.

Zeven concrete formulier-/incidentregressies faalden eerst en slagen na herstel.
Bestaande autorisatie, revisies, identiteitscontrole, rookprioriteit, ontdubbeling,
Bosch-beveiliging en beperkte stopbevoegdheid blijven leidend. Geen algemene
stop/mute, nieuwe providerondersteuning of automatische retries toegevoegd.

## Pakketinstallatie en update reproduceren

```powershell
pwsh -NoProfile -File ./dev/validate.ps1
pwsh -NoProfile -File ./dev/release/check-update.ps1 -HaVersion 2026.10.4
pwsh -NoProfile -File ./dev/release/check-update.ps1 -HaVersion 2026.11.1
```

De bestaande runner gebruikt standaard de exact gecontroleerde gepubliceerde
beta.3-revisie. `-PreviousRevision 0e7ba38` behoudt de eerdere foundationroute.
Nieuwe, niet gepubliceerde wijzigingen komen uitsluitend uit Git-zichtbare bestanden.
Containers gebruiken eigen interne netwerken, geen webpoort, radio, hardware,
accounts of Docker-socket; installatie- en fixturemounts zijn alleen-lezen.

De controle bewaart bij beta.3→werkboom bronnen, groepen, namen, overzichtsidentiteit
en expliciete koppelkeuzes. Nieuwe functies blijven eerst uit. Daarna worden in de
test expliciet mockontvangers en twee event-only scripts ingesteld; hun volgorde
en keuzes blijven na een echte nieuwe HA-processtart behouden. Reload herhaalt
geen meldingen/scripts. Verwijderen/opnieuw toevoegen en beschadigde opslag worden
via HA-API's gecontroleerd, inclusief herstel zonder onbedoelde uitvoer.

Dit is een bestandsupdate uit lokale ZIPs, geen nieuwe Marktplaats-/HACS-acceptatie.
Herstel gebruikt een kopie van normaal gestopte testbestanden, geen test van de
HA-back-upfunctie. Voor echte rollback blijft een passende pre-updateback-up nodig.
De catalogus blijft onderscheid maken tussen detectie, activering, beperkte stop
en alleen-lezen testfeedback; de daadwerkelijke zelftestknop vereist de aparte
[model/providervoorwaarden](incident-features.md). Geen fysieke werking bevestigd.

## Visuele acceptatie

Vervolg op 2026-11-15: de browser was tijdens de onafhankelijke review wel beschikbaar.
De concrete groeps-/incident-/zelftestscenario’s en twee UI-correcties staan in
[de visuele hercontrole](visual-flow-review.md). Onderstaande oorspronkelijke
blokkademelding blijft historisch bewijs van de eerdere ontwikkelronde.

De bestaande omgeving op **http://127.0.0.1:8131/alarmmesh** blijft beschikbaar.
Account en selectie worden behouden. Zowel `cua.getState` als `sky.list_apps` zijn
geprobeerd: de browserhost ontbreekt en de native pipe geeft `os error 2`.
Er zijn geen browserhandelingen of nieuwe screenshots uitgevoerd.

| Taal | Thema | 390×844 | 1024×768 |
| --- | --- | --- | --- |
| Nederlands | Licht | NIET UITGEVOERD | NIET UITGEVOERD |
| Nederlands | Donker | NIET UITGEVOERD | NIET UITGEVOERD |
| Engels | Licht | NIET UITGEVOERD | NIET UITGEVOERD |
| Engels | Donker | NIET UITGEVOERD | NIET UITGEVOERD |

Open blijven in alle acht combinaties: kernschermen, groepen/annuleren/verwijderen,
ontvangers/preview/mocktest, scriptvolgorde/event-only test, incident/uitval/herstel,
zelftest/resultaat/timeout/afzonderlijke rook, lange namen/scroll/focus en offline
formulieren/conflicten/herstel. DOM-tests vervangen geen zichtbare waarneming.
De eindstand van UI-helpers kon niet opnieuw visueel worden bevestigd. Er zijn
geen nieuwe automatische UI-functies ingeschakeld; andere omgevingen blijven intact.

## Actuele resultaten

Bewijsmap **F**: `config/finish-review/6da01972f7364a5189ac9a1547c57d85/`.
Volledige route **V**: `config/validation/b147f35fcd654e55bb11471ff82c9d12/`.

| Controle | Werkelijk resultaat | Bewijs |
| --- | --- | --- |
| Linux Python 3.14.10 / HA 2026.10.4 | **429 backendtests PASS**, geen skips; alle 428 eerdere gevallen en 79 statusgevallen behouden | V `pytest.xml`, `baseline.log` |
| Node 24.22.1 | **42 frontendtests PASS**, alle 33 eerdere assertions behouden | V `frontend.log` |
| Oorspronkelijke onafhankelijke P1-reproductie | **1 PASS**, ongewijzigde aangeleverde reproductie | F `original-review.log` |
| Gerichte pakket/incident/zelftestset | **64 PASS** | F `targeted.log` |
| Ruff, format, officieel hassfest, PowerShell/foutinjecties, Compose | **PASS** | V `validation-result.json`; finale updatedriver ook afzonderlijk gelint/geparseerd en op beide images uitgevoerd |
| HA 2026.10.4 en 2026.11.1 | Elk **24 runtime + 16 driver PASS**, versie en cleanup gecontroleerd | V `compatibility-<versie>.json` |
| Installatie/update/herstart/opslag/herstel op 2026.10.4 | **PASS**, definitief pakket met afzonderlijke faseverslagen | `config/update-checks/2026.10.4/109bdd5dbf4a4fb699e853668c712ab0/update-result.json` |
| Idem op 2026.11.1 | **PASS** | `config/update-checks/2026.11.1/5cb746d94917427da6cdb5cc01236738/update-result.json` |
| Reproduceerbare verpakking | **PASS**, 32 bestanden, twee bytegelijke builds, gelijk aan gevalideerde productbron | `config/release-packages/finish-6da01972-complete-one/inventory.json` |
| Scope, privacy en relatieve links | F `scope-result.json` / `documentation-result.json` | Gerichte audit, geen algemene secretsgarantie |

Pakket-SHA-256: `ab005a2c2f18ec82423816a2ef7903d55f19f6907ad5a16df3a30f4ec2b2b658`.
UI-matrix: `config/incident-ui/316a03fe45be4de3b789e1490bb9bed1/finish-6da01972f736/ui-result.json`.
Oorspronkelijke falende formulier-/incidenttests: F `frontend-before.log` en
`incident-groups-before.log`; hercontrole in V. Een eerste updaterun faalde door
onjuist gebruik van `async_setup` vanuit SETUP_ERROR in de testdriver; die gebruikt
nu de ondersteunde reload. Faseverslagen heten nu `phase-<fase>-result.json`, zodat
het hoofdverslag `update-result.json` het updatefasebewijs niet overschrijft.
Geen HA-rechten of bestaande assertions zijn gewijzigd. Mislukte runs blijven apart
bewaard en zijn niet als PASS aangeduid.

Voorgestelde volgende testrelease: **0.1.0-beta.4**, na de open visuele acceptatie
voor een afzonderlijk goedgekeurde publicatie. [Voorstel en besluiten](release-readiness.md).
Alle fysieke acceptatie blijft open. Er is geen hosted-CI-run voor deze lokale diff;
alle bovenstaande resultaten zijn lokaal. Niets gecommit, gepusht, getagd of gepubliceerd.
