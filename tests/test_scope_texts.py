"""Both installation forms explain opt-in effects without obsolete scope claims."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("language", ["en", "nl"])
@pytest.mark.parametrize("flow,step", [("config", "user"), ("options", "init")])
def test_scope_text_keeps_optional_effects_and_confirmation_visible(
    language, flow, step
):
    root = Path("custom_components/alarmmesh")
    source = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    translated = json.loads(
        (root / "translations" / f"{language}.json").read_text(encoding="utf-8")
    )
    if language == "en":
        assert source == translated
    text = translated[flow]["step"][step]["description"].lower()
    expected = (
        [
            "smoke reports",
            "source information",
            "optional",
            "mobile notifications",
            "incident actions",
            "panel",
            "off by default",
            "supported devices",
            "separate confirmation",
            "not a guarantee of safety",
        ]
        if language == "en"
        else [
            "rookmeldingen",
            "broninformatie",
            "optioneel",
            "gsm-meldingen",
            "incidentacties",
            "paneel",
            "standaard uit",
            "ondersteunde apparaten",
            "afzonderlijke bevestiging",
            "geen veiligheidsgarantie",
        ]
    )
    assert all(claim in text for claim in expected)
    assert "no notifications or device tests" not in text
    assert "geen notificaties of apparaattests" not in text
    assert translated[flow]["step"][step]["data_description"]["source_entity_ids"]
