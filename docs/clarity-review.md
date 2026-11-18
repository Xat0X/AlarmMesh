# Interface clarity review — 18 November 2026

Local changes after beta.13, based on the user's screenshots.

## Changes

- Detector rows show a battery percentage from existing device diagnostics. Zero remains zero. Missing, nonnumeric or out-of-range values are unknown. A low-battery warning remains available without a percentage. Changed source identities do not display a misleading percentage.
- Both alarm-route views use the same phone cards: selected phones first, including unavailable selections; unused phones in a collapsed counted list. Display names are readable, exact service IDs remain under technical details. Critical mode/sound is visible when configured. No claim of actual receipt is derived from readiness.
- Group sound controls now say Do not sound along / Also sound when smoke is detected elsewhere, with Dutch equivalents. The help explains that smoke reporting and the detector's own smoke alarm remain unaffected. Technical provider details and stop limitations remain accessible.
- Five setup entries replace seven. Group organization, linked sound and scripts share one destination, retaining their separate server assessments. Settings likewise has one Groups and actions card.
- No execution, permission, notification payload, stored identity, or save/reconnect logic changed. Only the panel asset cache identifier changed in Python. Status calculation and the 79 status tests are unchanged. Manifest remains beta.13.

## Verification

Three targeted tests failed before implementation and passed afterwards. Existing layout/copy assertions were updated for five entries and four settings cards; behavioral assertions remain. The frontend suite passes 120 tests. Full isolated validation also passes 602 backend tests, Ruff/format, hassfest, PowerShell/Compose, cleanup and HA 2026.10.4 / 2026.11.1 compatibility. Two local packages contain 43 files each and have identical SHA-256 `66835469234e836264fb054882530adc61b0c41f7661642fa240b0b8197ae433`.

[Browser results](../config/clarity-review/browser-results.json): the actual simulator read-only route was exercised first. Then presentation fixtures cover selected, unavailable and unselected phones and battery values 87, 12, 0, missing-with-low-warning and 55. All eight NL/EN × light/dark × phone/tablet combinations were rendered and inspected. Both role options were selected in unsaved forms. There were no page errors, output requests or saved settings changes.

- [Detector screens](../config/clarity-review/screenshots/contact-devices.jpg)
- [Phone screens](../config/clarity-review/screenshots/contact-phones.jpg)
- [Combined setup](../config/clarity-review/screenshots/contact-setup.jpg)
- [Sound roles](../config/clarity-review/screenshots/contact-role.jpg)
- [Full isolated validation](../config/validation/82a48280836a44ba89d1d6993912b49b/validation-result.json)

The browser matrix uses presentation fixtures for the alternative phone/battery states; this is not physical device or phone validation. Language is a panel browser override; themes use the HA theme event. Screenshots were actually inspected. No native screenreader or native zoom test is claimed.

No real phone, detector or production installation was contacted. The simulator remains with automatic output off. Nothing committed, pushed, tagged or published.
