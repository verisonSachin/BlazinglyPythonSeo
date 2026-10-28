"""PHP-compatible JSON serialisation.

``json_encode()`` with default flags is not the same as :func:`json.dumps`:

* ``/`` is escaped as ``\\/``
* non-ASCII characters are escaped as ``\\uXXXX``
* no spaces after ``:`` or ``,``

``SaveTestInfo()`` writes ``testinfo.json`` with these defaults and the file is
consumed by agents and by the result parsers, so the bytes matter.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["dumps", "loads"]


def dumps(value: Any) -> str:
    """Serialise ``value`` the way PHP's ``json_encode`` does by default."""

    text = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    # PHP escapes forward slashes unless JSON_UNESCAPED_SLASHES is passed.
    return text.replace("/", "\\/")


def loads(text: str | bytes) -> Any:
    """Parse JSON; thin wrapper that keeps the call sites readable."""

    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return json.loads(text)
