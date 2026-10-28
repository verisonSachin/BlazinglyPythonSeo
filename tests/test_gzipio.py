"""Gzip framing must be byte-identical to PHP's ``gzencode``."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from app.storage.gzipio import (
    gz_file_get_contents,
    gz_file_put_contents,
    gz_is_file,
    gzip_bytes,
    gunzip_bytes,
)

PHP = shutil.which("php")


def php_gzencode(payload: bytes) -> bytes:
    if PHP is None:  # pragma: no cover
        pytest.skip("php binary not available")
    proc = subprocess.run(
        [PHP, "-r", "echo bin2hex(gzencode(file_get_contents('php://stdin')));"],
        input=payload,
        capture_output=True,
        check=True,
    )
    return bytes.fromhex(proc.stdout.decode())


@pytest.mark.parametrize(
    "payload",
    [b"", b"hello world", b"a" * 5000, "caf\u00e9".encode(), bytes(range(256))],
)
def test_byte_identical_to_php(payload: bytes) -> None:
    assert gzip_bytes(payload) == php_gzencode(payload)


def test_roundtrip() -> None:
    payload = b"some testinfo json" * 100
    assert gunzip_bytes(gzip_bytes(payload)) == payload


def test_put_and_get(tmp_path) -> None:
    target = tmp_path / "testinfo.json"
    assert gz_file_put_contents(target, b"{}") is True
    assert (tmp_path / "testinfo.json.gz").is_file()
    assert not target.exists()
    assert gz_file_get_contents(target) == b"{}"
    assert gz_is_file(target) is True


def test_nogzip_writes_plain_file(tmp_path) -> None:
    target = tmp_path / "testinfo.json"
    assert gz_file_put_contents(target, b"{}", nogzip=True) is True
    assert target.is_file()
    assert not (tmp_path / "testinfo.json.gz").exists()
    assert gz_file_get_contents(target) == b"{}"


def test_missing_file_returns_none(tmp_path) -> None:
    assert gz_file_get_contents(tmp_path / "absent") is None


def test_prefers_compressed_copy(tmp_path) -> None:
    target = tmp_path / "data"
    target.write_bytes(b"plain")
    gz_file_put_contents(target, b"compressed")
    assert gz_file_get_contents(target) == b"compressed"
