# Independent review: critical alerts and saved choices

18 November 2026. Working tree based on beta.11, commit
`7061cd0c17122e53c717708080fb78557551c9fa`. No commit or publication.

## Finding and correction

The phone-settings readback compared persisted settings with the earlier submitted
snapshot. If the user edited the form before/during readback, it incorrectly said
those visible choices were saved. The same success text remained after later edits.

Three new frontend regressions first failed (105 PASS, 3 FAIL). Readback now compares
with the current form at completion; subsequent input invalidates the success text.
Choices remain visible and no save or delivery is repeated. All 108 frontend tests
pass. Existing confirmation/reconnect locking is retained.

## Independently executed checks

- Full validation `config/validation/561ef8f1454648668438c937950919ca/`:
  586 backend tests, 105 then-existing frontend tests, Ruff/format, hassfest,
  PowerShell, Compose and both HA 2026.10.4/2026.11.1 compatibility checks PASS.
- After correction: `node --test dev/frontend/panel.test.mjs`, 108 PASS;
  `config/plain-language-review/independent-before.log` and `independent-after.log`.
  Backend behavior was not changed by this correction; panel.py only changes the
  frontend asset cache key.
- Mixed critical iOS/Android profiles through the simulator UI: quiet save, exact
  critical sound/volume vs Android alarm_stream/high/ttl=0, separate confirmed
  mock tests, explicit failure, timeout without repeat, lost save response.
  Fresh rerun output: `config/plain-language-review/flows.json`.
- Full beta.11 regression browser flow rerun: two fake phones, ordinary incident
  and recovery, missing service, stale confirmation, smoke in form, actual browser
  disconnect, same-request readback and no duplicate. Evidence:
  `config/plain-language-review/beta11-regression-flows.json`.
- Three new browser scenarios with real server save, intentionally discarded reply,
  browser offline/reconnect, and edits before/during/after readback: PASS.
  `config/independent-critical-review/readback.json` and screenshots.
- User routes: group creation with outputs off, saved mock recipient, cancellation,
  draft resume, unavailable detector help, recovery preparation, reconnect and
  keyboard focus return: PASS; `config/independent-critical-review/usability.json`.
- Eight NL/EN x light/dark x phone/tablet combinations regenerated and actually
  visually inspected using settings/iOS/Android contact sheets. Individual Dutch
  phone, recovery, overview, corrected readback and reflow captures also inspected.
  `config/independent-critical-review/matrix.json` and `screenshots/`.
- `git diff --check` PASS; status.py and tests/test_status.py unchanged from HEAD.

The platform payloads were compared with the official Companion documentation:
https://companion.home-assistant.io/docs/notifications/critical-notifications/

## Scope and limitations

Simulator identity/labels, localhost-only port 8131, integration mounts and fake
notify handlers were inspected before tests. Only mobile_app_simulated_phone_a/b
were used. No real phone, smoke detector, production HA or external script used.

The visual matrix overrides panel language; the outer HA shell remains Dutch.
Long names/empty states are browser fixtures. Reflow is a 512x384 CSS viewport,
not native zoom or screenreader acceptance. Source replacement was prepared,
not executed anew in this review. Audible delivery, permissions, imported sounds
and phone Do Not Disturb remain physical acceptance tasks, not proven by mocks.
No hosted CI run was triggered.

Final simulator state: 5 sources off, all 107 helpers off, no groups, notifications,
maintenance, reminders and linking off. No running self-test; an older unknown
self-test result remains unknown. See `config/independent-critical-review/final-state.json`.

## Changes introduced by this review

- frontend/panel.js: compare current form and invalidate readback text on edits.
- frontend/translations.js: concise NL/EN explanation for edited form.
- panel.py: asset cache key only.
- dev/frontend/panel.test.mjs: three regression cases.
- CHANGELOG.md and this review report.

All other pre-existing local changes were retained. Simulator evidence is ignored
by Git. Nothing was committed, pushed, tagged or released.
