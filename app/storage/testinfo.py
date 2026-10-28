"""Reading and writing test metadata.

``GetTestInfo()`` reads ``testinfo.json`` (gzip when ``nogzip`` is off) under a
``Test Info <realpath>`` lock. The legacy code does **not** fall back to
``testinfo.ini`` locally -- if the JSON is absent it asks the owning server via
``testInfo.php``. ``testinfo.ini`` is still written for agents and humans, so it
must keep its exact key order and CRLF endings.

This module deliberately exposes both readers: :func:`read_json` for the
authoritative metadata and :func:`read_ini` for agent-facing values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from ..core import phpjson
from ..core.phpini import parse_ini_file
from .gzipio import gz_file_get_contents, gz_file_put_contents, gz_is_file
from .inifile import build_ini
from .locks import LockManager

__all__ = [
    "metadata_path",
    "read_json",
    "write_json",
    "read_ini",
    "write_ini",
    "build_testinfo_ini",
]

_METADATA_NAME = "testinfo.json"
_INI_NAME = "testinfo.ini"


def metadata_path(test_dir: str | os.PathLike[str]) -> Path:
    return Path(test_dir) / _METADATA_NAME


def read_json(
    test_dir: str | os.PathLike[str],
    *,
    locks: LockManager | None = None,
) -> dict[str, Any] | None:
    """Return decoded ``testinfo.json``, or ``None`` when it does not exist."""

    directory = Path(test_dir)
    path = directory / _METADATA_NAME
    if not gz_is_file(path):
        return None

    lock = None
    if locks is not None:
        try:
            resolved = directory.resolve()
        except OSError:
            resolved = directory
        lock = locks.acquire(f"Test Info {resolved}")
        if lock is None:
            return None

    try:
        raw = gz_file_get_contents(path)
        if raw is None:
            return None
        decoded = phpjson.loads(raw)
        return decoded if isinstance(decoded, dict) else None
    except ValueError:
        return None
    finally:
        if lock is not None:
            lock.release()


def write_json(
    test_dir: str | os.PathLike[str],
    data: dict[str, Any],
    *,
    locks: LockManager | None = None,
    nogzip: bool = False,
    compression: int = 6,
) -> bool:
    """Write ``testinfo.json`` under the same lock the legacy code uses."""

    directory = Path(test_dir)
    if not directory.is_dir():
        return False

    lock = None
    if locks is not None:
        try:
            resolved = directory.resolve()
        except OSError:
            resolved = directory
        lock = locks.acquire(f"Test Info {resolved}")
        if lock is None:
            return False

    try:
        return gz_file_put_contents(
            directory / _METADATA_NAME,
            phpjson.dumps(data),
            nogzip=nogzip,
            compression=compression,
        )
    finally:
        if lock is not None:
            lock.release()


def read_ini(test_dir: str | os.PathLike[str]) -> dict[str, str] | None:
    """Parse ``testinfo.ini`` and return the ``[test]`` section."""

    path = Path(test_dir) / _INI_NAME
    if not path.is_file():
        return None
    parsed = parse_ini_file(path, process_sections=True)
    section = parsed.get("test")
    if isinstance(section, dict):
        return section
    # Section-less file: treat the whole document as the test section.
    return {k: v for k, v in parsed.items() if isinstance(v, str)}


def write_ini(test_dir: str | os.PathLike[str], fields: Iterable[tuple[str, Any]]) -> bool:
    """Write ``testinfo.ini`` with CRLF endings and insertion order preserved."""

    directory = Path(test_dir)
    if not directory.is_dir():
        return False
    try:
        (directory / _INI_NAME).write_bytes(build_testinfo_ini(fields).encode("utf-8"))
    except OSError:
        return False
    return True


def build_testinfo_ini(fields: Iterable[tuple[str, Any]]) -> str:
    """Build the ``[test]`` INI document.

    Callers pass ``location`` already quoted (``"\\"label\\""``), because the
    legacy writer quotes it explicitly while every other value is bare.
    """

    return build_ini(fields, section="test")
