# Visuele acceptatie van groepsacties, incidenten en zelftests

Datum: 15 november 2026. Alleen de eigendomsgecontroleerde simulator op `http://127.0.0.1:8131/alarmmesh`, HA 2026.11.1, is gebruikt. Geen echte melders, radio, telefoons of externe scripts.

## Werkelijk doorlopen scenario's

| Onderdeel | Waargenomen resultaat |
| --- | --- |
| Groep maken | Twee expliciete simulatieleden A/B geselecteerd, beide als incidentbron, alleen mockzoemer A als doel. Aqara-voorwaarde en niet-beschikbare doelkeuze duidelijk zichtbaar. |
| Scriptacties | Twee verschillende event-only scripts voor begin, één voor bevestigd herstel. Omhoog/omlaag wijzigen zichtbaar correct; opgeslagen volgorde in de incidentdetails behouden. |
| Testbevestiging | Zonder toestemming wordt de test geweigerd. Daarna bevestigen geeft één geaccepteerde mockaanvraag; onderliggende betrokken invoer blijft vergrendeld tot annuleren. |
| Configuratiebevestiging | Exacte bronnen, B→A-doel en scripts getoond. Terug behoudt alle invoer; pas expliciet bevestigen bewaart de configuratie. |
| Rookincident | B meldt rook: gekozen mockzoemer A en beide beginscripts aangevraagd. Status noemt geaccepteerde opdrachten, geen hoorbaar geluid. |
| Overlappende bron | A meldt daarna ook rook: beide bronnen zichtbaar; beginscripts worden niet opnieuw uitgevoerd. |
| Bronuitval | B onbereikbaar tijdens incident: onbekende bron blijft als nog niet expliciet vrijgegeven benoemd. Rook van A blijft zichtbaar. |
| Geen vals herstel | A en B rookhelpers uit, B nog onbereikbaar: herstelactie blijft uit. Pas B weer expliciet off geeft herstelactie en de toegestane stopaanvraag. |
| Meldingsfoutisolatie | Beide mockontvangers ingesteld; B-foutinjectie aan. A geaccepteerd, B mislukt; groepsscripts en zoemer lopen door. Geen automatische herhaling bij alleen foutinjectie uitzetten. |
| Zelftestactiviteit | Mock-Heiman zelftest toont actief, zonder zelfstandig een rookincident te starten. |
| Rook tijdens zelftest | Afzonderlijke rookmelding van B start zichtbaar het incident terwijl zelfteststatus apart blijft. |
| Geen resultaat | Eindigende activiteitsvlag zonder expliciet resultaat geeft onbekend, geen succes. |
| Echte timeout | Tweede Heiman-aanvraag werkelijk twee minuten laten verlopen: resultaat onbekend, ook wanneer de testvlag nog aan staat. |
| Expliciet succes | Tijdelijk geselecteerde HALO-fixture Q: nieuwe aanvraag wordt eerst actief, daarna expliciete success-feedback; alleen die aanvraag wordt als expliciet geslaagd getoond. |
| Expliciete mislukking | Volgende Q-aanvraag neemt oud succes niet over; nieuwe running→fail_ion-feedback geeft expliciet mislukt. |
| Conflicterende test | Bij actieve rook wordt een bevestigde zelftestaanvraag geweigerd met de concrete conflictuitleg. |
| Offline formulier | Onbewaarde groepsnaam blijft zichtbaar bij stoppen van de simulator; bewaren wordt geblokkeerd en oude data niet als actueel gepresenteerd. |
| Herverbinding | Stop/start met dezelfde codeversie: hetzelfde concept blijft behouden en bewaren wordt na actuele gegevens weer beschikbaar. Concept daarna geannuleerd. |
| Groep verwijderen | Eerst annuleren: groep blijft behouden. Vervolgens afzonderlijk bevestigen: uitsluitend de tijdelijke reviewgroep verwijderd, bronnen blijven bestaan. |

De interactieve functionele scenario's zijn in Nederlands/donker uitgevoerd. De incidentweergave is daarnaast op telefoon 390×844 en tablet 1024×768 bekeken. De eerdere acht-combinatiecontrole van het meldingsformulier is apart vastgelegd in `afwerking-review-2026-11-15.md` in de gedeelde documentwerkruimte. Deze ronde claimt niet dat ieder interactief scenario achtmaal opnieuw is uitgevoerd.

## Gevonden en hersteld

1. Na een geweigerde onbevestigde aanvraag bleef de bevestigingswaarschuwing staan naast een later succesbericht. Nu wordt de oude waarschuwing gewist zodra een geldige aanvraag begint. Nieuwe permanente frontendregressie faalt vóór de correctie en slaagt erna. Na volledig vernieuwen van de browser is ook zichtbaar gecontroleerd dat de fouttekst leeg wordt.
2. Lange incidentregels konden het statusicoon op een losse regel duwen. Een vaste icoonkolom van 22 pixels met een meegroeiende tekstkolom houdt de uitlijning stabiel. Op telefoon en tablet visueel hergetest; bovenkanten van icoon en tekst in de eerste regel gelijk gemeten.

De assetcacheversie is `20261115-flows-1`. Een volledige browservernieuwing is gebruikt om de nieuwe componentcode te controleren. Een code-update die een component opnieuw laadt is onderscheiden van de gewone herverbinding met dezelfde versie.

## Bewijs

Screenshots en aanvullende logs staan lokaal onder:
`ui-flows-2026-11-15/`.

Belangrijke bestanden: `incident-active.png`, `incident-awaiting-clear.png`, `selftest-active.png`, `selftest-timeout.png`, `selftest-explicit-success.png`, `selftest-explicit-failure.png`, `offline-draft.png`, `reconnected-draft.png`, `confirmation-fixed-reloaded.png`, `incident-phone-fixed.png`, `incident-tablet-fixed.png`, `helpers-idle.png`, `final-automation-off.png`.

Een eerdere opname `incident-phone.png` had niet het bedoelde telefoonformaat; die telt niet als telefoonbewijs. Gebruik uitsluitend `incident-phone-fixed.png` voor de definitieve telefoonweergave. `confirmation-fixed.png` is van vóór volledig vernieuwen en bevat nog oude componentcode; gebruik `confirmation-fixed-reloaded.png`.

Nieuwe volledige validatie: `config/validation/b2fe46b7257e40a4b01ff2e081143b27/validation-result.json`: PASS. Backend 429 PASS, frontend 43 PASS, Ruff/format, hassfest, PowerShell/Compose, HA 2026.10.4 en 2026.11.1 en cleanup PASS.

## Eindtoestand

Tijdelijke groep verwijderd; oorspronkelijke bronselectie A+B hersteld, Q weer uit selectie. Rook-, uitval-, fout- en testhelpers uit; resultaathelper idle; geen lopende test. Automatische meldingen en beide mockontvangers uit. Geen groepsacties of koppeling meer ingesteld. Viewportoverride opgeheven; taal en thema behouden. De simulator draait voor review.

Geen commit, push, tag, publicatie of productie-installatie. Geen fysieke detectie, geluid of telefoonbezorging bewezen. Marktinstaller-/HA-back-upacceptatie valt buiten deze visuele review.
