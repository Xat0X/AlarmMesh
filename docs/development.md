# Development

## Supported development environment

Use Linux with Python 3.14 (Docker, a VS Code development container, or WSL).
Home Assistant development and this test suite run on Linux; native Windows
execution is not the supported validation path. Python on Windows may still be
used for editing or simple syntax checks.

The test harness is pinned to `pytest-homeassistant-custom-component==0.13.375`,
which pins `homeassistant==2026.10.4`. This is the tested baseline, not a claim
that every later Home Assistant version is already verified. `hacs.json` declares
the same minimum. Separate [technical compatibility checks](compatibility.md)
also verify exact **2026.11.1** without changing the harness or baseline. Update
the harness and minimum deliberately and rerun checks.
Direct developer tools are pinned; their transitive dependencies are not a full
lockfile. The devcontainer Python image follows the 3.14 tag.

## Complete local validation

From a clean checkout, run **PowerShell 7** with Git and Docker Desktop (Linux
containers), or PowerShell 7 on a Linux Docker host:

```powershell
pwsh -NoProfile -File ./dev/validate.ps1
```

This is the single complete validation route. It parses the PowerShell scripts,
runs focused wrapper-failure tests and Compose validation, installs the unchanged
requirements in Linux Python 3.14, runs Ruff lint/format and the full pytest
suite, runs official hassfest, then invokes the existing compatibility runner for
**2026.10.4** and **2026.11.1**. Independent checks continue after a failure, but
any failed check or cleanup makes the overall result FAIL and the process exit
nonzero. No execution-policy change is needed or made; use the supported shell
and do not bypass an organization policy.

The same route now also runs the packaged panel's DOM tests with exact
**Node 24.22.1**, `npm ci --ignore-scripts` and the committed
`dev/frontend/package-lock.json`. The sole direct frontend test dependency is
Linkedom 0.18.15. It is development-only; no Node/npm dependency, build output
generation or CDN belongs on the HA host. The product ships native ES modules
and CSS under `custom_components/alarmmesh/frontend/`. For a quick local pass:

```sh
npm ci --prefix dev/frontend --ignore-scripts --no-audit --no-fund
npm test --prefix dev/frontend
```

These tests exercise the actual component's navigation, safe text rendering,
push/disconnect lifecycle, group forms/conflicts and Dutch/English context.
Linkedom has no layout engine/native modal implementation: it is not proof of
phone/tablet layout, contrast or native keyboard focus. Use the separate
[panel simulation](panel.md#local-simulation-and-evidence) for those observations.
The Python fixture substitutes only the missing upstream UI-wheel filesystem
root in the pip HA harness; real HTTP routes, panel registration, WebSocket auth,
HA registries and group storage remain in use. Official image runs use their
real bundled frontend and now check **17** scenarios, including authenticated
panel subscription/group mutations, asset serving, persistent groups, verified
mock control profiles, mixed-provider failure isolation and linking cleanup.
The [linking simulation](linked-sounding.md#reproduce-the-simulation) uses mock
HA action handlers and registry metadata, never an MQTT/ZHA driver or radio.

The first run needs network access for container images and Python dependencies.
Generated `validation-result.json`, per-version sanitized summaries, JUnit XML and
private logs remain in ignored `config/validation/<run-id>/`. Compatibility runs
have their own fresh ignored configuration and internal network. Only exact
run-owned containers/networks are removed. Neither the existing web acceptance
instance nor other projects are used. Review logs locally; only sanitized
compatibility summaries are suitable for CI artifacts. A run's JSON identifies
its HEAD commit and individual checks; it is not a published release.

The existing CI test/hassfest jobs remain; an independent `fail-fast: false`
matrix now calls that same compatibility runner with exact versions. The matrix
uses read-only source/tool mounts, fresh configuration, no published port and
per-run internal networking. Only an explicitly new summary file in runner temp
is uploaded, even after failure; storage, accounts, databases and raw logs are
excluded. Hosted execution for exact a300d39 (244 tests) and bbd767a (249 tests)
was verified on 2026-11-12, including both downloaded compatibility artifacts for
each commit. See the [current acceptance matrix](acceptance-matrix.md).
New local changes still require their own separately authorized hosted run.

The baseline/hassfest containers receive a read-only export of Git-visible files,
including local review changes, rather than the entire working directory. Ignored
web accounts/configuration and `.git` are not mounted. The export stays under the
ignored validation run for local reproduction; it is never a CI upload target.

For a quick subset while editing, open the supplied development container or run
on Linux:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
```

In the supplied container, the environment and dependencies are created by
`postCreateCommand`; run the last three checks from a terminal. No Home Assistant
server starts automatically. For the complete Docker route, use `dev/validate.ps1`
above rather than mounting a working directory containing ignored account data.

## What the checks establish

Tests run real Home Assistant flow and entry APIs using the custom-integration
fixtures: opening and confirming the form, empty entry data, duplicate rejection,
two open dialogs, setup, unload, reload, removal, and the two read-only overview
entities. Tests cover local source changes, availability, stable entity identity,
disabled entities and setup-failure cleanup. AlarmMesh creates no devices or
services. Packaging and translation tests supplement these.
Network sockets are disabled during tests except Unix sockets required by the
local test runtime. No test controls hardware.

The earlier baseline had 235 tests. Seven packaged-image/HA serving tests and
two failure/privacy tests brought a300d39 to **244 tests**, confirmed on GitHub.
bbd767a adds five package-integrity cases, for **249 tests**. All 244
existing tests and assertions, including the 79 pure status tests, remain unchanged.
The new local interface adds backend and packaging regressions after that dated
249-test baseline; its actual final count and results are recorded separately in
the [acceptance matrix](acceptance-matrix.md). Old hosted CI does not cover this code.
Wrapper fault checks
add configuration failure, stale-report rejection, cleanup failure and an
existing output path without requiring Docker or another testing dependency.
Passing pytest on 2026.10.4 is not evidence for another HA version; the complete
route runs both image-based checks separately.

For release preparation, [package/file-update checks](release-package.md) reuse
the same simulation YAML and real HA APIs in additional disposable process runs.
They supplement the single standard validation route with package, replacement
and stopped-file recovery evidence; they are not an alternate pytest system or
installer/HA-backup acceptance. Current outcomes are recorded only in the matrix.

## Restart and failure regression coverage

The earlier suites already cover initial smoke, missing/reappearing sources,
single selection changes, overview identity/customizations, repeated reloads,
and recovery from failures injected into either overview platform's setup.
`tests/test_resilience.py` adds focused step-5 cases without changing production
code or weakening the existing assertions:

| Area | Additional fixture proof |
| --- | --- |
| Restart | Stop one HA instance, read saved config entries and registry through base bootstrap in a new HA instance, preserve custom names/IDs, and use current source states |
| Source registry | Rename/remove an actual simulated HA entity, keep the selected ID fixed as `MISSING`, then explicitly select the new ID through options |
| Options | Repeated swaps and switch-back, save an unavailable source using registry metadata, and reject/cancel edits during active smoke without interrupting tracking |
| Disabled lifecycle | Disable/re-enable the integration; reload with both overviews disabled, then let HA's existing re-enable delay reload them |
| Unload boundary | Change a source during platform teardown; check no old-runtime updates or duplicate processing after unload/reload |
| Failed unload | Inject both False and an exception in a platform's unload, assert `FAILED_UNLOAD` and its reason, retain only the surviving platform, and recover in a new storage-bootstrapped HA instance |
| Unchanged reports | Advance fixture time without changing a source; no arbitrary stale-report threshold turns an explicit off report into a fault |

HA 2026.10.4 rejects in-process reload from `FAILED_UNLOAD`. The regression tests
assert that restriction, rather than forcing entry state or patching HA's recovery
policy. Resolving the fault and restarting HA is the tested recovery route. The
new-instance tests are restart simulations using storage/setup fixtures, not real
process restarts. Manual UI and physical-device validation remain separate and
were not performed for this step.

The GitHub workflow runs lint, format, tests, and official hassfest on push or PR.
Hassfest checks Home Assistant metadata and translations independently of pytest.
To run the official custom-integration validator locally with Docker:

```powershell
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/github/workspace,readonly" ghcr.io/home-assistant/hassfest:latest
```

These checks prove the foundation contract, not real alarm behavior. A manual UI
check in an isolated Home Assistant instance is still useful to inspect translated
texts and remove/re-add the integration; it is separate from automated tests.

## Local Home Assistant files

For a reproducible isolated UI test, use the [MVP acceptance guide and result
list](mvp-acceptance.md). Public examples and guarded start/stop commands are in
`dev/mvp-acceptance/`. The web container publishes only `127.0.0.1:8124` and mounts
the repository integration read-only. Runtime/account data stays under the
already ignored `config/mvp-acceptance/`. Technical checks, a real container
restart and manual UI acceptance are reported separately. Onboarding requires
the user's account input. After user onboarding, the twelve UI scenarios were
executed on 2026-11-11; the guide records observations and remaining scope limits.

`mvp-acceptance.ps1 -Action Check` defaults to **2026.10.4** and accepts an explicit
`-HaVersion 2026.11.1`. Only those two versions are allowed; the version parameter
does not change the web environment. Each technical run uses a new ignored
`config/compatibility/<version>/<run-id>/`, a dedicated internal network, no web
port and read-only product code. It never reads the web instance's account or
storage. Commands, scenarios and reports are in [compatibility](compatibility.md).
For a script syntax check without Docker:

```powershell
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path 'dev/mvp-acceptance/mvp-acceptance.ps1'),
    [ref]$null, [ref]$parseErrors) | Out-Null
if ($parseErrors) { throw ($parseErrors | Out-String) }
```

Use the [installation guide](installation.md) for Marketplace versus older HACS
installation. The [pilot register](read-only-pilot.md) separates user reports from
simulated checks and defines passive follow-up; no live access is part of these
developer commands.

Keep any disposable Home Assistant instance configuration in the ignored `config/`
directory. Never commit `.storage`, credentials, `secrets.yaml`, logs, databases,
or real device/account data. The development container does not mount a live
Home Assistant configuration or expose hardware. LF line endings are normalized
by `.gitattributes` for Windows/Linux collaboration.


## Device catalog and realistic driver checks

[Device support and current evidence](device-compatibility.md) records the complete
inventory method, canonical/variant counts and provider-specific limits. The
reviewed snapshot is `dev/catalog/review.json`; `python dev/catalog/build.py`
generates the runtime literal and model index. `--check` and the catalog regression
tests reject stale output. The development-only `extract.cjs` reproduces the
website filter from pinned official sources; run it only in an ignored research
folder and review differences before changing capabilities.

The single validation route also runs the real HA MQTT/offline ZHA driver phase
on both exact compatibility versions. Official Mosquitto 2.0.22 is development
software, not an installed integration dependency. Its container has no published
port, owns no credentials, uses only synthetic topics on the run's internal
network, and is removed with the run. No coordinator, production broker, radio or
real source is used. Inspect `driver-result.json` separately from mock registry
results. Local tracebacks stay ignored; a failed assertion or cleanup fails the
whole run. Existing web environments remain untouched.

For the separate 16-detector catalog UI fixture:

```powershell
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Catalog -Port 8130 -Action Start
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Catalog -Port 8130 -Action Status
pwsh -NoProfile -File ./dev/panel-ui.ps1 -Mode Catalog -Port 8130 -Action Stop
```

Use only those clearly labelled helpers; no cloud/account connection is needed.
The fixture is mock provider metadata/actions, not the real MQTT driver phase.
It starts with all helpers off. After a review return helpers off and leave
linking off. Runtime/account data stays ignored under `config/catalog-ui/`.
The launcher's existing bridge has outbound access, not LAN-firewall semantics.
Visual access may require user onboarding; never substitute DOM tests for actual
phone/tablet/theme/keyboard observations. The completed representative native UI
review and its limits are recorded in the device support guide.
