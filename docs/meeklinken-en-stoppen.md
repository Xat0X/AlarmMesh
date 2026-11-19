# Welke rookmelders kunnen meeklinken en stoppen?

Onderzoek van 19 november 2026 bij de praktijktest op bèta 15. De gebruiker hoorde meerdere melders opnieuw afgaan. Het tijdstip en de afzender van een eventuele tweede opdracht zijn onbekend. De onderstaande mogelijkheden zijn ontleend aan apparaatdocumentatie, de code en tests met gesimuleerde apparaten.

## De melders uit de test

| Melder via Zigbee2MQTT | Bij rook op een andere melder | Wanneer kan AlarmMesh hem stoppen? |
| --- | --- | --- |
| Heiman HS1SA-E-PLUS | Een aangevinkte melder kan de opdracht `smoke_siren` krijgen op `siren_for_automation_only`. | Met `stop` op diezelfde bediening, zodra alle betrokken bronnen en de doelmelder zelf geen rook meer melden. AlarmMesh moet de start zelf hebben aangevraagd, de bediening nog herkennen en voldoende terugmelding hebben. |
| Aqara JY-GZ-01AQ, ook verkocht als JY-GZ-03AQ | De keuze `alarm` op `buzzer` vraagt geluid aan als de melder zelf geen rook waarneemt en `linkage_alarm` aan staat. De aparte sensor `buzzer_manual_alarm` geeft de toestand van het handmatig geactiveerde geluid. | Het toestel gebruikt `mute` om dit geluid te stoppen. Dezelfde keuze kan bij lokale rook het eigen alarm circa 80 seconden dempen. Er kan rook ontstaan tussen een HA-statuscontrole en ontvangst van de opdracht. AlarmMesh biedt daarom alleen starten aan voor deze route. |

Op de Heiman kan de fysieke knop het lokale geluid dempen terwijl de rookindicatie aan blijft. Zigbee2MQTT beschrijft de demptijd en het exacte heralarmgedrag van de PLUS als onbevestigd. Bij Aqara kan ook `linkage_alarm_state` uitgaan na handmatig dempen. Deze waarden zijn geen bewijs dat alle betrokken bronnen weer vrij zijn. [Heiman](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html) · [Aqara](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html)

Bèta 15 controleerde bij Aqara de stand van de schrijfkeuze zelf. Zigbee2MQTT publiceert daarvoor geen toestand. De lokale correctie controleert de afzonderlijke terugmelding van hetzelfde apparaat. De opdrachtkeuze moet beschikbaar zijn met de opties `alarm` en `mute`. Bij firmware 21 geldt de bestaande blokkade. Een eerder opgeslagen Aqara-keuze moet na deze wijziging eenmalig opnieuw worden bevestigd. [Zigbee2MQTT-apparaatdefinitie](https://github.com/Koenkk/zigbee-herdsman-converters/blob/master/src/devices/lumi.ts) · [HA-ontdekking in Zigbee2MQTT](https://github.com/Koenkk/zigbee2mqtt/blob/master/lib/extension/homeassistant.ts)

## Wat doet de blueprint anders?

De blueprint zoekt geluidsbedieningen bij de gekozen apparaten en controleert de beschikbare opties. Tijdens de alarmfase wacht ze onder meer op een dempschakelaar, de sensor voor handmatig dempen of de keuze `mute`. Zo'n signaal, een expliciete actie vanuit een telefoonmelding of het verdwijnen van de rook kan een herhaalde dempcyclus starten. Daarmee verklaart de code waarom de groep bij een eerdere test anders kon reageren. De beschikbare sensoren verschillen per apparaat. [Onderzochte blueprintversie](https://github.com/Xat0X/Smart-Smoke-System-The-Ultimate-Firealarm-Linker/blob/c665b6ad32f3beed8d0d833dd4023f37e84f463e/xat0x-smoke-linker-ultimate.yaml)

## Wat in Home Assistant is gereproduceerd

Dezelfde vijf scenario’s zijn in een geïsoleerde Home Assistant-omgeving afgespeeld op de gepubliceerde bèta 15 en op de lokale correctie. Bij bèta 15 faalden twee controles. Een werkende Aqara met een onbekende schrijfkeuze en expliciete rustterugmelding kon niet als doel worden opgeslagen. Bij een Heiman PLUS kon AlarmMesh de latere stop missen als een andere statusupdate binnenkwam tussen de startaanvraag en de bijbehorende terugmelding. Met de correctie slaagden alle vijf scenario’s. Na een kort vertraagde, aan de startaanvraag herkenbare terugmelding stuurde de integratie bij het vrijgeven van de bron één stop. Een latere geluidsmelding van onbekende herkomst gaf geen recht om dat geluid te stoppen.

Een fysieke druk op de bronknop levert daarmee nog geen groepsstop op. Het verschil tussen een lokaal gedempt alarm, een beëindigde rookmelding en een ontvangen groepsstop blijft van belang bij het lezen van de tijdlijn.

## Het incident achteraf bekijken

1. Noteer in de Home Assistant-geschiedenis het tijdstip van de eerste rookmelding, het drukken op de knop en de tweede geluidsronde. Bekijk voor **iedere** melder de eigen rookstatus. Noteer ook `unknown` of `unavailable` en een eventuele herstart of herlaadactie.
2. Leg de aanvragen in AlarmMesh-activiteiten naast dat tijdvak. Kijk bij Heiman ook naar de automatiseringssirene en de dempstatus. Kijk bij Aqara naar de terugmeldingen voor handmatig alarm en handmatig dempen. De laatst gekozen waarde van de schrijfbediening bewijst geen geluid.
3. Controleer in het automatiseringsoverzicht of de oude blueprint of een andere automatisering voor deze melders ingeschakeld was en of daar rond hetzelfde tijdstip een trace bestaat. Een tweede AlarmMesh-start, een nieuwe rookovergang, een start na herladen en hernieuwd geluid zonder geregistreerde HA-opdracht vragen elk om een andere verklaring. Ontbrekende logregels sluiten een opdracht buiten HA niet uit.

In de simulator bleef een handmatig gestopte doelmelder stil zolang dezelfde rookmelding doorliep. Na het herladen van de integratie, met dezelfde rookbron nog aan en het doel in rust, stuurde AlarmMesh wel opnieuw een start. Dat is de bestaande opstartlogica. Een herstart op het bewuste tijdstip is in de installatie van de gebruiker niet vastgesteld.

De screenshot toont de configuratie, niet deze tijdlijn. Voor de zoldermelder zijn de firmware, de actuele `linkage_alarm`-toestand en de beschikbaarheid van de select en terugmeldsensor voldoende om de eerste blokkade te lokaliseren. Deze gegevens kunnen worden bekeken terwijl de melders in rust blijven.

## Start en stop per model

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
| [Heiman HM-636THV-AC-M](https://www.zigbee2mqtt.io/devices/HM-636THV-AC-M.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | — |
| [Heiman HS15A-M](https://www.zigbee2mqtt.io/devices/HS15A-M.html) | warning | sirene 60 s / sirene 60 s | — |
| [Heiman HS1SA-E](https://www.zigbee2mqtt.io/devices/HS1SA-E.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman HS1SA-E Lover](https://www.zigbee2mqtt.io/devices/HS1SA-E_Lover.html) | temporary mute, siren for automation only | rooktoon / — | — |
| [Heiman HS1SA-E-PLUS](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | PLUS via Zigbee2MQTT, eigen aanvraag |
| [Heiman HS2SA-1](https://www.zigbee2mqtt.io/devices/HS2SA-1.html) | silence | — / — | — |
| [Heiman HS2SA-EF-3.0](https://www.zigbee2mqtt.io/devices/HS2SA-EF-3.0.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman HS3SA/HS1SA](https://www.zigbee2mqtt.io/devices/HS3SA_HS1SA.html) | Geen afzonderlijke geluidsbediening gevonden | — / — | — |
| [Heiman S1-M](https://www.zigbee2mqtt.io/devices/S1-M.html) | temporary mute, siren for automation only | rooktoon / — | — |
| [Heiman S1-TL](https://www.zigbee2mqtt.io/devices/S1-TL.html) | temporary mute, siren for automation only | rooktoon / sirene 60 s | — |
| [Heiman S1-TL-AI](https://www.zigbee2mqtt.io/devices/S1-TL-AI.html) | temporary mute, siren for automation only | rooktoon / — | — |
| [Heiman S2-E](https://www.zigbee2mqtt.io/devices/S2-E.html) | temporary mute, siren for automation only | rooktoon / — | — |
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
