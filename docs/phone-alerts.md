# Telefoonmeldingen bij rook

Lokale wijziging bovenop 0.1.0-beta.11; manifestversie blijft gelijk.
Gewone meldingen komen volgens de gebruiker aan, maar zijn niet hoorbaar in de
stille stand. Dit is gebruikersrapportage, geen live inspectie van een telefoon.

## Instellen in vijf minuten

1. Open **Instellingen > Telefoonmeldingen instellen** in AlarmMesh. Kies de telefoons.
2. Open hun geluidsinstellingen. Controleer iPhone of Android. AlarmMesh gebruikt
   een unieke Companion-registratie wanneer beschikbaar, nooit een gok op basis
   van de naam. Zonder zulke metadata kies je zelf het platform.
3. Kies desgewenst **Kritieke melding bij rook**. Op iPhone kun je geluid en volume
   kiezen. `Default` is het standaard telefoongeluid; 0% volume is stil.
4. Open **Waarom hoor ik niets?** en controleer de afzonderlijke telefoonstappen.
5. Controleer de samenvatting en sla op. Opslaan en de tekstpreview verzenden niets.
   **Testmelding voorbereiden** toont eerst het voorbeeld. Alleen de afzonderlijk
   bevestigde knop **Testmelding versturen** vraagt een bericht aan.
   Een test kan geluid maken. Deze ontwikkelopdracht heeft alleen mocks gebruikt.

Automatische incidentmeldingen en ontvangerkeuzes zijn afzonderlijk. Nieuwe
kritieke profielen worden nooit automatisch ingeschakeld. Bewaar voor een
terugkeer naar beta.11 een pre-updatebackup: beta.11 kent de nieuwe profielvelden
niet en mag ze niet als gewone melding herinterpreteren. Bestaande gewone
meldingen behouden hun instellingen. Opslaan tijdens bestaande rook verstuurt
geen inhaalmelding; een nieuwe rookgebeurtenis kan wel een melding veroorzaken.
Herstel, onderhoud en herinneringen gebruiken geen kritisch rookalarmprofiel.

## iPhone

Sta in de iPhone-instellingen meldingen en **kritieke meldingen** voor Home
Assistant toe. Tijdgevoelige meldingen zijn een andere toestemming. AlarmMesh
kan niet controleren of deze toestemming is verleend of het geluid is gehoord.
De geluidslijst bevat default en drie in de Companion-broncode aangetroffen
Engelstalige Alexa-rookmeldingen. De keuken- en garagevariant noemen letterlijk
die ruimte: kies ze alleen als die tekst bij jouw bronnen past. Aanwezigheid op
het toestel is niet bewezen. Een geavanceerde bestandsnaam werkt alleen nadat
het geluid zelf in Companion is geimporteerd; systeemgeluiden zijn niet
standaard geimporteerd. AlarmMesh levert of speelt geen audiobestanden af.

## Android

Controleer Home Assistant > Instellingen > Companion app > Meldingskanalen en
het kanaal `alarm_stream`. Controleer afzonderlijk het kanaalgeluid, alarmvolume
(en dus niet alleen beltoonvolume) en Niet storen. Menu's verschillen per toestel.
Het kanaal kan pas na de eerste ontvangen aanvraag zichtbaar worden. AlarmMesh
verwijdert of hermaakt het kanaal niet en verandert geen telefoonvolume.
Een toestel dat een melding niet direct kan ontvangen, kan deze missen: `ttl: 0`
bewaart de melding niet voor latere aflevering. Er is geen TTS-route toegevoegd.

## Uitkomsten begrijpen

- Door Home Assistant verwerkt: de dienstaanvraag is afgerond; ontvangst of
  hoorbaar geluid is niet bewezen.
- Uitkomst onbekend: de wachttijd is verlopen of de verbinding is onderbroken.
  AlarmMesh herhaalt de aanvraag niet automatisch. Bij reconnect wordt de
  bestaande aanvraagstatus opgehaald.
- Telefoon gewijzigd: controleer de opgeslagen keuze. Een ongeldig profiel wordt
  geblokkeerd, niet stilzwijgend een gewone melding.
- Zonder unieke registratie is de binding sessiegebonden; na een herstart of
  dienstvervanging is opnieuw beoordelen nodig. Instellingen worden niet gewist.

Laatste testaanvragen staan tijdens de runtime per ontvanger; begrensde activiteit
blijft de historische bron na herstart. Er bestaat geen automatisch vastgesteld
bewijs van geluid, toestemming of fysieke rookdetectie.

## Onderzoek en contracten (gecontroleerd 2026-11-17)

| Onderwerp | Officiele bron | Toepassing en grens |
|---|---|---|
| Kritiek op iOS/Android | [Companion critical notifications](https://companion.home-assistant.io/docs/notifications/critical-notifications/) | iOS `push.sound` met naam, critical=1 en volume 0-1; Android high/ttl=0/alarm_stream. Geen bewijs van telefoonrechten. |
| Geluiden | [Notification sounds](https://companion.home-assistant.io/docs/notifications/notification-sounds/) | Import en exacte bestandsnaam; geen browservoorbeluistering. |
| Meegeleverde bronbestanden | [iOS Sounds op gecontroleerde commit](https://github.com/home-assistant/iOS/tree/ac2896d2f14a0e80d18e612eef7633d06b5be501/Sources/App/Resources/Sounds/Alexa) | `US-EN-Alexa-Smoke-Detected-Generic.wav`, `US-EN-Alexa-Smoke-Detected-In-Kitchen.wav`, `US-EN-Alexa-Smoke-Detected-In-Garage.wav`. Broncode-aanwezigheid, niet geinspecteerd toestel. |
| Normale meldingen en kanalen | [Basic notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic/) | Bestaande Companion-dienst; Android kanaalinstellingen blijven van de gebruiker. |
| Links en aanvullende velden | [Notification details](https://companion.home-assistant.io/docs/notifications/notification-details/) | Android clickAction, iOS url; geen ongedocumenteerde instellingen-deeplink. |
| App en toestemming | [Getting started](https://companion.home-assistant.io/docs/getting_started/) | Eigen HA Companion-installatie nodig; geen eigen telefoon-tokenopslag. |
| TTL=0 | [Firebase message lifespan](https://firebase.google.com/docs/cloud-messaging/customize-messages/setting-message-lifespan) | Niet direct afleverbare berichten worden niet bewaard. |
| Registratiemetadata | [Core 2026.11.1 mobile_app notify](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/mobile_app/notify.py) | Unieke device_name/dienst-koppeling plus os_name; identiteit gebonden aan registratie. Geen webhook of token gekopieerd. |

De payload is lokaal getest via Home Assistants echte notify-servicelaag met een
nagebootste eindtransportfunctie. De inmiddels gerapporteerde iPhone-test staat
hieronder apart. Zelfstandige controle van telefoonaflevering, stilte, Niet
storen, volume en hoorbaarheid blijft afzonderlijke fysieke acceptatie.
Zie [review en bewijs](critical-notification-review.md).

## Zelf een test waarnemen

Bij Instellingen en Incidenten staat **Tests die je zelf hebt beoordeeld**. Open de
concrete aanvraag en leg ontvangen en gehoord afzonderlijk vast, of laat een
antwoord op niet gecontroleerd staan. Dit verzendt niets en verandert geen
telefoonrechten of automatische instellingen. Een HA-aanvraag die is verwerkt
is op zichzelf geen bewijs van ontvangst of hoorbaarheid.

De registratie bewaart datum en het gebruikte profiel. Een gewijzigd platform,
kritieke instelling, geluid, volume of ontvangeridentiteit maakt die eerdere
waarneming niet actueel voor de nieuwe instelling. Historie blijft zichtbaar
binnen de begrensde bewaarruimte: 100 aanvragen, vijf waarnemingen per aanvraag,
30 dagen zichtbaar; opschonen gebeurt bij laden of schrijven. Wijzigingen in
telefoonrechten kan AlarmMesh niet vanzelf zien. Na een verloren opslagantwoord
kun je teruglezen wat is opgeslagen; opnieuw verzenden gebeurt niet automatisch.

De gebruiker meldt inmiddels een geslaagde kritieke melding op zijn iPhone met
de geteste instellingen. Dat is gebruikersrapportage, geen zelfstandige controle
en geen bewijs voor Android, andere iPhones, alle geluiden of Focus/Niet storen.
Er wordt hierdoor geen telefoon automatisch als getest gemarkeerd.
Zie de [actuele lokale review en rondleiding](alarm-settings-review.md).
