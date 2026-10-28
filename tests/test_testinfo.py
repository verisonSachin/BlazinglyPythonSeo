"""testinfo.json / testinfo.ini round-trips."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from app.storage.locks import LockManager
from app.storage.testinfo import (
    build_testinfo_ini,
    read_ini,
    read_json,
    write_ini,
    write_json,
)


def test_write_and_read_json(tmp_path: Path) -> None:
    data = {"id": "250102_AB_x", "runs": 3, "fvonly": 1, "url": "https://example.com/a"}
    assert write_json(tmp_path, data) is True

    compressed = tmp_path / "testinfo.json.gz"
    assert compressed.is_file()
    assert json.loads(gzip.decompress(compressed.read_bytes())) == data
    assert read_json(tmp_path) == data


def test_json_escapes_slashes_like_php(tmp_path: Path) -> None:
    write_json(tmp_path, {"url": "https://example.com/a"})
    raw = gzip.decompress((tmp_path / "testinfo.json.gz").read_bytes()).decode()
    assert "https:\\/\\/example.com\\/a" in raw


def test_read_json_missing_returns_none(tmp_path: Path) -> None:
    assert read_json(tmp_path) is None


def test_write_json_requires_directory(tmp_path: Path) -> None:
    assert write_json(tmp_path / "absent", {"id": "x"}) is False


def test_write_json_with_lock(tmp_path: Path) -> None:
    locks = LockManager(tmp_path / "tmp")
    assert write_json(tmp_path, {"id": "x"}, locks=locks) is True
    assert list((tmp_path / "tmp").glob("*.lock")) == []


def test_ini_roundtrip(tmp_path: Path) -> None:
    fields = [
        ("fvonly", 1),
        ("runs", 3),
        ("location", '"Dulles, VA"'),
        ("loc", "Dulles"),
        ("id", "250102_AB_x"),
    ]
    assert write_ini(tmp_path, fields) is True

    raw = (tmp_path / "testinfo.ini").read_bytes()
    assert b"\r\n" in raw
    assert b"location=\"Dulles, VA\"\r\n" in raw

    parsed = read_ini(tmp_path)
    assert parsed == {
        "fvonly": "1",
        "runs": "3",
        "location": "Dulles, VA",
        "loc": "Dulles",
        "id": "250102_AB_x",
    }


def test_ini_skips_none_and_multiline_values() -> None:
    text = build_testinfo_ini([("a", None), ("b", "line1\nline2"), ("c", 0)])
    assert text == "[test]\r\nc=0\r\n"


def test_ini_key_order_preserved() -> None:
    text = build_testinfo_ini([("z", 1), ("a", 2)])
    assert text == "[test]\r\nz=1\r\na=2\r\n"
