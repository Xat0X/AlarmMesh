"""Closed package inventory and deterministic output; no HA or devices."""

import json
import zipfile
from pathlib import Path

import pytest

from dev.release.package import REQUIRED_FILES, validate_files, write_zip

ROOT = Path(__file__).resolve().parents[1] / "custom_components/alarmmesh"


@pytest.fixture
def files() -> dict[str, bytes]:
    return {name: (ROOT / name).read_bytes() for name in REQUIRED_FILES}


@pytest.mark.parametrize(
    "extra", ["../secrets.yaml", ".storage/auth", "__pycache__/status.pyc"]
)
def test_package_rejects_unreviewed_files(files: dict[str, bytes], extra: str) -> None:
    files[extra] = b"must never be packaged"
    with pytest.raises(ValueError, match="inventory"):
        validate_files(files)


def test_package_rejects_missing_runtime_file(files: dict[str, bytes]) -> None:
    del files["runtime.py"]
    with pytest.raises(ValueError, match="inventory"):
        validate_files(files)


def test_package_rejects_unreviewed_builtin_dependency(files: dict[str, bytes]) -> None:
    manifest = json.loads(files["manifest.json"])
    manifest["dependencies"].append("shell_command")
    files["manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="manifest"):
        validate_files(files)


def test_package_is_repeatable_and_exact(
    files: dict[str, bytes], tmp_path: Path
) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert write_zip(files, first) == write_zip(
        dict(reversed(list(files.items()))), second
    )
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == REQUIRED_FILES
        assert all(archive.read(name) == content for name, content in files.items())
    with pytest.raises(FileExistsError):
        write_zip(files, first)
