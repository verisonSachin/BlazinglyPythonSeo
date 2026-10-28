"""Differential tests: our INI parser must agree with PHP 8.5 on every real file.

These run the local ``php`` binary. They are the gate that lets the rest of the
backend trust settings, locations and test metadata without re-deriving PHP's
parser rules by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.phpini import parse_ini_file

from .helpers import ini_files, php_parse_ini

FILES = ini_files()


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_matches_php_flat(path: Path) -> None:
    expected = php_parse_ini(path, sections=False)
    # PHP represents an empty result as [] rather than {}; both are empty maps.
    assert parse_ini_file(path, process_sections=False) == (expected or {})


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_matches_php_sections(path: Path) -> None:
    expected = php_parse_ini(path, sections=True)
    assert parse_ini_file(path, process_sections=True) == (expected or {})
