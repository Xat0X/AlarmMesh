# Vrijgaveaudit voor 0.1.0-rc.3

In de simulator liet één klik Jana en TEST stoppen met meeklinken terwijl Senne rook bleef melden. Toen Jana vlak vóór de klik ook rook meldde, kreeg alleen TEST een stopopdracht. De Aqara kreeg bij beide proeven uitsluitend de startopdracht. De tijdlijn en de opdrachtenteller zijn in de simulator gecontroleerd. De thuistest controleert het hoorbare resultaat. [RC3 en het testpad](releases/0.1.0-rc.3.md)

## Vrijgaveaudit voor 0.1.0-rc.2

[RC2](releases/0.1.0-rc.2.md) maakt per Heiman de ontvangsttijd, de koppeling aan de startaanvraag en de reden voor uitstel of afzien van stoppen zichtbaar. De MQTT-simulator behandelt een tijdige en een late terugmelding en een meeklinkende melder die zelf rook detecteert. De pakketcontrole gebruikt RC1 als vorige versie op beide ondersteunde Home Assistant-versies.

## Vrijgaveaudit voor 0.1.0-rc.1

De [releasekandidaat](releases/0.1.0-rc.1.md) voegt een tijdlijn voor rook en startopdrachten toe. Vergelijk het tijdstip van een gehoord heralarm met de startregels voor dezelfde doelmelder. De bijbehorende simulatorproeven behandelen ook een herladen integratie en lokale rook op een meeklinkende doelmelder.

Controleer een upgrade vanaf de gepubliceerde bèta 20 met `dev/release/check-update.ps1 -PreviousRevision 0.1.0-beta.20 -HaVersion <versie> -CommittedCandidate` op de releasecommit. De praktijkpunten uit de audit hieronder blijven van toepassing.

## Vrijgaveaudit voor 0.1.0-beta.20

**20 november 2026 · laatste testversie vóór de productiebeslissing.** Gebruik de Incidents-simulator op poort 8131. De drie belangrijkste wijzigingen zijn rechtstreeks naar actuele rook gaan vanuit een open formulier, terugkeren naar de betrokken melder en een onzekere opslag controleren met de daadwerkelijk bewaarde gegevens.

| Taak | Wat is aangepast en hoe is het gecontroleerd? |
| --- | --- |
| Eerste gebruik en dagelijks overzicht | Bij maximaal drie melders met een duidelijke rookvrije status staan de namen op het overzicht. Een verse simulator met twee gekozen melders werkt zonder groep of telefoon. De browserproef omvat ruimtefilter, gelijke lange namen en een melder zonder ruimte. |
| Onderhoud tijdens rook | Op bèta 19 had de rookwaarschuwing in een geopend venster geen incidentknop. Vanuit onderhoud in Hal opent de knop nu de lopende rookmelding van Zolder. Vanuit het incident kun je terug naar Hal. Een onderbroken oefening gaat meteen naar de actuele melding. Een oude incidentlink houdt zijn eigen historie. |
| Tijdelijk offline | Na het sluiten van de WebSocket toont het paneel de laatste ontvangsttijd en de toen gemelde rook. Na opnieuw verbinden vervangt een actuele momentopname die informatie. |
| Groepen en telefoons | Een terugleesactie vergelijkt de server met het formulier zoals het er aan het einde van het ophalen uitziet. Groepen hebben bij aanmaken een herkenbaar, uniek ID. Twee browsertabs zijn gebruikt voor verlies vóór ontvangst, verlies na opslag, latere invoer en conflicten. Controleren verstuurt alleen een leesaanvraag. |
| Onderhoudslogboek | Controle vergelijkt melderidentiteit, registratie-ID, soort, datum en tekst. Latere invoer kan als een afzonderlijke nieuwe vermelding worden opgeslagen. Een tweede tab kan de eerdere registratie met hetzelfde ID niet overschrijven. |
| Meeklinken en telefoons | De standaardgroep verzond bij gesimuleerde rook geen opdracht. De modeltest volgt een Heiman S1-M en Aqara JY-GZ-01AQ via MQTT, ook wanneer het doel zelf rook meldt. De Heiman mag zijn eigen gekoppelde geluid na vrijgave stoppen. Voor deze Aqara verstuurt AlarmMesh geen automatische stilzetopdracht. De telefonieschermen onderscheiden instellingen, aanvraagstatus en de persoonlijke bevestiging van ontvangst of geluid. |

### Zelf beoordelen in vijf minuten

1. Open **Overzicht → Stille oefening → Zolder**. Ga één stap verder en open **Waarom blijven deze acties uit?** Bij Hal zie je via welke twee groepen hij is opgenomen. Bij de gekozen oefentelefoons staat waarom ze stil blijven.
2. Open **Melders → Hal**. Bekijk de batterij en de alarmroute. Onder **Onderhoud noteren** staat de weg terug naar dezelfde melder.
3. Bekijk de voor/na-beelden van de onderbroken onderhoudstaak en de matrix van Nederlands/Engels, licht/donker en telefoon/tablet. De rookknop opent het actuele incident. Op de smalle weergave blijft hij met het toetsenbord bereikbaar.

### Reproduceerbare vrijgavecontroles

De checkout is vergeleken met de tag `0.1.0-beta.19`. Gebruik `dev/validate.ps1` voor de volledige technische validatie en `dev/release/check-update.ps1 -PreviousRevision 0.1.0-beta.19 -HaVersion <versie> -CommittedCandidate` op de tag `0.1.0-beta.20` voor de upgrade vanaf bèta 19. De twee versies zijn 2026.10.4 en 2026.11.1. De updateproef controleert schone installatie, herstart en herstel van gestopte testbestanden. De vergelijking omvat groepsleden, expliciete koppeling, een geselecteerde telefoon met kritisch profiel, geluid, volume en een exacte onderhoudsregel. De pakketten worden tweemaal gebouwd en per bestand en SHA-256 vergeleken.

**Open vóór stabiele publicatie.** De eigenaar beslist over vrijgave, licentie en distributierechten van het beeldmateriaal. Acceptatie van de eigen installatie-/back-uproute, werkelijk geluid en herstel per model/provider en bezorging op de eigen telefoons vraagt een afzonderlijke praktijktest. De lokale review gebruikte uitsluitend simulatoren en mockontvangers.

---

## Historische vrijgaveaudit voor 0.1.0-beta.15

**19 november 2026.** Deze kandidaat volgt op de gepubliceerde bèta 14. De praktijkcontrole door de beheerder en zijn beslissing over stabiele publicatie staan open. De [release-instructies](releases/0.1.0-beta.15.md) bevatten een korte rondleiding.

| Onderdeel | Hoe je de controle kunt herhalen | Wat wordt gecontroleerd |
| --- | --- | --- |
| Rookstatus en uitval | Volledige backendtests, inclusief de bestaande statustests | Rook en ontbrekende gegevens, overlappende groepen, sensoridentiteit en herstelvoorwaarden |
| Melders en uitvoer | Runtime- en drivercontroles met testapparaten op HA 2026.10.4 en 2026.11.1 | Zigbee-, Matter- en Z-Wave-paden, ontbrekende mogelijkheden, testaanvragen, start en herstel. Koppeling begint uit. |
| Telefoons, onderhoud en scripts | Backendtests en het geïsoleerde update- en herstartscenario | Profielgebonden meldingen, bevestigingen, mockaanvragen, volgorde van scriptacties, onderhoud en uitblijven van dubbele uitvoer na herstart |
| Paneel, gezin en incidentlinks | Frontendtests en lokale Chromium-simulator | Oude incidentlink met huidige rook, pauzeren en hervatten van een gewijzigde oefenroute, opgeslagen onderhoud na wegvallen van het antwoord |
| Toegang en gegevens | Admincontroles bij WebSocket-opdrachten, tests voor rolverlies, diagnostiek en opslag, gesloten pakketlijst | Beheerderstoegang, wegvallen van oude gegevens, begrensde historie en toegestane pakketbestanden |
| Installeren en herstellen | `dev/release/check-update.ps1 -PreviousRevision 0.1.0-beta.14 -CommittedCandidate` op beide geteste HA-versies | Schone installatie, update vanaf het vorige pakket, bestaande groepskeuzes en melderidentiteiten, bewaard logboek, procesherstart, terugzetten van gestopte simulatorbestanden |
| Distribueren | Twee ZIP-builds met `dev/release/package.py --revision` vanaf dezelfde commit, controles op main en tag, controle van de gepubliceerde hash | Zelfde pakketinhoud als getest, versie in manifest en een afzonderlijke bètarelease |

## Gevonden en hersteld

1. Bij wijziging van telefooninstellingen kon de open oefenkaart de oude route blijven tonen. Een wijziging met dezelfde groepsrevisie is afzonderlijk gereproduceerd. Ook de onderliggende route-informatie verliest haar oude uitkomst.
2. Een opslagcontrole kon al lopen tijdens een onderhoudsaanvraag. De interface laat verificatie na een onzeker antwoord toe en controleert aanvraag, inhoud, installatie en melder. Een onleesbaar logboek geeft geen toestemming om opnieuw te schrijven.
3. Een geopende oude incidentlink kon de actuele rokende melder aan het zicht onttrekken. De actuele melding staat nu boven de bewaarde historie. De eerste geregistreerde bron blijft bij het vrijgegeven incident zichtbaar.

Alle drie kregen een eerst falende frontendtest. In de browser is de oefening in Nederlands en Engels, licht en donker, op telefoon- en tabletbreedte doorlopen. De onderhoudsproef gebruikte echte opslag in de lokale mockinstallatie met een onderschept antwoord en daarna een herladen pagina. De weergave van gelijktijdige actuele rook en een oud vrijgegeven incident en de gewijzigde instellingen gebruikten gecontroleerde schermgegevens. Tijdens deze browserproeven bleven de uitvoertellers van de simulator gelijk.

## Beslissing na de praktijktest

Controleer de update via je eigen installer, de bewaarde keuzes en de stille oefening. Een onderhoudsnotitie moet na herladen één keer terugkomen. Beoordeel of de Nederlandse teksten en alarmroutes kloppen voor jouw gezin. Meld afwijkingen met de versie en het precieze klikpad, zonder telefoonnummers of toegangscodes.

De updateproef vervangt bestanden in een geïsoleerde installatie en herstelt een kopie van normaal gestopte testbestanden. De installer op je eigen systeem en herstel van een echte Home Assistant-back-up zijn aparte praktijkcontroles. Radiobereik, fysieke detectie, werkelijk meeklinken en hoorbare telefoonbezorging zijn in deze audit niet getest. Eerdere gebruikerservaring met een kritieke melding op één iPhone staat los van deze kandidaat.

De repository bevat geen algemeen licentiebestand. De herkomst van de door de gebruiker aangeleverde afbeeldingen staat in [branding](../assets/branding/README.md). De eerdere open keuzes over licentie en distributie van artwork blijven bij de eigenaar. De publicatie van deze bèta kiest daarvoor geen voorwaarden.

---


## Historische vrijgavebeoordelingen

### Historical proposal: 0.1.0-beta.4

The unpublished working tree adds ordinary Companion notifications, existing HA
script actions and reviewed self-test requests to the beta.3 linking/catalog base.
The [finishing review](finish-review.md) records actual checks and package identity.
Proposed source: `b2f3d719a86cffb0a533fa5650dce624fd2275f2` plus the reviewed local
diff; there is no new commit or hosted-CI result for it. Remote beta.3 was verified
at that SHA on 2026-11-14; no beta.4 tag was observed. Manifest remains beta.3.

Keep this a default-off, opt-in pre-release after explicit owner approval, visual
acceptance and CI for the eventual exact release commit. Preserve existing explicit
choices. No production or physical acceptance is claimed. Installation/update uses
the existing Marketplace/HACS route; the new checks exercise local package copies,
not installer end-to-end behavior. Rollback from group schema 3 needs the matching
pre-update configuration backup; replacing Python alone is insufficient.

Draft release text: “AlarmMesh beta.4 adds separately configured phone notifications,
ordered incident scripts, reviewed built-in self-test requests and clearer incident
details. New automation defaults off. Current reports remain separate from requested
execution and physical results. Tested HA targets are exactly 2026.10.4 and 2026.11.1.
Read the supported-device conditions and back up before updating.”

Owner decisions remain license, artwork distribution rights, version/publication
timing and any later catalog participation. No release, tag, version bump, settings
change or catalog application is performed by this preparation.

## Historical catalog test release — 0.1.0-beta.3

Prepared 2026-11-14 at the owner's request for installation review on an existing
Home Assistant. Reviewed product baseline:
`e092fd6ead2739f3603bb7583a3c57accb506048`.
This release changes only version metadata and release documentation.

Manifest and tag use **0.1.0-beta.3**. Publish as GitHub pre-release, never latest
stable, only after all hosted checks for the exact release commit succeed.
The normal source-folder installer route, dependencies and minimum HA remain
unchanged. No live HA installation or physical action is part of publication.

New groups and old groups without linking remain disabled. Explicitly enabled
configurations are preserved: the installation notes tell the owner to disable
them before updating for this review. Catalog recognition never enables linking.
BSD-2 requires its same-device broadcast setting to explicitly report off;
the changed authority requires re-review of earlier broader local assignments.

The product baseline passed hosted tests (367 backend, 20 frontend), hassfest
and both HA compatibility jobs, including 20 runtime and 14 driver checks per
version. The release metadata commit must pass its own workflow before publication.

See [release notes](releases/0.1.0-beta.3.md) for installation, default-off review,
support coverage, Bosch behavior and backup-based recovery. Technical driver
checks do not establish complete provider/radio or physical device acceptance.
Earlier dated catalog/UI evidence remains historical in the support guide.

Outstanding: owner-observed upgrade/recovery of this payload, physical acceptance,
and previously recorded license/artwork/catalog-admission decisions. This work
does not make stable-release or certification claims.
