"""Settings precedence, caching and cookie-name parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.cache import TTLCache
from app.core.settings import Settings


def make_settings(tmp_path: Path, files: dict[str, str]) -> Settings:
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return Settings(tmp_path)


def test_merge_order_later_files_win(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        {
            "settings.ini": "a=1\nb=1\n",
            "common/settings.ini": "b=2\nc=2\n",
            "server/settings.ini": "c=3\n",
        },
    )
    assert settings.get("a") == "1"
    assert settings.get("b") == "2"
    assert settings.get("c") == "3"


def test_missing_setting_returns_default(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"settings.ini": "a=1\n"})
    assert settings.get("nope") is False
    assert settings.get("nope", "fallback") == "fallback"


def test_settings_are_cached_until_ttl(tmp_path: Path) -> None:
    now = [1000.0]
    cache = TTLCache(clock=lambda: now[0])
    settings = Settings(tmp_path, cache=cache)
    (tmp_path / "settings.ini").write_text("a=1\n", encoding="utf-8")
    assert settings.get("a") == "1"

    (tmp_path / "settings.ini").write_text("a=2\n", encoding="utf-8")
    assert settings.get("a") == "1"  # still inside the 60s window

    now[0] += 61
    assert settings.get("a") == "2"


def test_reload_bypasses_cache(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"settings.ini": "a=1\n"})
    assert settings.get("a") == "1"
    (tmp_path / "settings.ini").write_text("a=2\n", encoding="utf-8")
    settings.reload()
    assert settings.get("a") == "2"


def test_type_coercion(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        {"settings.ini": "flag=1\noff=0\nempty=\nnum=42\nword=hello\n"},
    )
    assert settings.get_bool("flag") is True
    assert settings.get_bool("off") is False
    assert settings.get_bool("empty") is False
    assert settings.get_int("num") == 42
    assert settings.get_str("word") == "hello"


def test_server_secret_precedence(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        {
            "keys.ini": "[server]\nsecret=base\n",
            "server/keys.ini": "[server]\nsecret=override\n",
        },
    )
    assert settings.server_secret() == "override"


def test_server_secret_missing_is_empty(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"settings.ini": "a=1\n"})
    assert settings.server_secret() == ""


def test_cookie_name_without_secret(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"settings.ini": "a=1\n"})
    # Vector produced by PHP: hash('sha256', hash('sha1', 'test' . 'x') . '')
    assert settings.cookie_name("test") == (
        "d6dd34c5112a293b24a06d37544e6175a96a9c363504595195135d55d132818c"
    )


def test_cookie_name_with_secret_and_cookie_secret(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        {
            "settings.ini": "cookie_secret=abc123\n",
            "keys.ini": "[server]\nsecret=s3cr3t\n",
        },
    )
    # Vector produced by PHP: hash('sha256', hash('sha1', 'o' . 'abc123') . 's3cr3t')
    assert settings.cookie_name("o") == (
        "78cd9ad97eaff9ca743959713f1336abeb238495c8452337b065f84b8d49403c"
    )


def test_ini_file_prefers_server_then_common(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        {
            "locations.ini": "[base]\nlabel=base\n",
            "common/locations.ini": "[common]\nlabel=common\n",
            "server/locations.ini": "[server]\nlabel=server\n",
        },
    )
    result = settings.ini_file("locations.ini", process_sections=True)
    assert result == {"server": {"label": "server"}}


def test_ini_file_sample_fallback(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"locations.ini.sample": "label=sample\n"})
    assert settings.ini_file("locations.ini", allow_sample=True) == {"label": "sample"}
    assert settings.ini_file("locations.ini") is None


def test_plain_file_skips_blank_lines(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, {"blockdomains.txt": "a\n\nb\n"})
    assert settings.plain_file("blockdomains.txt") == ["a", "b"]
