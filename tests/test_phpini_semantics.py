"""Explicit INI semantics captured from PHP 8.5.

Each case here is a behaviour the differential file sweep might not cover.
"""

from __future__ import annotations

import pytest

from app.core.phpini import IniParseError, parse_ini_string


def parse(text: str, **kwargs) -> dict:
    return parse_ini_string(text, **kwargs)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", "1"),
        ("TRUE", "1"),
        ("on", "1"),
        ("yes", "1"),
        ("false", ""),
        ("off", ""),
        ("no", ""),
        ("none", ""),
        ("null", ""),
    ],
)
def test_boolean_words(raw: str, expected: str) -> None:
    assert parse(f"k={raw}")["k"] == expected


def test_empty_values() -> None:
    result = parse('a=\nb=""\nc=\'\'\n')
    assert result == {"a": "", "b": "", "c": ""}


def test_values_are_strings() -> None:
    result = parse("a=42\nb=3.14\nc=0\n")
    assert result == {"a": "42", "b": "3.14", "c": "0"}


def test_key_and_section_case_preserved() -> None:
    result = parse("[Sec]\nMixedCase=1\n", process_sections=True)
    assert result == {"Sec": {"MixedCase": "1"}}


def test_duplicate_keys_last_wins() -> None:
    assert parse("k=1\nk=2") == {"k": "2"}


def test_semicolon_starts_comment_anywhere() -> None:
    assert parse("k=a;b")["k"] == "a"


def test_hash_only_comments_at_line_start() -> None:
    assert parse("k=a#b")["k"] == "a#b"
    assert parse("# comment\nk=1")["k"] == "1"


def test_trimming() -> None:
    assert parse("  k   =   value   ")["k"] == "value"


def test_quotes_preserve_spaces() -> None:
    assert parse('k="  spaced  "')["k"] == "  spaced  "


def test_single_quotes_are_literal() -> None:
    assert parse("k='a\\nb'")["k"] == "a\\nb"


def test_double_quote_escapes() -> None:
    assert parse('k="a\\"b"')["k"] == 'a"b'
    assert parse('k="a\\\\b"')["k"] == "a\\b"
    assert parse('k="a\\nb"')["k"] == "a\\nb"


def test_adjacent_quoted_fragments_concatenate() -> None:
    assert parse('k="a" "b" "c"')["k"] == "abc"
    assert parse('k="a"b')["k"] == "ab"


def test_trailing_comment_after_quoted_value() -> None:
    assert parse('k="x" ; note')["k"] == "x"


def test_environment_interpolation() -> None:
    assert parse("k=${WPT_TEST_VAR}", environ={"WPT_TEST_VAR": "v"})["k"] == "v"


def test_missing_environment_variable_is_empty() -> None:
    assert parse("k=${WPT_MISSING_VAR}rest", environ={})["k"] == "rest"


def test_bitwise_operators_match_php() -> None:
    assert parse("k=a|b", environ={})["k"] == "0"
    assert parse("k=1|2", environ={})["k"] == "3"
    assert parse("k=a&b", environ={})["k"] == "0"
    assert parse("k=~a", environ={})["k"] == "-1"
    assert parse("k=!a", environ={})["k"] == "1"


def test_arithmetic_is_literal() -> None:
    # PHP's ini scanner only treats & | ^ ~ ! as operators.
    assert parse("k=5+3")["k"] == "5+3"
    assert parse("k=a-b")["k"] == "a-b"


def test_sections_off_flattens() -> None:
    text = "[a]\nx=1\n[b]\ny=2\n"
    assert parse(text) == {"x": "1", "y": "2"}


def test_sections_on_nests() -> None:
    text = "[a]\nx=1\n[b]\ny=2\n"
    assert parse(text, process_sections=True) == {"a": {"x": "1"}, "b": {"y": "2"}}


def test_top_level_keys_with_sections_on() -> None:
    text = "top=1\n[a]\nx=2\n"
    assert parse(text, process_sections=True) == {"top": "1", "a": {"x": "2"}}


def test_unquoted_equals_is_rejected() -> None:
    # PHP refuses this too; failing loudly beats silently truncating credentials.
    with pytest.raises(IniParseError):
        parse("k=a=b=c")


def test_missing_equals_is_rejected() -> None:
    with pytest.raises(IniParseError):
        parse("just_a_key")


def test_unterminated_quote_is_rejected() -> None:
    with pytest.raises(IniParseError):
        parse('k="unterminated')
