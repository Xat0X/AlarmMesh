# Reproducible technical compatibility checks

**Technical checks with simulated sources, not physical-device validation.**
The development harness and default remain **HA 2026.10.4**. An explicit version
parameter also permits **exactly 2026.11.1**; other versions are rejected. This
does not change dependencies, minimum metadata or product code. CI adds a
separate compatibility job while retaining the pinned baseline tests.

Current local and hosted outcomes are in the [acceptance matrix](acceptance-matrix.md);
the independent CI matrix uses the [complete validation route](development.md#complete-local-validation).
The new local [linked-sounding extension](linked-sounding.md) adds three checks
to the existing runner (17 total), using mock HA controls and registry metadata.
Its evidence is recorded separately from the historical read-only results below.
The historical results below are retained as dated evidence; base `0e7ba38`
already includes those changes and the supplied branding.

## Run from a fresh checkout or reviewed working tree

From the repository root in PowerShell, with Docker Desktop running:

```powershell
$ErrorActionPreference = 'Stop'
docker pull ghcr.io/home-assistant/home-assistant:2026.10.4
docker pull ghcr.io/home-assistant/home-assistant:2026.11.1
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Check
if ($LASTEXITCODE -ne 0) { throw 'Baseline check failed' }
& .\dev\mvp-acceptance\mvp-acceptance.ps1 -Action Check -HaVersion 2026.11.1
if ($LASTEXITCODE -ne 0) { throw 'Compatibility check failed' }
```

The script throws on failures; when called from a fresh `powershell -File` or
`pwsh -File` process this gives a nonzero process exit. An assertion/configuration
failure is never a successful run. In a shell that continues after errors, check
the invocation's success or use `$ErrorActionPreference = 'Stop'`. Python checks
also return nonzero on failure and remain active under optimized Python.

Every run copies the tracked YAML examples to a newly allocated
`config/compatibility/<version>/<run-id>/` (ignored by Git), without accounts,
old helper states or `.storage`. It does not read or alter the existing
`config/mvp-acceptance/` web configuration. It mounts only the new configuration,
the integration, check tooling and mock fixture read-only. No published port, host
networking, privileged mode, hardware or Docker socket is used. The uniquely
named `alarmmesh-compat-…` containers and their labelled **internal Docker
network** are removed after the run; generated evidence remains. Networkless HA
can fail in its own network components, so `--network none` is not used.

The selected official image and both in-container version checks use the same
parameter. Compose validation, HA `check_config`, actual bootstrap and config/
options flows run before PASS. The runtime refuses a pre-existing `.storage`.
The examples contain only local helpers, template smoke sensors and mock controls; no
onboarding, account, real HA or direct device connection is needed.

## Scenarios and result files

Each run records requested/actual HA version, HEAD commit, working-tree change
indicator, relevant local paths and scenario outcomes. `compatibility-result.json`
is the overall result; `technical-result.json` contains the runtime detail.
Per-phase logs stay locally ignored. Summaries contain no account/configuration
contents or exception text. Do not publish raw local logs without review.
Failure identifies the phase/scenario and exception type; a fresh rerun is used
after correction, not reuse of the failed configuration.

For CI or an orchestrator, `-ReportPath <new-json-file>` exports just the overall
sanitized summary; its parent must exist and the file must not already exist.
The result must match this run's ID, version and commit, with all scenarios PASS.
Cleanup failure also makes the overall result FAIL and the process exit nonzero.
Original runtime tracebacks and host/cleanup failures stay in private local logs,
which are never uploaded by the matrix job. Each matrix version runs independently
with read-only repository permissions and a bounded timeout.

| Scenario | Required observation |
| --- | --- |
| Version and fresh config | Actual HA equals requested version; no old storage |
| Configure two sources | Real config flow creates and loads AlarmMesh |
| Exactly two overviews | One smoke binary sensor, one availability sensor, no device |
| Both off | Smoke `off`, availability `complete` |
| Smoke on | Smoke `on` |
| Smoke with source outage | Smoke `on`, availability `incomplete` |
| No smoke with outage | Smoke `unavailable`, never `off` |
| Source recovery | Current `off` / `complete` restored |
| Real options flow | Selection saved and entry reloaded through HA's API |
| Old source ignored | Old source changes cannot alter the new result or old runtime |
| Reload identity | Registry ID, unique ID and entity ID remain stable; current state retained |
| Unload and cleanup | Successful unload; old source/result subscriptions no longer update |
| Verified linking profiles | Exact mock MQTT/ZHA identities, controls and prerequisites |
| Mixed linking and failed target | Real group API confirmation, independent bounded mock actions, no mute |
| Linking stop and reload cleanup | Ownership-limited Heiman stop, stable identities and closed old executor |

The check observes AlarmMesh's existing shared calculation and entity states;
it introduces no substitute status calculation or product API. It does not
replace [manual UI acceptance](mvp-acceptance.md), simulate a full production
restart, or validate physical devices. Two focused CLI tests cover unsupported
versions and loaded-version mismatch with nonzero exits, without starting HA.

## Recorded result — 2026-11-11

| Requested HA | Actual HA | Configuration | All 12 technical scenarios |
| --- | --- | --- | --- |
| 2026.10.4 | 2026.10.4 | PASS | PASS |
| 2026.11.1 | 2026.11.1 | PASS | PASS |

Tested repository base: **1c9aae2c4d0fc21329369efe3d5ddddc64d26571** plus local
changes to `dev/mvp-acceptance/check_runtime.py` and `mvp-acceptance.ps1` in this
package. Tracked product code is unchanged. Working tree was explicitly reported
dirty; the final reports also list independently added, untracked
`custom_components/alarmmesh/brand/` assets present during those runs. Those
assets and `assets/branding/` were not created or changed by this package and
were left untouched. These results are not attributed to a new committed
revision. The earlier temporary 2026.11.1 check is superseded by these runs.

Retained local overall reports (ignored by Git):

- `config/compatibility/2026.10.4/e7f92000c1694083b9dc8f4e58d13022/compatibility-result.json`
- `config/compatibility/2026.11.1/895b6fa192d64536b81d62f1032f45f1/compatibility-result.json`

The original **233 tests** pass on the pinned Linux baseline. With the two new
tooling tests the full suite has **235 tests**. Automated results are distinct
from the user-reported [real-device pilot](read-only-pilot.md).

| Additional check on 2026-11-11 | Result |
| --- | --- |
| Linux Python 3.14.10 / HA 2026.10.4, full pytest suite | PASS, 235 tests (233 unchanged + 2 tooling tests) |
| Ruff 0.17.4 lint and format check | PASS, 27 Python files formatted |
| PowerShell parser | PASS |
| Unsupported PowerShell version parameter | Rejected, process exit 1 as expected |
| Compose configuration | PASS |
| Official hassfest container | PASS, 1 integration, 0 invalid |
| Git whitespace, protected tracked files and privacy review | PASS for this package; independent untracked branding assets excluded |

The Python failure tests confirm exits 2 (unsupported version) and 1 (loaded
version mismatch, FAIL report). No failed assertion is counted as acceptance.

No check issues device commands. Do not point this tooling at a real HA
configuration. It never stops, restarts or recreates the separate web acceptance
container; existing web lifecycle commands remain documented separately.
