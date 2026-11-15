# Instellen, onderhouden en incidenten begrijpen

Review van 15 november 2026 op basis van **0.1.0-beta.4**,
commit `84cf0932d0dbafb1cf87894cff8e6f7fc07d4d52`, met lokale wijzigingen.
Dit is geen nieuwe release en geen fysieke apparaatacceptatie. De eerdere
[visuele beta.4-controle](visual-flow-review.md) blijft historisch bewijs voor
die revisie; zij dekt deze nieuwe schermen niet.

De [onafhankelijke vervolgcontrole](#onafhankelijke-vervolgcontrole) hieronder
registreert de latere bronreview, twee correcties en de nog geblokkeerde visuele
acceptatie. De eerste implementatieresultaten blijven als eerder bewijs staan.

## Wat is gebouwd

- Eén zevenstappenroute in de bestaande instelhulp, vanuit Overzicht en
  Instellingen. Voortgang komt uit de actuele bewaarde configuratie en
  servervalidatie. Overslaan en later terugkomen kan zonder extra opslag.
  Ingesteld, uit/optioneel, aandacht nodig, niet ondersteund en onbekend staan
  afzonderlijk vermeld. Niets wordt met een algemene afrondknop ingeschakeld.
- Onderhoud vanuit diezelfde schermen: configuratieproblemen en apparaatmeldingen
  staan apart. Bron-/bedieningsuitval, ontbrekende ruimtes en bewaarde ongeldige
  zoemer-, script- en telefoontoewijzingen verwijzen naar bestaande instellingen.
  Verwijderde ontvangers blijven zichtbaar tot een expliciete wijziging; annuleren
  bewaart de oude selectie.
- Batterijpercentages alleen tussen 0 en 100, plus aantoonbaar gekoppelde binaire
  lage-batterij-/storingswaarden. Geen bewijs betekent onbekend. **20% of lager**
  is uitsluitend een benoemde presentatiedrempel. De rookregels en uitvoering
  veranderen niet; er worden geen onderhoudsmeldingen verstuurd.
- Incidentdetails onderscheiden actuele rook, nog niet expliciet vrijgegeven
  bronnen, groepen, opdrachtsoorten, acceptatie/fouten/onbekende uitkomsten en
  werkelijk geregistreerd herstel. Ontbrekende chronologie wordt benoemd.
  Zelftestaanvraag, activiteit en expliciet resultaat blijven apart.
- Nederlandse en Engelse tekst, grotere aanraakdoelen, afbreken van lange namen,
  beperkte dialoogbreedte en behoud van concepten/confirmaties. Bestaande
  serverrechten, identiteiten en bevestigingen blijven leidend.

Zie de [paneelhandleiding](panel.md#guided-setup-and-group-troubleshooting-local-development)
voor de bediening. Geen rook gemeld is geen veiligheidsgarantie. Complete is geen
heartbeat of fysieke gezondheidscontrole. Een geslaagde HA-opdracht bewijst geen
fysieke uitvoering; ook een apparaatzelftest bewijst geen rookdetectie.

## Eerdere controlelijst van de eerste implementatie

Lokale bewijsmap: `config/usability-review/5481b54336c446959c460f0c37e20c14/`.
Deze map, alle screenshots/configuraties en pakketten worden door Git genegeerd.

| Controle | Soort bewijs | Resultaat |
| --- | --- | --- |
| Nieuwe metadata-/voortgangtests | Geautomatiseerd, echte HA-fixtures en mocks | 15 PASS; `targeted-final.log` |
| Volledige bestaande validatieroute | Linux Python 3.14.10, HA 2026.10.4; Node 24.22.1 | 444 backendtests en 48 frontendtests PASS; Ruff/format, hassfest, PowerShell/Compose en cleanup PASS |
| Beide exacte compatibiliteitsversies | Officiële images, simulatie en bestaande private driverfixtures | 2026.10.4 en 2026.11.1 elk 25 runtime + 16 driverchecks PASS; werkelijke versies geassert |
| Pakket tweemaal gebouwd | De bestaande gesloten inventaris, deterministische ZIP | PASS; elk 32 bestanden, identieke SHA-256 |
| Simulatorconfiguratie / asset | Technisch | Configuratiecheck PASS; actuele JS via HTTP 200, geen visuele waarneming |
| Acht visuele combinaties | Niet uitgevoerd | Browserhost en native computer-use-pipe ontbreken |
| Fysieke melders/telefoons/scripts | Niet uitgevoerd | Uitgesloten; alleen mocks en event-only scripts gebruikt |

Definitieve volledige run:
`config/validation/97fb076a267347ff922cf073be155d38/validation-result.json`,
met `pytest.xml`, `frontend.log`, `hassfest.log` en beide compatibiliteitssamenvattingen.
De collector heeft beide pakketten bytegewijs vergeleken met de daadwerkelijk
gevalideerde productexport. Samenvatting en exacte lijst van de 20 gewijzigde
bestanden: `results.json` en `scope-result.json` in de lokale bewijsmap.
Scope-/privacycontrole en alle **71 lokale documentatie-/afbeeldingslinks** PASS.
Dit is lokale uitvoering op de genoemde basis plus wijzigingen, geen nieuwe
hosted GitHub-uitkomst.

Pakketten: `config/release-packages/usability-5481b543-final-one/` en
`config/release-packages/usability-5481b543-final-two/`, elk met `inventory.json`.
SHA-256: `24b1595e0946b5732fcbd184fe6a43fd80a57e233d6852c82d80b589d359c925`.
Het zijn lokale testpakketten, geen gepubliceerde of distributiegoedgekeurde release.

De standaardroute is ongewijzigd `pwsh -NoProfile -File ./dev/validate.ps1`.
Er is één extra compatibiliteitsscenario voor afgeleide instelvoortgang en
passief onderhoud; de wrapper eist nu alle **25 runtime + 16 driver**-scenario's.
Geen oude tests zijn uitgeschakeld. Alleen de bestaande frontendassertie voor het
aantal instelstappen is gericht aangescherpt van drie naar zeven; alle andere
bestaande assertions en de 79 statusregeltests blijven behouden.

Een gerichte test toonde tijdens afwerking een verkeerde nieuwe labelkeuze aan:
een ondersteund Aqara-profiel met nog ontbrekende toestemming kreeg onterecht
"niet ondersteund". Dit is hersteld naar "uit/optioneel"; de specifieke voorwaarde
blijft zichtbaar en is niet automatisch aangepast. Bewijs vóór de correctie staat
in `prerequisite-before.log`; dezelfde test slaagt in `targeted-final.log`.

## Nog uit te voeren visuele matrix

Beide ondersteunde routes zijn daadwerkelijk geprobeerd: browserinventaris geeft
`The browser access host is unavailable`; `@oai/sky` geeft een ontbrekende native
pipe (`os error 2`). Er waren geen bestuurbare vensters. Geen authenticatie of
browserbeleid is omzeild, geen nieuwe onboarding gevraagd en geen screenshots
gemaakt. DOM-tests gelden niet als visuele controle.

| Taal | Thema | Formaat | Instelhulp, onderhoud, incidentdetails en dialogen |
| --- | --- | --- | --- |
| Nederlands | Licht | 390 × 844 | NIET UITGEVOERD |
| Nederlands | Donker | 390 × 844 | NIET UITGEVOERD |
| Engels | Licht | 390 × 844 | NIET UITGEVOERD |
| Engels | Donker | 390 × 844 | NIET UITGEVOERD |
| Nederlands | Licht | 1024 × 768 | NIET UITGEVOERD |
| Nederlands | Donker | 1024 × 768 | NIET UITGEVOERD |
| Engels | Licht | 1024 × 768 | NIET UITGEVOERD |
| Engels | Donker | 1024 × 768 | NIET UITGEVOERD |

Zodra de browserhost werkt: doorloop één volledige interactieve ronde; controleer
daarna alle acht combinaties op afbreken, overloop, contrast, focus en vertaling.
Gebruik de herkenbare simulatiemelders A/B/C/D en O: ondersteund, onbekend, gemengd
Zigbee2MQTT/ZHA en een lange naam. Gebruik uitsluitend de simulatiehelpers voor
rook, uitval, ontbrekende bediening, batterij, storing en mockfouten. Verwijder
alleen zelf gemaakte tijdelijke toewijzingen/ontvangers/scripts in deze simulator.
Controleer ook annuleren, oude bevestigingen, gewoon reconnect met een ingevuld
formulier en een zelftest zonder resultaat. Bewaar screenshots lokaal, inspecteer
ze werkelijk en rond af met alle helpers uit, resultaat idle en automatisering uit.

## Lokale reviewomgeving

Open **http://127.0.0.1:8131/alarmmesh** en vernieuw volledig voor cacheversie
`20261115-guidance-1`. Het bestaande simulatoraccount en de selectie blijven
behouden; onboarding hoeft niet opnieuw. Open Onderhoud via Overzicht of
Instellingen. Op het aparte simulatie-overzicht staan ook drie nieuwe helpers:
B batterij 14%, D batterij onbekend en B bediening ontbreekt. De bediening is
uitsluitend een mock, zonder broker, radio of fysieke uitvoer.

De bestaande eigendomsgecontroleerde omgeving gebruikt HA **2026.11.1**,
container `alarmmesh-incident-ui-316a03fe45be`, alleen localhostpoort 8131 en
alleen-lezen product-/fixturemounts. Configuratiecontrole is vóór herstart gedaan.
Alle booleans hebben expliciet `initial: false`, de testresultaathelper `idle`.
Er zijn geen opgeslagen groepen of ingeschakelde automatische meldingen/acties.
De eindtoestand is technisch voorbereid; de browserweergave is niet geïnspecteerd.
Omgevingen op 8124–8130 zijn niet bediend.

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Incidents -Port 8131 -Action Stop
```

Stop bewaart account/configuratie. Verwijder de testmap niet automatisch. De
bridge is geen LAN-firewall; er zijn geen echte apparaten of productiegegevens
geconfigureerd. Niets is gecommit, gepusht, getagd, gepubliceerd of op een echte
installatie gewijzigd.

## Onafhankelijke vervolgcontrole

Op **15 november 2026** zijn de actuele diff, bestaande assertions en het
oorspronkelijke testbewijs opnieuw gecontroleerd. **56 product-/testbestanden**
uit de beginstand komen bytegewijs overeen met de export van de eerdere
geslaagde run (444 backendtests, 48 frontendtests en beide HA-versies).
Dit verifieert bestaand bewijs; het is geen nieuwe uitvoering van die tests.

Twee concrete afwijkingen zijn hersteld:

1. Een geselecteerde bron die in het register geen rookmelder meer is, kon in
   de instelhulp toch "Ingesteld" blijven. De presentatie gebruikt nu ook de
   bestaande backend-identiteitscontrole, toont aandacht nodig en benoemt de
   gewijzigde identiteit. Herstel van de metadata wordt direct verwerkt.
   Rookberekening, selectie en uitvoering zijn niet aangepast.
2. Een numerieke batterijwaarde met bijvoorbeeld eenheid V kon als percentage
   worden gepresenteerd. Een tegenstrijdige eenheid geeft nu onbekend in het
   onderhoudsoverzicht; de ruwe waarde en eenheid blijven in de details staan.
   Ook een ongeldige samengestelde eenheid blijft onbekend zonder het paneel te
   laten uitvallen.
   De bestaande HA-batterijklasse/providersemantiek geldt wanneer geen eenheid
   is aangeleverd. De 20%-presentatiedrempel verandert geen rook- of alarmregel.

Bewijs staat lokaal in
`config/usability-independent/90410a2724f44f4d82310bd947d6b7d0/`.
`regressions-before-valid.log` bevestigt vier falende assertions tegen de
oorspronkelijke bronkopie (bronidentiteit en drie conflicterende eenheden).
`regressions-after-valid.log` bevestigt 19 gerichte PASS-resultaten. De verdere
typecontrole reproduceerde twee fouten met samengestelde eenheden in
`unit-type-before.log`; `regressions-final.log` bevestigt alle **21 PASS**.
Een eerste testopzet gebruikte een niet-toegestane entiteitsruimtetoewijzing;
die fixture is gecorrigeerd naar de ondersteunde apparaatruimte-API. HA-rechten
of assertions zijn daarvoor niet afgezwakt. De oorspronkelijke logs zijn bewaard.

Instelstatus is configuratie-informatie, geen veiligheidsstatus. Onbekende
batterij-/storingswaarden krijgen geen gezonde melding. Een bestaande expliciete
apparaatuitslag blijft onderscheiden van HA-acceptatie en fysieke werking;
ontbrekend zelftestresultaat of bronuitval wordt niet als succes/herstel behandeld.
Formulierbehoud, reconnect, lange namen en lege toestanden zijn in code en
bestaande tests beoordeeld; hun visuele gedrag is in deze ronde niet waargenomen.

De browserinventaris gaf opnieuw geen apps/tabs: browser access host unavailable
en native pipe `os error 2`. Het ondersteunde `@oai/sky`-alternatief gaf dezelfde
ontbrekende pipe. Alle acht combinaties in de matrix hierboven blijven
**NIET UITGEVOERD**. Er zijn geen nieuwe screenshots gemaakt of geïnspecteerd en
er wordt geen visuele PASS afgeleid uit DOM-tests. Geen nieuwe onboarding nodig.

De simulator op 8131 is gecontroleerd op eigendom, localhostbinding, HA 2026.11.1,
alleen-lezen product-/fixturemounts, mocktelefoons en event-only scripts.
Opgeslagen groepen en automatische acties/meldingen staan uit; helpers hebben
expliciet een ruststand bij opstart. Er is geen productieomgeving benaderd.

Officiële semantiek opnieuw gecontroleerd:
[batterijsensor in procenten](https://contributors.home-assistant.io/core/entities/sensor/)
en [binaire batterij-/probleemstatus](https://contributors.home-assistant.io/core/entities/binary-sensor/).
Definitieve nieuwe validatie:
`config/validation/224775e0b5ff43e5873faf45badc0ac5/validation-result.json`.

| Controle na de correcties | Werkelijk resultaat |
| --- | --- |
| Linux Python 3.14.10 / HA 2026.10.4 | 450 backendtests PASS, inclusief 79 ongewijzigde statusregeltests |
| Node 24.22.1 | 48 frontendtests PASS |
| Ruff lint/format, hassfest, PowerShell, Compose, cleanup | PASS |
| Exact HA 2026.10.4 en 2026.11.1 | Elk 25 runtime + 16 driverchecks PASS, inclusief de twee reviewcorrecties |
| Bestaande assertions en overige beginbestanden | Behouden; alleen zeven bestanden in deze vervolgcontrole gewijzigd |
| Nederlands/Engels × licht/donker × 390×844/1024×768 | Alle acht NIET UITGEVOERD; ontbrekende browser-/native host |
| Screenshots | Geen nieuwe screenshots beschikbaar; geen visuele PASS geclaimd |

`results.json` en `scope-result.json` in de vervolgcontrolemap bevatten het
gecontroleerde bewijs en de precieze vervolgdiff. Twee nieuwe lokale testpakketten
onder `config/release-packages/independent-90410a27-final-one/` en `-two/` bevatten
elk dezelfde 32 bestanden en zijn bytegewijs vergeleken met de gevalideerde
productexport. Beide SHA-256:
`e068db505088a4718ef78bd9369111256ef2db7fd9250f07e2e371bd0bd3ffd0`.
De eerdere pakketten en resultaten hierboven zijn historisch bewijs gebleven.

De simulator is na de laatste correctie gecontroleerd herstart met behoud van
account en selectie. Geen opgeslagen groepen, automatische meldingen uit,
helpers initial false en resultaat idle. De echte eindweergave blijft niet
visueel gecontroleerd. Alleen de eigen ontwikkelcontainer is opgeruimd; 8131
blijft draaien. Geen commit, push, publicatie of toegang tot echte apparaten.


## Visuele vervolgacceptatie uitgevoerd


15 november 2026. Basis `84cf0932d0dbafb1cf87894cff8e6f7fc07d4d52`
(0.1.0-beta.4), met bestaande lokale wijzigingen. Alleen de gecontroleerde
simulator op `http://127.0.0.1:8131/alarmmesh`, HA 2026.11.1, is bediend.
Dit is nieuwe visuele waarneming; de eerdere ontbrekende browserhost is hier
niet meer de blokkade. Geen fysieke apparaatacceptatie of hosted CI geclaimd.

## Acht werkelijk bekeken combinaties

Per combinatie zijn vier screenshots opgeslagen en daadwerkelijk bekeken:
instelroute, onderhoud met batterijwaarschuwing, dialoog met lange apparaatnaam,
en incidentdetails met actuele rook. Bestandsvoorvoegsels:

| Taal | Thema | Formaat | Voorvoegsel | Resultaat |
| --- | --- | --- | --- | --- |
| Nederlands | Donker | 390 × 844 | nl-dark-phone | Bekeken, bruikbaar |
| Nederlands | Donker | 1024 × 768 | nl-dark-tablet | Bekeken, bruikbaar |
| Nederlands | Licht | 390 × 844 | nl-light-phone | Bekeken, bruikbaar |
| Nederlands | Licht | 1024 × 768 | nl-light-tablet | Bekeken, bruikbaar |
| Engels (GB) | Licht | 390 × 844 | en-light-phone | Bekeken, bruikbaar |
| Engels (GB) | Licht | 1024 × 768 | en-light-tablet | Bekeken, bruikbaar |
| Engels (GB) | Donker | 390 × 844 | en-dark-phone | Bekeken, bruikbaar |
| Engels (GB) | Donker | 1024 × 768 | en-dark-tablet | Bekeken, bruikbaar |

De matrix is browseremulatie, geen fysieke telefoon-/tabletvalidatie. Geen
horizontale afsnijding in de bekeken schermen; lange namen breken af, knoppen
en statusiconen blijven binnen de beschikbare ruimte. De route is lang maar
scrollbaar. De huidige dubbele HA/AlarmMesh-zijbalk blijft op tablet aanwezig.
Er wordt geen volledige WCAG-audit of achtmaal dezelfde integrale functionele
acceptatie geclaimd. Eerste/laatste routestappen zijn aanvullend bekeken.

## Uitgevoerde functionele controles

- Tijdelijk A/B/C/D/O geselecteerd: Zigbee2MQTT, ZHA, onbekend model en lange naam.
  De onbekende melder krijgt uitleg, geen willekeurige externe bediening.
- B batterij 14% wordt als presentatiewaarschuwing getoond; D batterij onbekend
  blijft onbekend. C-storing en ontbrekende B-bediening afzonderlijk zichtbaar.
  Geen van die onderhoudswaarden maakt op zichzelf een rookincident.
- Optionele groepen/zoemers/scripts/meldingen blijven als uit/optioneel vermeld,
  zonder algemene knop die ze allemaal aanzet. Ontbrekende ruimtes blijven
  aandachtspunten. Bronselectielink en bestaande HA-opties zijn bediend.
- Nieuwe-groepsdialoog met lange naam, expliciete leden en incidentbronnen
  bekeken. Geen groep opgeslagen, koppeling en scripts bleven uit.
- B rook aan en C bronuitval: rook behoudt prioriteit. Na B rook uit blijft C
  expliciet openstaan. Pas C weer beschikbaar/off geeft geregistreerd herstel.
  Mockuitvoertellers bleven 0; geen telefoon, script of zoemer aangestuurd.
- Zelftesthistorie wordt apart van actuele rook getoond; de bestaande gefaalde
  Q-mockaanvraag is historie, geen nieuwe zelftest in deze ronde. Geen nieuwe
  zelftestaanvraag gestart, geen fysiek resultaat geclaimd.
- Offline formulier blijft zichtbaar en bewaren wordt geblokkeerd. Tijdens de
  eerste herstart in de assetvernieuwingsronde werd het paneel opnieuw opgebouwd
  en ging het concept verloren. Daarom opnieuw getest zonder verdere codewijziging:
  na stop/start bleven groepsnaam en lidselectie behouden, de waarschuwing verdween
  en bewaren kwam beschikbaar. Concept geannuleerd. Een volledige paginareload
  wordt niet als conceptbehoud beloofd; dit is een grens van de waarneming.

## Gevonden fout en correctie

Na navigatie vanaf een lange pagina stond de nieuwe pagina soms halverwege of
onderaan. Visueel gereproduceerd op telefoon. `go()` brengt de eigen panelshell
nu terug naar het begin. Pushupdates blijven hiervan uitgesloten, zodat actuele
statusberichten de leespositie niet resetten.

Nieuwe regressie in `dev/frontend/panel.test.mjs` faalde vóór correctie
(0 scrollaanroepen waar 1 verwacht) en slaagt erna. Alle 49 frontendtests slagen.
De assetversie is `20261115-usability-visual-1`, zodat vernieuwen de correctie laadt.
De correctie is na vernieuwen visueel bevestigd.

## Validatie na de correctie

Volledige run: `config/validation/a3d81590dab1423e83362414df87d4f3/validation-result.json`.

| Controle | Werkelijk resultaat |
| --- | --- |
| Backend, Linux / HA 2026.10.4 | 450 PASS |
| Frontend, Node | 49 PASS |
| Ruff, format, hassfest, PowerShell, Compose, cleanup | PASS |
| Exact HA 2026.10.4 | 25 runtime + 16 driverchecks PASS |
| Exact HA 2026.11.1 | 25 runtime + 16 driverchecks PASS |

De rookstatuscode, beschermde statustests, manifestversie en branding zijn door
deze visuele correctieronde niet gewijzigd. De bestaande lokale wijzigingen zijn
behouden. Nieuwe CI-resultaten ontbreken omdat niets gecommit/gepusht is.

## Bewijs en eindstand

Screenshots staan lokaal in
`C:/Users/Steven/Documents/ChatGPT/AlarmMesh/ui-usability-2026-11-15/`.
De matrix gebruikt `*-guide.jpg`, `*-maintenance.jpg`, `*-dialog.jpg` en
`*-incidents.jpg`. Aanvullend: `awaiting-clear.jpg`, `confirmed-recovery.jpg`,
`offline-draft.jpg`, `reconnected-draft.jpg` en `final-overview.jpg`.
`final-automation-off.jpg` toont slechts een gedeelte van de instelroute en is
geen zelfstandig bewijs van de volledige meldingsinstelling; die is in de
actuele toegankelijkheidsweergave expliciet als uit bevestigd.

Een incidenteel verkeerd geschaald browsercapture is na reset van de tijdelijke
viewport opnieuw gemaakt en overschreven; alleen de opnieuw bekeken matrixbeelden
worden als formaatbewijs gebruikt.

Oorspronkelijke A+B-selectie hersteld, geen groepen opgeslagen, alle gebruikte
helpers uit en resultaat idle. Meldingen uit, beide mockontvangers uit. Nederlandse
taal en automatisch thema hersteld, tijdelijke schermoverride verwijderd. Simulator
blijft beschikbaar. Geen commit, push, tag, release of toegang tot echte HA/apparaten.
