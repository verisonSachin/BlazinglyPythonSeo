"""INI writing helpers.

``AddIniLine()`` in ``www/common_lib.inc`` only appends a line when the value is
set and contains no newline. ``testinfo.ini`` uses CRLF line endings and the key
order is significant to humans diffing stored tests, so the builder preserves
insertion order.
"""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["add_ini_line", "build_ini"]


def add_ini_line(lines: list[str], key: str, value: Any) -> None:
    """Append ``key=value`` unless the value is unset or multi-line."""

    if value is None:
        return
    text = str(value)
    if "\n" in text or "\r" in text:
        return
    lines.append(f"{key}={text}")


def build_ini(
    fields: Iterable[tuple[str, Any]],
    *,
    section: str | None = "test",
) -> str:
    """Build CRLF-delimited INI text.

    ``section=None`` produces a section-less file. Values are written verbatim;
    callers quote them where the legacy code does (for example ``location``).
    """

    lines: list[str] = []
    if section is not None:
        lines.append(f"[{section}]")
    for key, value in fields:
        add_ini_line(lines, key, value)
    return "".join(f"{line}\r\n" for line in lines)
