"""Repository layout discovery.

The PHP application is the reference implementation this package is ported
from. It may sit at ``./www`` (original checkout) or ``./php_original/www``
(after the tree was separated from the Python backend). Both layouts are
supported so tests and local runs work either way.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["repo_root", "find_php_root", "find_www_root", "find_settings_dir"]


def repo_root() -> Path:
    """Return the directory that contains the PHP reference tree.

    Walks up from this module so it works whether or not the package is
    installed in editable mode.
    """

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "www").is_dir() or (parent / "php_original" / "www").is_dir():
            return parent
    return here.parents[3]


def find_php_root() -> Path:
    """Return the PHP application root (``www``'s parent)."""

    root = repo_root()
    for candidate in (root / "php_original", root):
        if (candidate / "www").is_dir():
            return candidate
    return root / "php_original"


def find_www_root() -> Path:
    """Return the PHP web root."""

    override = os.environ.get("WPT_WWW_ROOT")
    if override:
        return Path(override).resolve()
    return find_php_root() / "www"


def find_settings_dir() -> Path:
    """Return the runtime settings directory."""

    override = os.environ.get("WPT_SETTINGS_DIR")
    if override:
        return Path(override).resolve()
    return find_www_root() / "settings"
