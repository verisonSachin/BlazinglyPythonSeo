"""Test ID generation and validation.

Ported from ``www/common_lib.inc``:

``NumToString()``      base-32 with the alphabet ``0123456789ABCDEFGHJKMNPQRSTVWXYZ``
``ShardKey()``         two random base-32 digits by default, plus optional
                       ``cp_capture_prefix`` / location / ``serverID`` prefixes
``GenerateTestID()``   ``ymd_`` + shard + daily counter (public) or MD5 (private)
``ValidateTestId()``   shape check plus a two-digit year window

The random shard is injected so tests can be deterministic; production callers
pass a ``secrets``-backed generator.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
from typing import Callable, Protocol

from ..core.errors import InvalidTestId

__all__ = [
    "DIGITS",
    "UniqueIdAllocator",
    "num_to_string",
    "shard_key",
    "validate_test_id",
    "require_valid_test_id",
    "generate_test_id",
    "is_private_id",
]

DIGITS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]")

# PHP: intval(substr($testId, 0, 2)) must be within [8, current year % 100].
_MIN_YEAR = 8


class UniqueIdAllocator(Protocol):
    """Callable that allocates the next daily ID and exposes its counter."""

    counter: int

    def __call__(self) -> str:  # pragma: no cover - protocol definition
        ...


def num_to_string(num: int) -> str:
    """Convert a positive integer to the legacy base-32 alphabet."""

    if num <= 0:
        return "0"
    out: list[str] = []
    while num > 0:
        num, digit = divmod(num, 32)
        out.append(DIGITS[digit])
    return "".join(reversed(out))


def shard_key(
    test_num: int,
    *,
    shard: int = 2,
    bucket_size: int = 0,
    capture_prefix: str = "",
    location_id: str | None = None,
    server_id: str | None = None,
    rand_digit: Callable[[int], str] | None = None,
) -> str:
    """Return the shard portion of a test ID.

    ``bucket_size`` groups tests sequentially instead of using a random shard.
    ``shard`` outside ``1..19`` disables the random shard entirely (PHP's
    ``$size > 0 && $size < 20`` guard).
    """

    key = ""

    if bucket_size:
        key = f"{num_to_string(test_num // bucket_size)}_"
    else:
        size = int(shard)
        if 0 < size < 20:
            chooser = rand_digit or _default_rand_digit
            key = "".join(chooser(len(DIGITS)) for _ in range(size)) + "_"

    if capture_prefix:
        key = f"{capture_prefix}c{key}"

    if location_id and key:
        cleaned = _NON_ALNUM_RE.sub("", location_id)
        if cleaned:
            key = f"{cleaned}x{key}"

    if key and server_id:
        cleaned = _NON_ALNUM_RE.sub("", server_id)
        if cleaned:
            key = f"{cleaned}i{key}"

    return key


def _default_rand_digit(alphabet_size: int) -> str:
    import secrets

    return DIGITS[secrets.randbelow(alphabet_size)]


def validate_test_id(test_id: str, *, current_year: int | None = None) -> bool:
    """Return whether ``test_id`` is acceptable.

    PHP also mutates its argument to ``''`` on failure and then ``exit(0)``;
    that is a routing concern, handled by :func:`require_valid_test_id`.
    """

    if not test_id or not _SAFE_ID_RE.match(test_id):
        return False
    year = current_year if current_year is not None else _dt.datetime.now().year
    prefix = test_id[:2]
    if not prefix.isdigit():
        return False
    test_year = int(prefix)
    return _MIN_YEAR <= test_year <= year % 100


def require_valid_test_id(test_id: str, *, current_year: int | None = None) -> str:
    """Return ``test_id`` or raise :class:`InvalidTestId`.

    Callers must translate the exception into an empty HTTP 200 response to
    match the legacy ``exit(0)``.
    """

    if not validate_test_id(test_id, current_year=current_year):
        raise InvalidTestId(test_id)
    return test_id


def is_private_id(test_id: str) -> bool:
    """Private IDs use a 32-character hex suffix instead of the daily counter.

    This is a heuristic used for diagnostics only; the authoritative marker is
    ``testinfo.ini``'s ``private`` flag.
    """

    if test_id.find("_") != 6:
        return False
    suffix = test_id.rsplit("_", 1)[-1]
    return len(suffix) == 32 and all(c in "0123456789abcdef" for c in suffix.lower())


def generate_test_id(
    *,
    unique_id: UniqueIdAllocator | Callable[[], str],
    now: _dt.datetime | None = None,
    private: bool = False,
    location_shard: str | None = None,
    shard: int = 2,
    bucket_size: int = 0,
    capture_prefix: str = "",
    server_id: str | None = None,
    rand_digit: Callable[[int], str] | None = None,
    path_exists: Callable[[str], bool] | None = None,
) -> str:
    """Generate a unique test ID.

    Mirrors ``GenerateTestID()``, including its side effect on the daily
    counter: ``unique_id()`` is called once even for private tests, because the
    legacy code allocates the counter before discarding the encoded value.

    ``path_exists`` is consulted to avoid collisions; when a directory already
    exists the shard is re-rolled and an MD5 token used, exactly like PHP.
    """

    today = now or _dt.datetime.now(_dt.timezone.utc)
    stamp = today.strftime("%y%m%d")

    allocated = unique_id()
    test_num = _allocator_counter(unique_id, fallback=allocated)

    shard_part = shard_key(
        test_num,
        shard=shard,
        bucket_size=bucket_size,
        capture_prefix=capture_prefix,
        location_id=location_shard,
        server_id=server_id,
        rand_digit=rand_digit,
    )
    suffix = _md5_token() if private else allocated
    test_id = f"{stamp}_{shard_part}{suffix}"

    if path_exists is None:
        return test_id

    while path_exists(test_id):
        shard_part = shard_key(
            test_num,
            shard=shard,
            bucket_size=bucket_size,
            capture_prefix=capture_prefix,
            location_id=location_shard,
            server_id=server_id,
            rand_digit=rand_digit,
        )
        test_id = f"{stamp}_{shard_part}{_md5_token()}"

    return test_id


def _allocator_counter(unique_id: object, *, fallback: str) -> int:
    """Best-effort numeric counter used only by ``bucket_size`` grouping."""

    counter = getattr(unique_id, "counter", None)
    if counter is not None:
        try:
            return int(counter)
        except (TypeError, ValueError):
            return 0
    try:
        return int(fallback)
    except (TypeError, ValueError):
        return 0


def _md5_token() -> str:
    return hashlib.md5(os.urandom(16)).hexdigest()
