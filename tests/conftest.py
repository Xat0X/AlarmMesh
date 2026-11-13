"""Home Assistant fixtures for custom integration tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load this repository's custom integration."""


@pytest.fixture(autouse=True)
def frontend_test_assets(tmp_path):
    """HA's pip test harness omits its UI wheel; keep real frontend setup/APIs.

    Only the upstream bundle's filesystem root is substituted. AlarmMesh assets,
    HTTP authentication, WebSocket handlers and panel registration are real.
    Actual HA images test the shipped frontend separately.
    """
    with patch(
        "homeassistant.components.frontend._frontend_root", return_value=tmp_path
    ):
        yield
