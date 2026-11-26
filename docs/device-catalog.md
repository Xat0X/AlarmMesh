# Device catalog index

Generated from [the reviewed snapshot](../dev/catalog/review.json). Use [the guide](device-compatibility.md) or the panel for filters and limits.

55 canonical definitions covering 70 website model/variant rows. Every row has separate A-F assessments for both providers. A listed action depends on eligible HA entities and confirmation. Physical validation: zero. ZHA standard IAS routes are conditional, not a claim that every signature creates a siren.

Read each direction separately. Start with a selected HA smoke source, then look up the receiving detector and its provider below. Heat, relay, acoustic and siren rows have different roles. Stop applies only to an eligible AlarmMesh-owned linked sounder.

| Vendor / model | Kind | MQTT detection | MQTT start / stop | ZHA detection | ZHA start / stop |
| --- | --- | --- | --- | --- | --- |
| [Alecto SMART-SMOKE10](https://www.zigbee2mqtt.io/devices/SMART-SMOKE10.html) | smoke | documented | — / — | unconfirmed | — / — |
| [Aqara JY-GZ-01AQ](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html) | smoke | documented | aqara_mqtt / — | conditional | aqara_zha / — |
| [Aqara JY-GZ-03AQ](https://www.zigbee2mqtt.io/devices/JY-GZ-01AQ.html) | smoke | documented | aqara_mqtt / — | conditional | — / — |
| [AVATTO ZSD20](https://www.zigbee2mqtt.io/devices/ZSD20.html) | smoke | documented | — / — | unconfirmed | — / — |
| [BYUN M415-6C](https://www.zigbee2mqtt.io/devices/M415-6C.html) | contact_proxy | documented | — / — | conditional | — / — |
| [Bosch 8750001213](https://www.zigbee2mqtt.io/devices/8750001213.html) | smoke | documented | bosch_twinguard_mqtt / — | conditional | — / — |
| [Bosch BSD-2](https://www.zigbee2mqtt.io/devices/BSD-2.html) | smoke | documented | bosch_bsd_mqtt / — | conditional | — / — |
| [CTM Lyng mSwitch_Mic](https://www.zigbee2mqtt.io/devices/mSwitch_Mic.html) | acoustic | documented | — / — | conditional | — / — |
| [Climax SD-8SCZBS](https://www.zigbee2mqtt.io/devices/SD-8SCZBS.html) | smoke | documented | ias_mqtt / — | conditional | ias_zha / — |
| [Develco HESZB-120](https://www.zigbee2mqtt.io/devices/HESZB-120.html) | heat | documented | ias_mqtt / — | conditional | basic_ias_zha / — |
| [Frient 94431](https://www.zigbee2mqtt.io/devices/HESZB-120.html) | heat | documented | ias_mqtt / — | conditional | — / — |
| [Develco SIRZB-110](https://www.zigbee2mqtt.io/devices/SIRZB-110.html) | siren | not_available | — / — | not_available | — / — |
| [Develco SIRZB-111](https://www.zigbee2mqtt.io/devices/SIRZB-111.html) | siren | not_available | — / — | not_available | — / — |
| [Develco SMSZB-120](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) | smoke | documented | smszb_mqtt / — | conditional | smszb_zha / — |
| [Frient 94430](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) | smoke | documented | smszb_mqtt / — | conditional | — / — |
| [Cavius 2103](https://www.zigbee2mqtt.io/devices/SMSZB-120.html) | smoke | documented | smszb_mqtt / — | conditional | — / — |
| [Feibit SSA01ZB](https://www.zigbee2mqtt.io/devices/SSA01ZB.html) | smoke | documented | — / — | conditional | — / — |
| [GISE GSKS-ZB](https://www.zigbee2mqtt.io/devices/GSKS-ZB.html) | smoke | documented | — / — | conditional | — / — |
| [GS SSHM-I1](https://www.zigbee2mqtt.io/devices/SSHM-I1.html) | smoke | documented | — / — | conditional | — / — |
| [Halo Smart Labs HALO](https://www.zigbee2mqtt.io/devices/HALO.html) | smoke | documented | — / — | conditional | — / — |
| [Halo Smart Labs HALO+](https://www.zigbee2mqtt.io/devices/HALO+.html) | smoke | documented | — / — | conditional | — / — |
| [Heiman HM-636THV-AC-M](https://www.zigbee2mqtt.io/devices/HM-636THV-AC-M.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | basic_ias_zha / — |
| [Heiman HS15A-M](https://www.zigbee2mqtt.io/devices/HS15A-M.html) | smoke | documented | ias_mqtt / — | conditional | ias_zha / — |
| [Heiman HS1SA-E](https://www.zigbee2mqtt.io/devices/HS1SA-E.html) | smoke | documented | — / — | conditional | — / — |
| [Heiman HS1SA-E Lover](https://www.zigbee2mqtt.io/devices/HS1SA-E_Lover.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | — / — |
| [Heiman HS1SA-E-PLUS](https://www.zigbee2mqtt.io/devices/HS1SA-E-PLUS.html) | smoke | documented | heiman_mqtt / stop | conditional | basic_ias_zha / — |
| [Heiman HS2SA-1](https://www.zigbee2mqtt.io/devices/HS2SA-1.html) | smoke | documented | — / — | conditional | — / — |
| [Heiman HS2SA-EF-3.0](https://www.zigbee2mqtt.io/devices/HS2SA-EF-3.0.html) | smoke | documented | — / — | conditional | — / — |
| [Heiman HS3SA/HS1SA](https://www.zigbee2mqtt.io/devices/HS3SA_HS1SA.html) | smoke | documented | — / — | conditional | — / — |
| [Heiman S1-M](https://www.zigbee2mqtt.io/devices/S1-M.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | — / — |
| [Heiman S1-TL](https://www.zigbee2mqtt.io/devices/S1-TL.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | basic_ias_zha / — |
| [Heiman S1-TL-AI](https://www.zigbee2mqtt.io/devices/S1-TL-AI.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | — / — |
| [Heiman S2-E](https://www.zigbee2mqtt.io/devices/S2-E.html) | smoke | documented | heiman_cascade_mqtt / stop | conditional | — / — |
| [Heimgard Technologies HT-SMO-2](https://www.zigbee2mqtt.io/devices/HT-SMO-2.html) | smoke | documented | — / — | conditional | — / — |
| [Konke TW-S1](https://www.zigbee2mqtt.io/devices/TW-S1.html) | smoke | documented | — / — | conditional | — / — |
| [Moes ZSS-HM-SSD01](https://www.zigbee2mqtt.io/devices/ZSS-HM-SSD01.html) | smoke | documented | — / — | conditional | — / — |
| [MultIR MIR-SM200](https://www.zigbee2mqtt.io/devices/MIR-SM200.html) | smoke | documented | — / — | conditional | — / — |
| [ONENUO 288WZ](https://www.zigbee2mqtt.io/devices/288WZ.html) | smoke | documented | — / — | conditional | — / — |
| [SMaBiT (Bitron Video) AV2010/24](https://www.zigbee2mqtt.io/devices/AV2010_24.html) | smoke | documented | ias_mqtt / — | conditional | ias_zha / — |
| [SMaBiT (Bitron Video) AV2010/24A](https://www.zigbee2mqtt.io/devices/AV2010_24A.html) | smoke | documented | ias_mqtt / — | conditional | ias_zha / — |
| [Schneider Electric W599001](https://www.zigbee2mqtt.io/devices/W599001.html) | smoke | documented | — / — | conditional | — / — |
| [Schneider Electric 755WSA](https://www.zigbee2mqtt.io/devices/W599001.html) | smoke | documented | — / — | conditional | — / — |
| [Schneider Electric W599501](https://www.zigbee2mqtt.io/devices/W599001.html) | smoke | documented | — / — | conditional | — / — |
| [ShinaSystem FAM-300Z](https://www.zigbee2mqtt.io/devices/FAM-300Z.html) | smoke | documented | shina_mqtt / — | conditional | — / — |
| [Slacky-DIY Smoke Sensor TLSR8258](https://www.zigbee2mqtt.io/devices/Smoke_Sensor_TLSR8258.html) | smoke | documented | — / — | conditional | — / — |
| [Sunricher SR-ZG9070A-SS](https://www.zigbee2mqtt.io/devices/SR-ZG9070A-SS.html) | smoke | documented | — / — | unconfirmed | — / — |
| [Trust ZSDR-850](https://www.zigbee2mqtt.io/devices/ZSDR-850.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya 228WZH](https://www.zigbee2mqtt.io/devices/228WZH.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya PA-44Z](https://www.zigbee2mqtt.io/devices/PA-44Z.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya SA12IZL](https://www.zigbee2mqtt.io/devices/SA12IZL.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0205](https://www.zigbee2mqtt.io/devices/TS0205.html) | smoke | documented | — / — | conditional | — / — |
| [Tesla Smart TSL-SEN-SMOKE](https://www.zigbee2mqtt.io/devices/TS0205.html) | smoke | documented | — / — | conditional | — / — |
| [Dongguan Daying Electornics Technology YG400A](https://www.zigbee2mqtt.io/devices/TS0205.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0205_smoke_2](https://www.zigbee2mqtt.io/devices/TS0205.html) | smoke | documented | — / — | conditional | — / — |
| [Nedis ZBDS10WT](https://www.zigbee2mqtt.io/devices/TS0205.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_1](https://www.zigbee2mqtt.io/devices/TS0601_smoke_1.html) | smoke | documented | — / — | conditional | — / — |
| [Nous E8](https://www.zigbee2mqtt.io/devices/TS0601_smoke_1.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_3](https://www.zigbee2mqtt.io/devices/TS0601_smoke_3.html) | smoke | documented | — / — | conditional | — / — |
| [KnockautX SMOAL024](https://www.zigbee2mqtt.io/devices/TS0601_smoke_3.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_4](https://www.zigbee2mqtt.io/devices/TS0601_smoke_4.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_5](https://www.zigbee2mqtt.io/devices/TS0601_smoke_5.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_6](https://www.zigbee2mqtt.io/devices/TS0601_smoke_6.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya TS0601_smoke_co](https://www.zigbee2mqtt.io/devices/TS0601_smoke_co.html) | smoke | documented | — / — | conditional | — / — |
| [Moes JKD-513COM-Z](https://www.zigbee2mqtt.io/devices/TS0601_smoke_co.html) | smoke | documented | — / — | conditional | — / — |
| [Tuya ZSS-QY-SSD-A-EN](https://www.zigbee2mqtt.io/devices/ZSS-QY-SSD-A-EN.html) | smoke | documented | — / — | conditional | — / — |
| [Woox R7049](https://www.zigbee2mqtt.io/devices/R7049.html) | smoke | documented | — / — | conditional | — / — |
| [Xiaomi JTYJ-GD-01LM/BW](https://www.zigbee2mqtt.io/devices/JTYJ-GD-01LM_BW.html) | smoke | documented | — / — | conditional | — / — |
| [Xiaomi YTC4020RT](https://www.zigbee2mqtt.io/devices/JTYJ-GD-01LM_BW.html) | smoke | documented | — / — | conditional | — / — |
| [eWeLink CK-TLSR8656-SS5-01(7035)](https://www.zigbee2mqtt.io/devices/CK-TLSR8656-SS5-01(7035).html) | smoke | documented | — / — | conditional | — / — |
| [eWeLink CK-TLSR8656-Z123SE22DY-01(7035)](https://www.zigbee2mqtt.io/devices/CK-TLSR8656-SS5-01(7035).html) | smoke | documented | — / — | conditional | — / — |

## Matter (separate provider review)

The counts above cover the Zigbee2MQTT inventory, including the reviewed model-specific smoke properties. Matter evidence uses the same snapshot; no entry authorizes a sounder. See [Matter capability matrix](matter-support.md).

| Model | Region / variant | HA route |
| --- | --- | --- |
| Heiman HS1SA-M | Europe / China; do not substitute Zigbee HS1SA-E | Smoke + optional endpoint-scoped information / conditional self-test button; no sounder |
| Heiman S1-M | USA; S1-TM is a separate model | Smoke + optional endpoint-scoped information / conditional self-test button; no sounder |
| Sensereo MS-1 | Original MS-1; not MS-1 Interlink | Smoke + optional endpoint-scoped information / conditional self-test button; no sounder |
| Sensereo MSC-1 | Smoke portion only; CO remains separate | Smoke + optional endpoint-scoped information / conditional self-test button; no sounder |
| Sensereo MS-1 Interlink | Separate July 2026 variant; native Interlink is not AlarmMesh permission | Smoke + optional endpoint-scoped information / conditional self-test button; no sounder |
