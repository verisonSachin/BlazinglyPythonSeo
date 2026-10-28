from __future__ import annotations

from pathlib import Path

import pytest

from .helpers import PHP, REPO_ROOT, SETTINGS_DIR, WWW, ini_files, php_parse_ini

__all__ = ["PHP", "REPO_ROOT", "SETTINGS_DIR", "WWW", "php_parse_ini", "ini_files"]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def www_dir() -> Path:
    return WWW


@pytest.fixture(scope="session")
def settings_dir() -> Path:
    return SETTINGS_DIR
