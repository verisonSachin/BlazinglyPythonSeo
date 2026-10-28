"""Legacy lock-file protocol."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from app.storage.locks import LockManager


def test_acquire_creates_named_file(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    lock = manager.acquire("Unique ID")
    assert lock is not None
    assert lock.file.name == "named-Unique-ID.lock"
    assert lock.file.is_file()
    lock.release()
    assert not lock.file.exists()


def test_second_acquirer_is_blocked_when_non_blocking(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    first = manager.acquire("Test 250102_AB_x")
    assert first is not None
    assert manager.acquire("Test 250102_AB_x", blocking=False) is None
    first.release()
    assert manager.acquire("Test 250102_AB_x", blocking=False) is not None


def test_unsafe_names_are_hashed(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    path = manager.lock_path("Test 250102_AB/x")
    assert path.name == f"lock-{hashlib.sha1(b'Test 250102_AB/x').hexdigest()}.lock"


def test_stale_lock_is_broken(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    path = manager.lock_path("Unique ID")
    path.write_text("stale")
    old = time.time() - 400
    os.utime(path, (old, old))

    lock = manager.acquire("Unique ID", blocking=False, max_lock_seconds=300)
    assert lock is not None
    assert lock.file.is_file()
    lock.release()


def test_fresh_lock_is_not_broken(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    path = manager.lock_path("Unique ID")
    path.write_text("fresh")
    assert manager.acquire("Unique ID", blocking=False, max_lock_seconds=300) is None


def test_context_manager_releases(tmp_path: Path) -> None:
    manager = LockManager(tmp_path)
    with manager.acquire("Test x") as lock:
        assert lock is not None
        assert lock.file.is_file()
    assert not (tmp_path / "named-Test-x.lock").exists()
