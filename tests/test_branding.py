"""Packaged image requirements and actual HA serving, not visual UI acceptance."""

from pathlib import Path

import pytest
from PIL import Image
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.alarmmesh.const import DOMAIN

BRAND = Path(__file__).resolve().parents[1] / "custom_components/alarmmesh/brand"
IMAGES = (
    "icon.png",
    "icon@2x.png",
    "logo.png",
    "logo@2x.png",
    "dark_logo.png",
    "dark_logo@2x.png",
)


@pytest.mark.parametrize("filename", IMAGES)
def test_packaged_png_requirements(filename: str) -> None:
    """Catch corrupt, padded, opaque or incorrectly sized delivered assets."""
    with Image.open(BRAND / filename) as image:
        assert image.format == "PNG"
        image.verify()
    with Image.open(BRAND / filename) as image:
        alpha = image.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        assert alpha.getbbox() == (0, 0, *image.size)
        doubled = "@2x" in filename
        if filename.startswith("icon"):
            size = 512 if doubled else 256
            assert image.size == (size, size)
        else:
            low, high = (256, 512) if doubled else (128, 256)
            assert low <= min(image.size) <= high
            assert image.width > image.height


async def test_ha_serves_local_brand_images(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Authenticated HA fixture serves exact local PNG bytes, never a placeholder."""
    assert await async_setup_component(hass, "brands", {})
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.has_branding, str(integration.file_path)
    client = await hass_client()
    for filename in IMAGES:
        response = await client.get(
            f"/api/brands/integration/{DOMAIN}/{filename}?placeholder=no"
        )
        assert response.status == 200
        assert response.content_type == "image/png"
        assert await response.read() == (BRAND / filename).read_bytes()
