"""Fail-closed CLI checks for compatibility tooling; no HA instance is started."""

import json
import subprocess
import sys
from pathlib import Path

from homeassistant.const import __version__

SCRIPT = Path(__file__).resolve().parents[1] / "dev/mvp-acceptance/check_runtime.py"


def test_unsupported_version_rejected(tmp_path: Path) -> None:
    """An unreviewed version must fail argument parsing before any setup."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ha-version",
            "stable",
            "--config",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert not (tmp_path / "technical-result.json").exists()
    assert not (tmp_path / ".storage").exists()


def test_image_version_mismatch_is_failure(tmp_path: Path) -> None:
    """A wrong loaded HA version produces a FAIL report and nonzero exit code."""
    assert __version__ == "2026.10.4"  # This suite stays on the pinned baseline.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ha-version",
            "2026.11.1",
            "--config",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads((tmp_path / "technical-result.json").read_text("utf-8"))
    assert report["result"] == "FAIL"
    assert report["requested_ha_version"] == "2026.11.1"
    assert report["actual_ha_version"] == __version__
    assert report["error_type"] == "AssertionError"
    assert report["scenarios"]["version_and_fresh_config"] == "FAIL"
    assert set(report["scenarios"].values()) == {"FAIL", "NIET UITGEVOERD"}
    assert not (tmp_path / ".storage").exists()


def test_previous_success_cannot_survive_reused_configuration(tmp_path: Path) -> None:
    """Old storage and a PASS file must become a fresh nonzero FAIL, before setup."""
    (tmp_path / ".storage").mkdir()
    output = tmp_path / "technical-result.json"
    output.write_text('{"result": "PASS", "run_id": "old"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads(output.read_text("utf-8"))
    assert report["result"] == "FAIL"
    assert report["run_id"] is None
    assert report["scenarios"]["version_and_fresh_config"] == "FAIL"
    traceback = (tmp_path / "failure-traceback.log").read_text("utf-8")
    assert "Configuration is not fresh" in traceback
    assert "Configuration is not fresh" not in result.stdout + result.stderr


def test_original_failure_is_local_and_summary_is_sanitized(tmp_path: Path) -> None:
    """Missing run metadata retains the original traceback without public paths."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads((tmp_path / "technical-result.json").read_text("utf-8"))
    assert report["result"] == "FAIL"
    assert report["error_type"] == "FileNotFoundError"
    assert "run-context.json" in (tmp_path / "failure-traceback.log").read_text("utf-8")
    assert str(tmp_path) not in result.stdout + result.stderr
