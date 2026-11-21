# Welke rookmelders kunnen meeklinken en stoppen?

Onderzoek van 19 november 2026 bij de praktijktest op bèta 15. De gebruiker hoorde meerdere melders opnieuw afgaan. Het tijdstip en de afzender van een eventuele tweede opdracht zijn onbekend. De onderstaande mogelijkheden zijn ontleend aan apparaatdocumentatie, de code en tests met gesimuleerde apparaten.

## Meeklinken stoppen met één druk

Open tijdens een rookmelding **Groepen → je groep → Stop meeklinken in deze groep**. Dezelfde knop staat bij de groep in het actuele incident. Boven de knop staan de melders waarvoor een stop mogelijk is. Zolang de melder op de overloop rook meldt, kun je bijvoorbeeld het meeklinken van de melders in de hal en de berging stoppen. Meldt de melder in de hal inmiddels zelf rook, dan krijgt alleen de melder in de berging de stopopdracht. In de tijdlijn staat per melder wanneer je de stop hebt aangevraagd.

De knop werkt voor een herkende Heiman-bediening waarvan de start aan AlarmMesh is gekoppeld. Een melder met onzekere terugmelding of een doel dat tegelijk voor een andere groep klinkt valt buiten de opdracht. Voor de Aqara-melder blijft alleen starten beschikbaar. De fysieke knop op een melder geeft geen groepsopdracht.

Bij een Heiman kan de groepsknop ook beschikbaar worden als de eerste herkenbare terugmelding van het meeklinken pas na twee seconden binnenkomt. Dat geldt voor de oorspronkelijke groep en startopdracht. Ook nadat de bron weer rookvrij is, kun je bij **Groepen** op de knop drukken zolang AlarmMesh diezelfde sirenestand nog kan herleiden. Bij eigen rook, een onzekere rookstatus of een nieuwe start vervalt die toestemming. Een late bevestiging geeft uitsluitend toestemming voor een handmatige groepsstop.

Na een groepsstop controleert AlarmMesh per melder de door Home Assistant gemelde sirenestand. Bij `stop` zie je die terugmelding in de tijdlijn. Meldt de bediening na de opdracht opnieuw en herkenbaar dat ze nog meeklinkt, dan controleert AlarmMesh na vijf seconden de rookstatus en groep en kan het één extra stop aanvragen. Bij uitblijvende of onduidelijke terugmelding zie je **De stand stop is niet bevestigd**. De tijdlijn geeft de softwarestand weer. Of de melder fysiek stil is, kun je ter plaatse vaststellen.

## De melders uit de test

| Melder via Zigbee2MQTT | Bij rook op een andere melder | Wanneer kan AlarmMesh hem stoppen? |
| --- | --- | --- |
| Heiman HS1SA-E-PLUS | Een aangevinkte melder kan de opdracht `smoke_siren` krijgen op `siren_for_automation_only`. | Automatisch zodra alle betrokken bronnen en de doelmelder rookvrij zijn, of eerder met de groepsknop als de doelmelder zelf rookvrij is. Beide gebruiken `stop` op de afzonderlijke bediening voor meeklinken en vereisen een bevestigde eigen start. |
| Aqara JY-GZ-01AQ, ook verkocht als JY-GZ-03AQ | De keuze `alarm` op `buzzer` vraagt geluid aan als de melder zelf geen rook waarneemt en `linkage_alarm` aan staat. De aparte sensor `buzzer_manual_alarm` geeft de toestand van het handmatig geactiveerde geluid. | Het toestel gebruikt `mute` om dit geluid te stoppen. Dezelfde keuze kan bij lokale rook het eigen alarm circa 80 seconden dempen. Er kan rook ontstaan tussen een HA-statuscontrole en ontvangst van de opdracht. AlarmMesh biedt daarom alleen starten aan voor deze route. |

Op de Heiman kan de fysieke knop het lokale geluid dempen terwijl de rookindicatie aan blijft. Zigbee2MQTT beschrijft de demptijd en het exacte heralarmgedrag van de PLUS als onbevestigd. Bij Aqara kan ook `linkage_alarm_state` uitgaan na handmatig dempen. Deze waarden zijn geen bewijs dat alle betrokken bronnen weer vrij zijn. [Heiman](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html) · [Aqara](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html)

Bèta 15 controleerde bij Aqara de stand van de schrijfkeuze zelf. Zigbee2MQTT publiceert daarvoor geen toestand. De lokale correctie controleert de afzonderlijke terugmelding van hetzelfde apparaat. De opdrachtkeuze moet beschikbaar zijn met de opties `alarm` en `mute`. Bij firmware 21 geldt de bestaande blokkade. Een eerder opgeslagen Aqara-keuze moet na deze wijziging eenmalig opnieuw worden bevestigd. [Zigbee2MQTT-apparaatdefinitie](https://github.com/Koenkk/zigbee-herdsman-converters/blob/master/src/devices/lumi.ts) · [HA-ontdekking in Zigbee2MQTT](https://github.com/Koenkk/zigbee2mqtt/blob/master/lib/extension/homeassistant.ts)

## Waarom bleef het vinkje van de Aqara-melder uit in bèta 16?

Wanneer Zigbee2MQTT de Aqara JY-GZ-01AQ aan Home Assistant doorgeeft, kan de interne identificatie van de koppelschakelaar `switch_linkage_alarm` bevatten. Bèta 16 zocht alleen naar de kortere vorm `linkage_alarm`. Daardoor kon AlarmMesh bij een ingeschakelde schakelaar vragen om hem in te schakelen. Dit is ook gebeurd in een geïsoleerde Home Assistant met de identificatie uit Zigbee2MQTT. [Schakelaar bij ontdekking](https://github.com/Koenkk/zigbee2mqtt/blob/3c841fdfd66c92239921ef84fde8f039c64e1662/lib/extension/homeassistant.ts#L1172-L1205) · [Opbouw van de unieke identificatie](https://github.com/Koenkk/zigbee2mqtt/blob/3c841fdfd66c92239921ef84fde8f039c64e1662/lib/extension/homeassistant.ts#L1853-L1855)

De correctie herkent beide vormen, ook als de gebruiker de entiteit heeft hernoemd. De schakelaar moet bij dezelfde melder en dezelfde MQTT-integratie horen. AlarmMesh geeft afzonderlijk aan of de schakelaar uit staat, ontbreekt, tijdelijk onleesbaar is of dubbel voorkomt. De meting `linkage_alarm_state` beschrijft een gekoppeld alarm. De instelling `linkage_alarm` geeft toestemming om mee te klinken. [Aqara-apparaatpagina](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html)

**Zo controleer je het zonder geluid te maken.** Open **Groepen → je groep → Samen afgaan**. Is de schakelaar beschikbaar en aan en voldoet de melder aan de overige voorwaarden, dan wordt het vinkje bij de Aqara-melder beschikbaar. Ook een geopend groepsformulier werkt het vinkje bij. Je kiest zelf of de melder mee mag klinken. Blijft het vakje grijs, lees dan de reden direct onder de naam. Je kunt in Home Assistant op de apparaatpagina van de Aqara-melder de entiteiten **Linkage alarm**, **Buzzer** en **Buzzer manual alarm** bekijken. Alleen hun toestand bekijken is voldoende voor deze controle. Firmware 21 heeft een afzonderlijke blokkade.

## Hercontrole van alle opgenomen modellen

Op 19 november 2026 zijn de 52 Zigbee-apparaatdefinities en hun 15 geregistreerde verkoopvarianten vergeleken met versie 26.135.0 van de Zigbee2MQTT-apparaatdefinities. Voor alle 52 bleven de aangeboden eigenschappen, hun type, de lees- en schrijfmogelijkheden, de keuzeopties en de onderliggende functies gelijk aan de eerder onderzochte versie 26.131.0. Ook de schakelaar voor Bosch BSD-2 en de geluidsbediening van ShinaSystem FAM-300Z vallen onder de verbeterde herkenning. [Apparaatdefinities bij deze controle](https://github.com/Koenkk/zigbee-herdsman-converters/tree/a2573dbbd7b5d28916c9007fd0f9e469b89befde/src/devices) · [Modelregister met verkoopvarianten](device-catalog.md)

De tabel hieronder bevat 47 rookmeldermodellen, twee losse sirenes, een hittemelder, een akoestische detector en een contactmodule. Van de **47 rookmeldermodellen** hebben er **16 via Zigbee2MQTT** en **9 via ZHA** een beoordeelde opdracht om bij rook elders mee te klinken. Een model kan in beide aantallen voorkomen. De vereiste bediening moet in de betreffende Home Assistant-installatie zichtbaar zijn. Voor de overige 31 Zigbee2MQTT-rookmeldermodellen is geen geschikte externe startopdracht gevonden. Een rookmelding kan wel andere ondersteunde apparaten aansturen. Zeven Heiman-modellen via Zigbee2MQTT ondersteunen daarnaast automatisch stoppen van het meeklinken. De laatste sectie behandelt de vijf Matter-modellen en Z-Wave JS afzonderlijk.

**Bijzonderheid bij ShinaSystem FAM-300Z.** De Zigbee2MQTT-definitie verwacht voor de externe alarmbediening de waarden `ON` en `OFF`. Dezelfde converter kan de terugmelding van het toestel als `true` of `false` publiceren. Home Assistant vergelijkt de ontvangen waarde met de bij ontdekking geregistreerde waarden. Herkenning van het apparaat en zijn schakelaar is daarom op zichzelf onvoldoende om de terugmelding te bevestigen. AlarmMesh vereist een beschikbare schakelaar met een bekende stand en toestemming van het toestel. [ShinaSystem-converter](https://github.com/Koenkk/zigbee-herdsman-converters/blob/a2573dbbd7b5d28916c9007fd0f9e469b89befde/src/devices/shinasystem.ts) · [MQTT-schakelaar in Home Assistant](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/mqtt/switch.py)

## Wat doet de blueprint anders?

De blueprint zoekt geluidsbedieningen bij de gekozen apparaten en controleert de beschikbare opties. Tijdens de alarmfase wacht ze onder meer op een dempschakelaar, de sensor voor handmatig dempen of de keuze `mute`. Zo'n signaal, een expliciete actie vanuit een telefoonmelding of het verdwijnen van de rook kan een herhaalde dempcyclus starten. Daarmee verklaart de code waarom de groep bij een eerdere test anders kon reageren. De beschikbare sensoren verschillen per apparaat. [Onderzochte blueprintversie](https://github.com/Xat0X/Smart-Smoke-System-The-Ultimate-Firealarm-Linker/blob/c665b6ad32f3beed8d0d833dd4023f37e84f463e/xat0x-smoke-linker-ultimate.yaml)

## Wat in Home Assistant is gereproduceerd

Dezelfde vijf scenario’s zijn in een geïsoleerde Home Assistant-omgeving afgespeeld op de gepubliceerde bèta 15 en op de lokale correctie. Bij bèta 15 faalden twee controles. Een werkende Aqara met een onbekende schrijfkeuze en expliciete rustterugmelding kon niet als doel worden opgeslagen. Bij een Heiman PLUS kon AlarmMesh de latere stop missen als een andere statusupdate binnenkwam tussen de startaanvraag en de bijbehorende terugmelding. Met de correctie slaagden alle vijf scenario’s. Na een kort vertraagde, aan de startaanvraag herkenbare terugmelding stuurde de integratie bij het vrijgeven van de bron één stop. Een latere geluidsmelding van onbekende herkomst gaf geen recht om dat geluid te stoppen.

Een fysieke druk op de bronknop levert daarmee nog geen groepsstop op. Het verschil tussen een lokaal gedempt alarm, een beëindigde rookmelding en een ontvangen groepsstop blijft van belang bij het lezen van de tijdlijn.

## Het incident achteraf bekijken

Voor Heiman HS1SA-E-PLUS en S1-M zie je per melder de sirenestand die Home Assistant doorgaf, het tijdstip tot op de milliseconde en de bijbehorende startopdracht. Bij een bevestigde koppeling wacht AlarmMesh tot de betrokken melders rookvrij zijn. Als de bevestiging uitblijft, vermeldt de tijdlijn of de wachttijd van twee seconden verstreek, het opdrachtkenmerk afweek of de sirenestand onbetrouwbaar was. Een latere terugmelding tijdens hetzelfde incident kan zichtbaar worden nadat automatisch stoppen voor die start is vervallen. De stand *stop* beschrijft wat Home Assistant rapporteerde. Een stopopdracht van AlarmMesh heeft een eigen regel. Oudere incidenten houden de gegevens die destijds werden geregistreerd.

Open **Activiteit → Rook en startopdrachten** en kies bij **Toon vanaf** de lokale begintijd van de test. Bovenaan staat het aantal vastgelegde startaanvragen per doelmelder. De tijdlijn toont de nieuwste gebeurtenis eerst. Bij elke opdracht zie je ook de melder of melders die de aanleiding waren. **Meldde al rook bij het opstarten** betekent dat AlarmMesh bij het inlezen rook zag. Het begin van die rookmelding kan eerder zijn geweest.

Twee startregels voor dezelfde melder zijn twee afzonderlijke Home Assistant-aanroepen. Noteer wanneer je de tweede toon hoorde en vergelijk dat met de tijdlijn. Een eerste start, gevolgd door alleen een stop, bevat één geregistreerde start. Een bevestiging van Home Assistant bewijst geen hoorbaar geluid. De geschiedenis omvat maximaal 30 dagen en 1.000 gebeurtenissen. Bij een onderbreking, een onvolledig logboek of tests met een oudere versie kan bewijs ontbreken.

1. Noteer in de Home Assistant-geschiedenis het tijdstip van de eerste rookmelding, het drukken op de knop en de tweede geluidsronde. Bekijk voor **iedere** melder de eigen rookstatus. Noteer ook `unknown` of `unavailable` en een eventuele herstart of herlaadactie.
2. Leg de aanvragen in AlarmMesh-activiteiten naast dat tijdvak. Kijk bij Heiman ook naar de automatiseringssirene en de dempstatus. Kijk bij Aqara naar de terugmeldingen voor handmatig alarm en handmatig dempen. De laatst gekozen waarde van de schrijfbediening bewijst geen geluid.
3. Controleer in het automatiseringsoverzicht of de oude blueprint of een andere automatisering voor deze melders ingeschakeld was en of daar rond hetzelfde tijdstip een trace bestaat. Een tweede AlarmMesh-start, een nieuwe rookovergang, een start na herladen en hernieuwd geluid zonder geregistreerde HA-opdracht vragen elk om een andere verklaring. Ontbrekende logregels sluiten een opdracht buiten HA niet uit.

In de simulator bleef een handmatig gestopte doelmelder stil zolang dezelfde rookmelding doorliep. Na het herladen van de integratie, met dezelfde rookbron nog aan en het doel in rust, stuurde AlarmMesh wel opnieuw een start. Dat is de bestaande opstartlogica. Een herstart op het bewuste tijdstip is in de installatie van de gebruiker niet vastgesteld.

De screenshot toont de configuratie, niet deze tijdlijn. Voor de zoldermelder zijn de firmware, de actuele `linkage_alarm`-toestand en de beschikbaarheid van de select en terugmeldsensor voldoende om de eerste blokkade te lokaliseren. Deze gegevens kunnen worden bekeken terwijl de melders in rust blijven.

## Als een meeklinkende melder zelf rook detecteert

De Heiman S1-M, S1-TL, S1-TL-AI, S2-E, HM-636THV-AC-M en HS1SA-E Lover gebruiken via Zigbee2MQTT dezelfde aparte instelling voor het meeklinken als de HS1SA-E-PLUS. De driver leest lokale rook via IAS Zone. Start en stop van het meeklinken gebruiken het aparte attribuut deviceCascadeState. Tijdelijk dempen heeft een eigen bediening. Een S1-M die via Matter is aangesloten meldt rook via een ander profiel. [S1-M](https://www.zigbee2mqtt.io/devices/S1-M.html) · [Apparaatdefinities van de zes modellen](https://github.com/Koenkk/zigbee-herdsman-converters/blob/a2573dbbd7b5d28916c9007fd0f9e469b89befde/src/devices/heiman.ts)

**Voorbeeld met twee melders.** De hal meldt rook en de S1-M op zolder krijgt een aanvraag om mee te klinken. Zodra zolder zelf rook meldt, houdt AlarmMesh de stopopdracht tegen. Als de hal weer vrij is en zolder nog rook meldt, blijft die blokkade gelden. Pas als beide melders expliciet vrij zijn, vraagt AlarmMesh één keer om het eigen meeklinken te stoppen. Een ontbrekende rookstatus houdt de stop tegen. Na een herstart, een handmatige stop of ontbrekende of onherleidbare terugmelding neemt AlarmMesh een al lopende toon niet over. De simulatie controleert de berichten die Home Assistant verstuurt. De hoorbare werking per firmware vraagt afzonderlijke praktijkvalidatie.

**Bestaande groepen.** Open na een update naar deze versie **Groepen → Samen afgaan** en bevestig een eerder gekozen doel uit de zes nieuwe modellen opnieuw. De nieuwe bevoegdheid krijgt een andere identificatie. Het bestaande PLUS-profiel blijft geldig.

| Onderzochte melder | Wat bepaalt de keuze? |
| --- | --- |
| Bosch Twinguard 8750001213 | De Zigbee2MQTT-driver combineert bij stop een dempbericht, een bericht om het alarm te wissen en het uitschakelen van het inbraakalarm. Een afzonderlijke stop van alleen het eigen meeklinken is daarmee onvoldoende onderbouwd. [Bosch-driver](https://github.com/Koenkk/zigbee-herdsman-converters/blob/a2573dbbd7b5d28916c9007fd0f9e469b89befde/src/devices/bosch.ts) |
| Bosch Smoke Alarm II (BSD-2) | De driver kiest op basis van een bewaarde stand welke alarmmodus hij stopt. Bij onbekende stand kan hij meerdere modi stoppen. Ook wist hij een timer die meerdere BSD-2-melders delen. De huidige aan/uit-terugmelding geeft AlarmMesh hiervoor onvoldoende zekerheid. [Bosch-alarmbediening](https://github.com/Koenkk/zigbee-herdsman-converters/blob/a2573dbbd7b5d28916c9007fd0f9e469b89befde/src/lib/bosch.ts) |
| Develco SMSZB-120, ook frient 94430 en Cavius 2103 | De handleiding bevestigt dat extern starten geen lokale rookindicatie zet. Zigbee2MQTT documenteert ook een stop. De sirene in Home Assistant houdt echter zelf een aangenomen stand bij en de beschreven stop geeft geen zekerheid over het eigen alarm bij gelijktijdige rook. De bestaande aanvraag heeft een duur van 60 seconden. [Technische handleiding, §4.2.4 en §6.4.3](https://keyfree.no/wp-content/uploads/2023/09/Optiskbrannalarm-smszb-120-technical-manual-Develco.pdf) · [Zigbee2MQTT](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) · [Ontdekking van de HA-sirene](https://github.com/Koenkk/zigbee2mqtt/blob/3c841fdfd66c92239921ef84fde8f039c64e1662/lib/extension/homeassistant.ts#L1400-L1452) |

## Start en stop per model

De [matrix met alle 67 modellen en varianten](device-catalog.md) noemt de start- en stopmogelijkheid van elke variant per integratie. Van de 61 rookmeldervarianten hebben er 19 een startprofiel via Zigbee2MQTT en 9 via ZHA. Zeven Heiman-modellen hebben via Zigbee2MQTT ook een afzonderlijke stop voor eigen meeklinkopdrachten. De overige zes catalogusrijen betreffen twee hittevarianten, twee losse sirenes, een contactapparaat en een akoestische melder. De catalogusdatum 14 november 2026 verwijst naar de broninventaris.

Een koppeling loopt via Home Assistant. Een Aqara kan als rookbron een geschikte Heiman laten meeklinken. In de omgekeerde richting moet de Aqara zelf als doel aan de voorwaarden voldoen. Deze richtingen kunnen dus verschillende mogelijkheden hebben. De catalogustest controleert de model- en providerherkenning, verzamelt de toegestane doelen en berekent de routes in beide richtingen tussen Zigbee2MQTT en ZHA. Voor de radiokoppeling tussen twee fysieke apparaten is afzonderlijk bewijs nodig.

De tabel vergelijkt de 52 apparaatdefinities uit de catalogus met de officiële Zigbee2MQTT-modelpagina’s. Daaronder vallen ook enkele hitte-, geluids- en contactapparaten en losse sirenes. Een streep betekent dat AlarmMesh voor dit apparaat en deze provider geen geverifieerde geluidsopdracht heeft. De ZHA-kolom geldt voor de herkende apparaatidentiteit en de daarbij zichtbare bediening. Een verkoopvariant in dezelfde rij heeft niet automatisch dezelfde ZHA-ondersteuning. Bij “60 s” vraagt AlarmMesh een duur aan. Het toestel bepaalt de feitelijke geluidsduur. Een model met alleen een demp-, alarmvrijgave- of testknop heeft daarmee nog geen geschikte externe sirene. De kolom voor Zigbee2MQTT beschrijft de bediening van het apparaat. De laatste kolom beschrijft welke stopopdracht de integratie daadwerkelijk mag sturen. [Bronbestanden modelpagina’s](https://github.com/Koenkk/zigbee2mqtt.io/tree/b6b32994b3a5f05ca8f5a8e1710ef8a0ea0161b0/docs/devices) · [Register en herkomst per provider](device-catalog.md)

| Model en varianten | Apparaatbediening via Zigbee2MQTT | Start via AlarmMesh met Zigbee2MQTT / ZHA | Automatische stop via AlarmMesh |
| --- | --- | --- | --- |
| [Aqara JY-GZ-01AQ](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html) · Aqara JY-GZ-03AQ | buzzer (alarm / mute) | alarm / aan | — |
| [BYUN M415-6C](https://www.zigbee2mqtt.io/devices/M415-6C.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Bosch 8750001213](https://www.zigbee2mqtt.io/devices/8750001213.html) | alarm (onder meer fire / stop) | fire / — | — |
| [Bosch BSD-2](https://www.zigbee2mqtt.io/devices/BSD-2.html) | alarm control (smoke / burglar / off) | smoke / — | — |
| [CTM Lyng mSwitch_Mic](https://www.zigbee2mqtt.io/devices/mSwitch_Mic.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Climax SD-8SCZBS](https://www.zigbee2mqtt.io/devices/SD-8SCZBS.html) | warning | sirene 60 s / sirene 60 s | — |
| [Develco HESZB-120](https://www.zigbee2mqtt.io/devices/HESZB-120.html) · Frient 94431 | warning | sirene 60 s / sirene 60 s | — |
| [Develco SIRZB-110](https://www.zigbee2mqtt.io/devices/SIRZB-110.html) | warning | — / — | — |
| [Develco SIRZB-111](https://www.zigbee2mqtt.io/devices/SIRZB-111.html) | warning | — / — | — |
| [Develco SMSZB-120](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) · Frient 94430, Cavius 2103 | warning (apparaat documenteert ook OFF) | sirene 60 s / sirene 60 s | — |
| [Feibit SSA01ZB](https://www.zigbee2mqtt.io/devices/SSA01ZB.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [GISE GSKS-ZB](https://www.zigbee2mqtt.io/devices/GSKS-ZB.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [GS SSHM-I1](https://www.zigbee2mqtt.io/devices/SSHM-I1.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Halo Smart Labs HALO](https://www.zigbee2mqtt.io/devices/HALO.html) | hush | — / — | — |
| [Halo Smart Labs HALO+](https://www.zigbee2mqtt.io/devices/HALO+.html) | hush | — / — | — |
| [Heiman HM-636THV-AC-M](https://www.zigbee2mqtt.io/devices/HM-636THV-AC-M.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | Zigbee2MQTT, eigen aanvraag |
| [Heiman HS15A-M](https://www.zigbee2mqtt.io/devices/HS15A-M.html) | warning | sirene 60 s / sirene 60 s | — |
| [Heiman HS1SA-E](https://www.zigbee2mqtt.io/devices/HS1SA-E.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman HS1SA-E Lover](https://www.zigbee2mqtt.io/devices/HS1SA-E_Lover.html) | temporary mute, siren for automation only | rooktoon / — | Zigbee2MQTT, eigen aanvraag |
| [Heiman HS1SA-E-PLUS](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | PLUS via Zigbee2MQTT, eigen aanvraag |
| [Heiman HS2SA-1](https://www.zigbee2mqtt.io/devices/HS2SA-1.html) | silence | — / — | — |
| [Heiman HS2SA-EF-3.0](https://www.zigbee2mqtt.io/devices/HS2SA-EF-3.0.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman HS3SA/HS1SA](https://www.zigbee2mqtt.io/devices/HS3SA_HS1SA.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman S1-M](https://www.zigbee2mqtt.io/devices/S1-M.html) | temporary mute, siren for automation only | rooktoon / — | Zigbee2MQTT, eigen aanvraag |
| [Heiman S1-TL](https://www.zigbee2mqtt.io/devices/S1-TL.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | Zigbee2MQTT, eigen aanvraag |
| [Heiman S1-TL-AI](https://www.zigbee2mqtt.io/devices/S1-TL-AI.html) | temporary mute, siren for automation only | rooktoon / — | Zigbee2MQTT, eigen aanvraag |
| [Heiman S2-E](https://www.zigbee2mqtt.io/devices/S2-E.html) | temporary mute, siren for automation only | rooktoon / — | Zigbee2MQTT, eigen aanvraag |
| [Heimgard Technologies HT-SMO-2](https://www.zigbee2mqtt.io/devices/HT-SMO-2.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Konke TW-S1](https://www.zigbee2mqtt.io/devices/TW-S1.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Moes ZSS-HM-SSD01](https://www.zigbee2mqtt.io/devices/ZSS-HM-SSD01.html) | silence | — / — | — |
| [MultIR MIR-SM200](https://www.zigbee2mqtt.io/devices/MIR-SM200.html) | silence | — / — | — |
| [ONENUO 288WZ](https://www.zigbee2mqtt.io/devices/288WZ.html) | silence | — / — | — |
| [SMaBiT (Bitron Video) AV2010/24](https://www.zigbee2mqtt.io/devices/AV2010_24.html) | warning | sirene 60 s / sirene 60 s | — |
| [SMaBiT (Bitron Video) AV2010/24A](https://www.zigbee2mqtt.io/devices/AV2010_24A.html) | warning | sirene 60 s / sirene 60 s | — |
| [Schneider Electric W599001](https://www.zigbee2mqtt.io/devices/W599001.html) · Schneider Electric 755WSA, Schneider Electric W599501 | hush | — / — | — |
| [ShinaSystem FAM-300Z](https://www.zigbee2mqtt.io/devices/FAM-300Z.html) | force smoke alarm (aan / uit met toestemming) | geforceerd alarm aan / — | — |
| [Slacky-DIY Smoke Sensor TLSR8258](https://www.zigbee2mqtt.io/devices/Smoke_Sensor_TLSR8258.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Trust ZSDR-850](https://www.zigbee2mqtt.io/devices/ZSDR-850.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya 228WZH](https://www.zigbee2mqtt.io/devices/228WZH.html) | silence | — / — | — |
| [Tuya PA-44Z](https://www.zigbee2mqtt.io/devices/PA-44Z.html) | silence | — / — | — |
| [Tuya SA12IZL](https://www.zigbee2mqtt.io/devices/SA12IZL.html) | alarm, silence siren (alarmfunctie in-/uitschakelen) | — / — | — |
| [Tuya TS0205](https://www.zigbee2mqtt.io/devices/TS0205.html) · Tesla Smart TSL-SEN-SMOKE, Dongguan Daying Electornics Technology YG400A, Tuya TS0205_smoke_2, Nedis ZBDS10WT | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya TS0601_smoke_1](https://www.zigbee2mqtt.io/devices/TS0601_smoke_1.html) · Nous E8 | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya TS0601_smoke_3](https://www.zigbee2mqtt.io/devices/TS0601_smoke_3.html) · KnockautX SMOAL024 | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya TS0601_smoke_4](https://www.zigbee2mqtt.io/devices/TS0601_smoke_4.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya TS0601_smoke_5](https://www.zigbee2mqtt.io/devices/TS0601_smoke_5.html) | silence, alarm (alarmfunctie in-/uitschakelen) | — / — | — |
| [Tuya TS0601_smoke_6](https://www.zigbee2mqtt.io/devices/TS0601_smoke_6.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Tuya TS0601_smoke_co](https://www.zigbee2mqtt.io/devices/TS0601_smoke_co.html) · Moes JKD-513COM-Z | silence, alarm switch (alarmfunctie in-/uitschakelen) | — / — | — |
| [Tuya ZSS-QY-SSD-A-EN](https://www.zigbee2mqtt.io/devices/ZSS-QY-SSD-A-EN.html) | silence | — / — | — |
| [Woox R7049](https://www.zigbee2mqtt.io/devices/R7049.html) | test alarm, alarm, silence siren (alarmfunctie in-/uitschakelen) | — / — | — |
| [Xiaomi JTYJ-GD-01LM/BW](https://www.zigbee2mqtt.io/devices/JTYJ-GD-01LM_BW.html) · Xiaomi YTC4020RT | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [eWeLink CK-TLSR8656-SS5-01(7035)](https://www.zigbee2mqtt.io/devices/CK-TLSR8656-SS5-01(7035).html) · eWeLink CK-TLSR8656-Z123SE22DY-01(7035) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |

Een expliciete apparaatopdracht voor stoppen is vooral bij Bosch BSD-2, Bosch Twinguard en de Develco SMSZB-120 interessant voor vervolgonderzoek. Hun providerpagina’s beschrijven respectievelijk `off`, `stop` en een externe `OFF`. Voor toelating tot automatisch stoppen is ook bewijs nodig van het effect wanneer **tijdens het meeklinken eigen rook ontstaat**, van herkomst van het geluid en van terugmelding na de opdracht. De huidige AlarmMesh-profielen sturen deze opdrachten niet. [BSD-2](https://www.zigbee2mqtt.io/devices/BSD-2.html) · [Twinguard](https://www.zigbee2mqtt.io/devices/8750001213.html) · [SMSZB-120](https://www.zigbee2mqtt.io/devices/SMSZB-120.html)

## Matter en Z-Wave in gemengde groepen

Een geldige eigen rookindicatie via Matter of Z-Wave JS kan een groep met bijvoorbeeld Heiman-doelen activeren. In omgekeerde richting moet het doel een eigen gedocumenteerde externe geluidsbediening hebben. Voor de onderzochte Matter-modellen Heiman HS1SA-M, Heiman S1-M, Sensereo MS-1, MSC-1 en MS-1 Interlink heeft AlarmMesh geen dergelijke HA-doelbediening. De interconnect-status beschrijft gekoppeld alarm. De zelftest oefent het toestel. Voor Z-Wave JS heeft AlarmMesh momenteel geen modelprofiel voor starten of stoppen. Een reset van een notificatie, een associatiegroep en een sirene hebben verschillende effecten. [Matter-modelmatrix](matter-support.md) · [Z-Wave-onderbouwing](zwave-support.md)

**Twee Z-Wave-voorbeelden maken het onderscheid concreet.** Bij de POPP POPE004001 documenteert de fabrikant een apart geluidsritme voor de externe sirene en een aan/uit-schakelaar. Dit maakt het een kandidaat voor een gericht AlarmMesh-profiel. Onbevestigd zijn nog de exacte HA-doelentiteit in een passende installatie, terugmelding en wat het toestel doet bij gelijktijdig lokaal rookalarm. De FIBARO FGSD-002-handleiding beschrijft lokale alarmering en uitgaande Z-Wave-berichten. Daaruit volgt geen externe sireneschakelaar voor dat apparaat. [POPP-handleiding bij de Z-Wave Alliance](https://products.z-wavealliance.org/wp-content/uploads/products/50577/POPE004001_en.pdf) · [FIBARO FGSD-002-handleiding](https://manuals.fibaro.com/content/manuals/orange/FGSD-002.pdf)

De standaard Matter Smoke CO Alarm-cluster in de geraadpleegde specificatie biedt een optionele zelftestopdracht. De gekoppelde rookstatus en dempstatus zijn attributen. Een fabrikant kan aanvullende functionaliteit hebben via een andere interface. Voor een AlarmMesh-doel moet die interface per apparaat aantoonbaar bereikbaar zijn in Home Assistant. [Matter-clusterspecificatie, §2.11](https://csa-iot.org/wp-content/uploads/2025/08/3-27350_matter-1-4-2-adopted-application-cluster-specification.pdf)
