"""Check packaging and the texts shipped with the custom integration."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "alarmmesh"


def test_packaging_metadata() -> None:
    """HACS receives exactly one self-contained integration with matching domain."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text("utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text("utf-8"))
    integrations = [
        path.name
        for path in (ROOT / "custom_components").iterdir()
        if path.is_dir() and not path.name.startswith("__")
    ]
    assert integrations == ["alarmmesh"]
    assert manifest["domain"] == INTEGRATION.name
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["requirements"] == []
    assert all(
        manifest[key]
        for key in ("name", "version", "documentation", "issue_tracker", "codeowners")
    )
    assert hacs["render_readme"] is True
    assert not hacs.get("content_in_root", False)


def test_translation_keys() -> None:
    """Every shipped language contains the confirmation and duplicate texts."""
    strings = json.loads((INTEGRATION / "strings.json").read_text("utf-8"))
    english = json.loads((INTEGRATION / "translations" / "en.json").read_text("utf-8"))
    assert english == strings
    for path in (INTEGRATION / "translations").glob("*.json"):
        translated = json.loads(path.read_text("utf-8"))
        assert translated["title"] == "AlarmMesh"
        assert translated["config"]["step"]["user"]["title"]
        assert translated["config"]["step"]["user"]["description"]
        assert translated["config"]["abort"]["already_configured"]
