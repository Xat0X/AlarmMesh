# Onafhankelijke review: alarminstellingen en telefoontestbeoordelingen

Datum: 18 november 2026. Lokale wijzigingen bovenop beta.12; geen publicatie.

## Uitkomst

In de gecontroleerde code en simulatorscenario's zijn geen nieuwe productfouten aangetroffen. Er is daarom geen functionele code aangepast. De bestaande lokale wijzigingen blijven behouden. Deze review voegt onafhankelijke bewijsbestanden en dit verslag toe.

## Zelf uitgevoerd

- Alarmroutes openen en vernieuwen zonder uitvoer; ontbrekende bron en probleemhulp gecontroleerd.
- Kritiek telefoonprofiel wijzigen, samenvatting bekijken en annuleren; opgeslagen instellingen blijven intact.
- Precies één expliciet bevestigde aanvraag naar een aantoonbaar gesimuleerde ontvanger. Ontvangen en gehoord afzonderlijk geregistreerd, met simulatiemarkering. Registratie verstuurt niets.
- Profielwijziging bewaart de eerdere beoordeling als historie, niet als bewijs voor het nieuwe profiel.
- Telefooninstellingen daadwerkelijk opgeslagen; antwoord daarna onderschept. Na reconnect opgeslagen gegevens teruggelezen zonder opnieuw te versturen.
- Ook een beoordelingsopslag daadwerkelijk uitgevoerd en het antwoord verloren laten gaan. Daarna browser offline/online en reconnect. Tijdens teruglezen gewijzigde formulierkeuzes blijven herkenbaar als niet opgeslagen. Heropenen toont de werkelijk bewaarde beoordeling. Precies één schrijfactie en nul telefoonopdrachten.
- Onverzonden concept heropend. Twee gesimuleerde rookbronnen gecontroleerd: waarschuwing blijft in het formulier zichtbaar en incidentverloop vermeldt waarnemingen. Automatische uitvoering blijft uit.
- Volledige herstart van de eigen simulatorcontainer. Instellingen en alle vijf testaanvragen met beoordelingen exact vergeleken vóór en na herstart: behouden, geen herhaalde uitvoer.
- Acht Nederlands/Engels × licht/donker × telefoon/tablet-combinaties gerenderd en de schermbeelden bekeken. Ook breed scherm, toetsenbordfocus, Escape/focusherstel, lange gelijke namen, lege toestanden en beperkte schermruimte beoordeeld. Geen horizontale overloop in gecontroleerde dialogen.

## Automatische controle

De volledige nieuwe Linux-validatie heeft 602 backendtests en 117 frontendtests zonder skips doorlopen. Ruff, opmaak, hassfest, PowerShell, Compose en opruimcontrole slagen. De compatibiliteitscontroles op HA 2026.10.4 en 2026.11.1 slagen eveneens.

## Bewijs

- [Browserroutes en controles](../config/independent-evidence-review/flows.json)
- [Verloren beoordelingsantwoord en teruglezen](../config/independent-evidence-review/observation-readback.json)
- [Werkelijke simulatorherstart](../config/independent-evidence-review/restart-result.json)
- [Visuele matrix](../config/independent-evidence-review/matrix.json)
- [Alarminstellingen: acht weergaven](../config/independent-evidence-review/screenshots/contact-settings.jpg)
- [Testbeoordelingen: acht weergaven](../config/independent-evidence-review/screenshots/contact-observation.jpg)
- [Afwijkende onverzonden keuzes na reconnect](../config/independent-evidence-review/screenshots/observation-readback.png)
- [Volledige nieuwe validatie](../config/validation/742ae647d4d642f5ad626b1f81a35d76/validation-result.json)

Twee lokale pakketten bevatten elk 43 bestanden met dezelfde SHA-256: `41de2901c139d469e7a074fa9b72e7dbe8fb591c15e4e84004297ba0d1439c40`. Statuscode en bestaande statustests zijn ongewijzigd. Manifestversie blijft beta.12.

## Bewijsgrenzen

De verloren antwoorden zijn geïnjecteerd nadat een echte simulatoropslag slaagde; de browserverbinding is daarnaast daadwerkelijk offline/online gezet. Lange/lege gegevens en taalkeuze zijn browserfixtures. Beperkte schermruimte is CSS-reflow, geen native browserzoom. Dit is eigen visuele inspectie, geen gebruikersonderzoek of screenreadertest. Geautomatiseerde routecontroles dekken ook gemengde providers en overlappende groepen; geen fysieke apparaten gebruikt.

Er zijn geen echte telefoons, melders of productie-installaties benaderd. De eerder door de gebruiker gemelde geslaagde iPhone-test blijft afzonderlijke gebruikersrapportage. Koppeling en automatische uitvoer staan uit, helpers in rust, geen lopende zelftest. Niets gecommit, gepusht, getagd of gepubliceerd. Hosted GitHub Actions zijn niet gestart.
