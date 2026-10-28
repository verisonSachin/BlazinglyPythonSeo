"""Transparent gzip helpers matching ``www/common_lib.inc``.

The legacy helpers look for ``<file>.gz`` first and fall back to the plain file,
and they compress with zlib level 6 by default. Gzip framing is rebuilt by hand
so the output is byte-identical to PHP's ``gzencode()`` (verified: the deflate
stream from zlib is already identical, only the header differs).

Relevant settings: ``nogzip`` disables compression entirely, ``compression``
selects the level (clamped to 1..9).
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

__all__ = [
    "GZIP_HEADER",
    "gzip_bytes",
    "gunzip_bytes",
    "gz_file_get_contents",
    "gz_file_put_contents",
    "gz_is_file",
    "gz_compress",
    "gz_read_bytes",
]

# mtime=0, XFL=0, OS=3 (Unix) -- what PHP writes.
GZIP_HEADER = bytes([0x1F, 0x8B, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03])


def gzip_bytes(data: bytes, level: int = 6) -> bytes:
    """Compress ``data`` into a gzip member identical to PHP's output."""

    if not 1 <= level <= 9:
        level = 6
    compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
    body = compressor.compress(data) + compressor.flush()
    trailer = struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)
    return GZIP_HEADER + body + trailer


def gunzip_bytes(data: bytes) -> bytes:
    """Decompress a gzip member, tolerating concatenated members."""

    return zlib.decompress(data, wbits=31)


def gz_read_bytes(path: str | os.PathLike[str]) -> bytes | None:
    """Read ``<path>.gz`` if present, otherwise ``path``.

    Returns ``None`` when neither exists, matching ``gz_file_get_contents``
    returning ``null``.
    """

    compressed = Path(f"{path}.gz")
    if compressed.is_file() and compressed.stat().st_size:
        return gunzip_bytes(compressed.read_bytes())
    plain = Path(path)
    if plain.is_file() and plain.stat().st_size:
        return plain.read_bytes()
    return None


def gz_file_get_contents(path: str | os.PathLike[str]) -> bytes | None:
    """Alias of :func:`gz_read_bytes` for parity with the legacy name."""

    return gz_read_bytes(path)


def gz_file_put_contents(
    path: str | os.PathLike[str],
    data: bytes | str,
    *,
    nogzip: bool = False,
    compression: int = 6,
) -> bool:
    """Write ``path.gz`` (or ``path`` when ``nogzip``) and report success."""

    if isinstance(data, str):
        data = data.encode("utf-8")

    if nogzip:
        try:
            Path(path).write_bytes(data)
        except OSError:
            return False
        return True

    if not 1 <= int(compression) <= 9:
        compression = 6
    try:
        Path(f"{path}.gz").write_bytes(gzip_bytes(data, int(compression)))
    except OSError:
        return False
    return True


def gz_compress(path: str | os.PathLike[str], *, nogzip: bool = False, compression: int = 6) -> bool:
    """Compress an existing plain file in place, as ``gz_compress()`` does."""

    if nogzip:
        return False
    source = Path(path)
    if not source.is_file():
        return False
    data = source.read_bytes()
    if not data:
        return False
    return gz_file_put_contents(path, data, nogzip=nogzip, compression=compression)


def gz_is_file(path: str | os.PathLike[str]) -> bool:
    """True when either the compressed or the plain file exists."""

    return Path(f"{path}.gz").is_file() or Path(path).is_file()
