"""Build a deterministic local test ZIP, never publish or choose release metadata."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

INTEGRATION = "custom_components/alarmmesh"
FOUNDATION_FILES = frozenset(
    {
        "__init__.py",
        "binary_sensor.py",
        "config_flow.py",
        "const.py",
        "entity.py",
        "runtime.py",
        "sensor.py",
        "status.py",
        "manifest.json",
        "strings.json",
        "translations/en.json",
        "translations/nl.json",
        "brand/icon.png",
        "brand/icon@2x.png",
        "brand/logo.png",
        "brand/logo@2x.png",
        "brand/dark_logo.png",
        "brand/dark_logo@2x.png",
    }
)
REQUIRED_FILES = FOUNDATION_FILES | {
    "capabilities.py",
    "linking.py",
    "linking_runtime.py",
    "groups.py",
    "panel.py",
    "frontend/panel.js",
    "frontend/panel.css",
    "frontend/translations.js",
}


def git(repo: Path, *arguments: str) -> bytes:
    """Read repository data without changing refs, index or working files."""
    return subprocess.run(
        ["git", "-C", str(repo), *arguments], capture_output=True, check=True
    ).stdout


def validate_files(files: dict[str, bytes], *, legacy: bool = False) -> dict:
    """Fail closed on missing/unreviewed files and wrong installation metadata."""
    if set(files) != (FOUNDATION_FILES if legacy else REQUIRED_FILES):
        raise ValueError(
            "Integration file inventory differs from the reviewed allowlist"
        )
    manifest = json.loads(files["manifest.json"])
    if (
        manifest.get("domain") != "alarmmesh"
        or manifest.get("config_flow") is not True
        or manifest.get("single_config_entry") is not True
        or manifest.get("requirements") != []
        or manifest.get("dependencies", [])
        != ([] if legacy else ["frontend", "http", "websocket_api"])
        or not all(
            manifest.get(key)
            for key in (
                "name",
                "version",
                "documentation",
                "issue_tracker",
                "codeowners",
            )
        )
    ):
        raise ValueError("Invalid or unexpected AlarmMesh manifest")
    if json.loads(files["translations/en.json"]) != json.loads(files["strings.json"]):
        raise ValueError("English translation and source strings differ")
    json.loads(files["translations/nl.json"])
    return manifest


def write_zip(files: dict[str, bytes], path: Path, *, legacy: bool = False) -> str:
    """Use fixed metadata/order and stored bytes for cross-platform repeatability."""
    validate_files(files, legacy=legacy)
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(files):
            raise ValueError("Written package failed archive validation")
        if any(archive.read(name) != content for name, content in files.items()):
            raise ValueError("Written package differs from source")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(repo: Path, output: Path, revision: str | None = None) -> dict:
    """Inventory only Git-visible reviewed files, or bytes from an exact commit."""
    repo = repo.resolve()
    output = output.resolve()
    relative_output = output.relative_to(repo).as_posix()
    # A fixed ignored root prevents artifacts accidentally becoming repository data.
    if not relative_output.startswith("config/release-packages/"):
        raise ValueError(
            "Output must be a new directory under config/release-packages/"
        )
    subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", relative_output],
        check=True,
    )
    commit = (
        git(repo, "rev-parse", "--verify", f"{revision or 'HEAD'}^{{commit}}")
        .decode()
        .strip()
    )
    if revision:
        paths = git(repo, "ls-tree", "-rz", "--name-only", commit, "--", INTEGRATION)
    else:
        paths = git(
            repo,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            INTEGRATION,
        )
    files = {}
    for encoded in paths.split(b"\0"):
        if not encoded:
            continue
        source_name = encoded.decode("utf-8")
        name = source_name.removeprefix(INTEGRATION + "/")
        if name not in REQUIRED_FILES:
            raise ValueError("Unreviewed file in integration inventory")
        if revision:
            files[name] = git(repo, "show", f"{commit}:{source_name}")
        else:
            source = repo / source_name
            if source.is_symlink() or not source.resolve().is_relative_to(
                repo / INTEGRATION
            ):
                raise ValueError("Symlink or escaped integration source")
            files[name] = source.read_bytes()
    # Explicit old inventory is allowed only for an exact historical Git build.
    # Working-tree builds must always contain the complete reviewed panel payload.
    legacy = bool(revision and set(files) == FOUNDATION_FILES)
    manifest = validate_files(files, legacy=legacy)
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "alarmmesh.zip"
    digest = write_zip(files, archive, legacy=legacy)
    changes = (
        []
        if revision
        else git(repo, "status", "--porcelain", "--untracked-files=all")
        .decode()
        .splitlines()
    )
    inventory = {
        "classification": (
            "local test package; not a published or distribution-approved release"
        ),
        "base_commit": commit,
        "source": "git revision" if revision else "Git-visible working files",
        "local_changes": changes,
        "manifest_version": manifest["version"],
        "layout": "integration-root ZIP; extract into custom_components/alarmmesh/",
        "package": archive.name,
        "sha256": digest,
        "files": [
            {
                "path": name,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(files.items())
        ],
    }
    (output / "inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "package": str(archive.relative_to(repo)),
                "sha256": digest,
                "files": len(files),
            }
        )
    )
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--revision", help="Optional earlier Git commit, resolved to a full SHA"
    )
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[2], args.output, args.revision)
