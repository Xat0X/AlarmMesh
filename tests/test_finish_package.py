"""Historical update input must never relax the current package inventory."""

import pytest

from dev.release.package import CATALOG_FILES, REQUIRED_FILES, validate_files


def test_previous_catalog_package_is_not_accepted_as_current():
    from pathlib import Path

    root = Path("custom_components/alarmmesh")
    files = {name: (root / name).read_bytes() for name in CATALOG_FILES}
    with pytest.raises(ValueError, match="inventory"):
        validate_files(files)
    assert validate_files(files, catalog=True)["domain"] == "alarmmesh"
    assert set(files) != REQUIRED_FILES
    del files["linking_runtime.py"]
    with pytest.raises(ValueError, match="inventory"):
        validate_files(files, catalog=True)
