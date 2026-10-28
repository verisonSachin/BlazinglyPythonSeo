"""A parser for PHP ``parse_ini_file`` semantics.

The legacy application reads every setting, location, connectivity profile and
test metadata through PHP's INI parser. Re-implementing it with ``configparser``
or a naive ``key=value`` splitter silently changes behaviour, so this module
mirrors the parts of the real parser that the repository actually exercises and
raises :class:`IniParseError` on constructs it does not model.

Verified against PHP 8.5 (see ``tests/test_phpini_differential.py``):

* keys and section names preserve case; duplicate keys are last-wins
* ``;`` starts a comment anywhere in a line; ``#`` only at the start of a line
* unquoted values are trimmed
* ``true|on|yes`` -> ``"1"``; ``false|off|no|none|null`` -> ``""`` (case-insensitive)
* values are always strings
* double quotes honour ``\\"`` and ``\\\\`` only; other backslashes are literal
* adjacent quoted/bare fragments concatenate (``k="a"b`` -> ``"ab"``)
* ``${VAR}`` interpolates the process environment; an unknown name becomes empty
* unquoted values support the bitwise/boolean operators ``& | ^ ~ !``
* ``key=`` and ``key=""`` both yield ``""``
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

__all__ = ["IniParseError", "parse_ini_file", "parse_ini_string"]


class IniParseError(ValueError):
    """Raised when a line cannot be represented by the supported INI subset."""


_TRUE_WORDS = frozenset({"true", "on", "yes"})
_FALSE_WORDS = frozenset({"false", "off", "no", "none", "null"})

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# PHP's ini scanner treats these as operators inside unquoted values.
_BINARY_OPS = "&|^"
_UNARY_OPS = "~!"


def parse_ini_file(
    path: str | os.PathLike[str],
    process_sections: bool = False,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Parse an INI file the way ``parse_ini_file()`` does.

    Missing or unreadable files raise :class:`FileNotFoundError` /
    ``OSError``; the PHP callers check ``file_exists()`` first, so the
    equivalent check is the caller's responsibility.
    """

    text = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    return parse_ini_string(text, process_sections, environ=environ)


def parse_ini_string(
    text: str,
    process_sections: bool = False,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Parse INI text the way ``parse_ini_string()`` does."""

    env = os.environ if environ is None else environ
    result: dict[str, Any] = {}
    section: dict[str, Any] = result
    section_name: str | None = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(";") or line.startswith("#"):
            continue

        if line.startswith("["):
            if not line.endswith("]"):
                raise IniParseError(f"line {lineno}: unterminated section header")
            name = line[1:-1].strip()
            if not name:
                raise IniParseError(f"line {lineno}: empty section name")
            if process_sections:
                section_name = name
                section = result.setdefault(name, {})
            continue

        key, sep, value = line.partition("=")
        if not sep:
            raise IniParseError(f"line {lineno}: expected 'key = value'")
        key = key.strip()
        if not key:
            raise IniParseError(f"line {lineno}: empty key")
        if key.startswith(('"', "'")):
            key = _unquote_key(key, lineno)

        parsed = _parse_value(value, env, lineno)

        if process_sections and section_name is None:
            result[key] = parsed
        else:
            section[key] = parsed

    return result


def _unquote_key(key: str, lineno: int) -> str:
    quote = key[0]
    if len(key) < 2 or not key.endswith(quote):
        raise IniParseError(f"line {lineno}: unterminated quoted key")
    return key[1:-1]


def _parse_value(raw: str, env: Mapping[str, str], lineno: int) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in "\"'":
        return _parse_quoted(value, env, lineno)
    return _parse_unquoted(value, env)


def _parse_quoted(value: str, env: Mapping[str, str], lineno: int) -> str:
    out: list[str] = []
    i = 0
    length = len(value)

    while i < length:
        ch = value[i]

        if ch in " \t":
            i += 1
            continue

        if ch in ";#":
            break

        if ch in "\"'":
            quote = ch
            i += 1
            buf: list[str] = []
            while True:
                if i >= length:
                    raise IniParseError(f"line {lineno}: unterminated quoted value")
                current = value[i]
                if current == "\\" and quote == '"' and i + 1 < length and value[i + 1] in '"\\':
                    buf.append(value[i + 1])
                    i += 2
                    continue
                if current == quote:
                    i += 1
                    break
                buf.append(current)
                i += 1
            out.append(_interpolate("".join(buf), env))
            continue

        # Bare fragment following a quoted one (`k="a"b` -> `ab`).
        start = i
        while i < length and value[i] not in ";#":
            i += 1
        out.append(_interpolate(value[start:i].strip(), env))

    return "".join(out)


def _parse_unquoted(value: str, env: Mapping[str, str]) -> str:
    comment = value.find(";")
    if comment != -1:
        value = value[:comment].rstrip()

    lowered = value.lower()
    if lowered in _TRUE_WORDS:
        return "1"
    if lowered in _FALSE_WORDS:
        return ""

    value = _interpolate(value, env)

    if "=" in value:
        # PHP's parser refuses an unquoted ``=``; values that need one must be
        # quoted. Failing here is safer than silently storing a truncated value.
        raise IniParseError("unquoted '=' in value; quote the value")

    if any(op in value for op in _BINARY_OPS) or any(op in value for op in _UNARY_OPS):
        return _eval_operators(value)

    return value


def _interpolate(value: str, env: Mapping[str, str]) -> str:
    if "${" not in value:
        return value
    return _ENV_RE.sub(lambda m: env.get(m.group(1), ""), value)


def _operand(token: str) -> int:
    token = token.strip()
    if not token:
        return 0
    lowered = token.lower()
    if lowered in _TRUE_WORDS:
        return 1
    if lowered in _FALSE_WORDS:
        return 0
    try:
        return int(token, 0)
    except ValueError:
        try:
            return int(float(token))
        except ValueError:
            return 0


def _eval_operators(value: str) -> str:
    """Evaluate PHP's unquoted-value operators with PHP's precedence.

    ``!`` binds tightest, then ``~``, then ``&``, ``^``, ``|``. Numeric tokens
    become integers; unknown bare words become ``0``, matching PHP's treatment
    of undefined constants in INI values.
    """

    # Split into operands and operators, keeping unary operators attached.
    tokens: list[str] = []
    buf: list[str] = []
    for ch in value:
        if ch in _BINARY_OPS or ch in _UNARY_OPS:
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(ch)
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))

    # Resolve unary operators right-to-left.
    resolved: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _UNARY_OPS:
            operand_index = i + 1
            if operand_index >= len(tokens):
                resolved.append("0")
                i += 1
                continue
            n = _operand(tokens[operand_index])
            if tok == "!":
                resolved.append("1" if n == 0 else "")
            else:
                resolved.append(str(~n))
            i += 2
        else:
            resolved.append(tok)
            i += 1

    # Apply binary operators in precedence order.
    for ops in ("&", "^", "|"):
        i = 0
        while i < len(resolved):
            if resolved[i] == ops:
                left = _operand(resolved[i - 1])
                right = _operand(resolved[i + 1]) if i + 1 < len(resolved) else 0
                if ops == "&":
                    result = left & right
                elif ops == "^":
                    result = left ^ right
                else:
                    result = left | right
                resolved[i - 1 : i + 2] = [str(result)]
                continue
            i += 1

    return resolved[0] if len(resolved) == 1 else "".join(resolved)
