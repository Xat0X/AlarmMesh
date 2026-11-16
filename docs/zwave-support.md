# Z-Wave JS smoke sources

AlarmMesh uses existing Home Assistant Z-Wave JS smoke binary sensors. Add a detector in HA first, then select its smoke entity in AlarmMesh integration options. No additional AlarmMesh dependencies, MQTT bridge, controller connection, inclusion or network changes are needed.

Support is based on the original device class supplied by HA, not a product name. This covers models for which HA actually exposes a smoke binary sensor, including unknown models. It is not a claim that every Z-Wave product or feature works. CO, heat, test/diagnostic and manually relabelled non-smoke entities cannot become smoke sources. Old invalid selections remain unknown instead of producing a smoke incident.

Z-Wave smoke sources participate in the existing overview, rooms, mixed groups, maintenance, activities, reminders and phone/script incident handling. Automatic functions remain opt-in. Z-Wave is a source provider; this implementation adds no Z-Wave sounder targets. No actions run merely by opening details or adding a detector.

Battery percentage, low-battery and problem flags are read only from enabled entities with original HA battery/problem classes, on the exact same HA device and config entry. Endpoint parent/child devices are not traversed. Multiple valid battery values use the minimum; a positive problem flag wins. Missing, unavailable or invalid values stay unknown. A problem flag may concern the overall HA device, not a particular smoke chamber. Cached timestamps are not proof of recent radio contact.

Remote sounding, stopping, silencing and self-test have no verified Z-Wave route in this version. Buttons named ping, idle/reset notification or self-test do not grant command authority. Network associations and native interconnect are not configured or certified by AlarmMesh. Consult the detector's own instructions for manual testing and native linking.

## Evidence and limits

- [Official HA Z-Wave JS integration](https://www.home-assistant.io/integrations/zwave_js/)
- [HA smoke/CO/diagnostic binary sensor mapping](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/zwave_js/binary_sensor.py)
- [HA Z-Wave buttons: ping and notification idle](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/zwave_js/button.py)

The simulator creates an ignored registry-only Z-Wave owner and five explicit virtual helpers. It starts no Z-Wave JS client/controller and operates no physical devices. Automated registry tests and browser checks do not prove physical detection, audible sound, radio interoperability or phone delivery. No physical Z-Wave model has been validated here.
