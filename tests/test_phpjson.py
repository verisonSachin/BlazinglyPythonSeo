"""PHP ``json_encode`` parity."""

from __future__ import annotations

import pytest

from app.core import phpjson


def test_matches_php_default_flags() -> None:
    value = {
        "a": "x/y",
        "b": "é",
        "c": 1.5,
        "d": True,
        "e": None,
        "f": [],
        "g": "http://a/b?c=d",
    }
    expected = (
        '{"a":"x\\/y","b":"\\u00e9","c":1.5,"d":true,"e":null,"f":[],'
        '"g":"http:\\/\\/a\\/b?c=d"}'
    )
    assert phpjson.dumps(value) == expected


def test_compact_separators() -> None:
    assert phpjson.dumps({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_roundtrip() -> None:
    value = {"day": 12, "num": 34, "nested": {"ok": True}}
    assert phpjson.loads(phpjson.dumps(value)) == value


def test_rejects_nan() -> None:
    with pytest.raises(ValueError):
        phpjson.dumps({"x": float("nan")})
