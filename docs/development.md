# Development

## Supported development environment

Use Linux with Python 3.14 (Docker, a VS Code development container, or WSL).
Home Assistant development and this test suite run on Linux; native Windows
execution is not the supported validation path. Python on Windows may still be
used for editing or simple syntax checks.

The test harness is pinned to `pytest-homeassistant-custom-component==0.13.375`,
which pins `homeassistant==2026.10.4`. This is the tested baseline, not a claim
that every later Home Assistant version is already verified. `hacs.json` declares
the same minimum. Update the harness and minimum deliberately and rerun checks.
Direct developer tools are pinned; their transitive dependencies are not a full
lockfile. The devcontainer Python image follows the 3.14 tag.

Open the repo in the supplied development container, or run on Linux:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
```

In the supplied container, the environment and dependencies are created by
`postCreateCommand`; run the last three checks from a terminal. No Home Assistant
server starts automatically. To reproduce via Docker from PowerShell:

```powershell
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/workspace,readonly" -w /workspace -e PYTHONDONTWRITEBYTECODE=1 python:3.14-bookworm sh -c 'python -m pip install -r requirements-dev.txt && python -m ruff check --no-cache . && python -m ruff format --check --no-cache . && python -m pytest -p no:cacheprovider'
```

## What the checks establish

Tests run real Home Assistant flow and entry APIs using the custom-integration
fixtures: opening and confirming the form, empty entry data, duplicate rejection,
two open dialogs, setup, unload, reload, removal, and the two read-only overview
entities. Tests cover local source changes, availability, stable entity identity,
disabled entities and setup-failure cleanup. AlarmMesh creates no devices or
services. Packaging and translation tests supplement these.
Network sockets are disabled during tests except Unix sockets required by the
local test runtime. No test controls hardware.

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

Keep any disposable Home Assistant instance configuration in the ignored `config/`
directory. Never commit `.storage`, credentials, `secrets.yaml`, logs, databases,
or real device/account data. The development container does not mount a live
Home Assistant configuration or expose hardware. LF line endings are normalized
by `.gitattributes` for Windows/Linux collaboration.
