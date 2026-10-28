"""Lock files compatible with the legacy ``Lock()`` protocol.

``www/common_lib.inc`` coordinates PHP processes with ``fopen($file, 'xb')``
(``O_CREAT|O_EXCL``) and treats a lock older than ``maxLockSeconds`` as stale.
There is no owner token, so a lock cannot be safely broken by a process that
merely believes it owns it -- staleness is the only recovery mechanism.

This module reproduces that protocol exactly so PHP and Python can interlock
during a staged cutover. Do not "improve" it by adding ownership metadata until
the legacy writers are gone: unknown keys are written into the file, and the
file content is never read by the legacy code, but the filename derivation and
stale threshold are load-bearing.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Lock", "LockManager", "lock_test", "LockTimeout"]

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9\-_ ]+$")


class LockTimeout(RuntimeError):
    """Raised when a blocking lock could not be acquired in time."""


@dataclass
class Lock:
    """An acquired lock file."""

    name: str
    file: Path
    manager: "LockManager" = field(repr=False)

    def release(self) -> None:
        self.manager.release(self)

    def __enter__(self) -> "Lock":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


class LockManager:
    """Create and release legacy-compatible lock files in ``TEMP_DIR``."""

    def __init__(self, temp_dir: str | os.PathLike[str], *, clock=time.time) -> None:
        self.temp_dir = Path(temp_dir)
        self._clock = clock
        self._held: dict[Path, Lock] = {}
        atexit.register(self.cleanup)

    # ------------------------------------------------------------------
    # filename derivation
    # ------------------------------------------------------------------

    def lock_path(self, name: str) -> Path:
        """Return the lock file path for a logical name.

        Names matching ``^[a-zA-Z0-9-_ ]+$`` use a readable filename; everything
        else is hashed, exactly like the PHP implementation. Note the character
        class: ``-`` sits between ``9`` and ``_`` in ASCII, so it is a literal
        range member, not a range operator.
        """

        if _SAFE_NAME_RE.match(name):
            return self.temp_dir / f"named-{name.replace(' ', '-')}.lock"
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
        return self.temp_dir / f"lock-{digest}.lock"

    # ------------------------------------------------------------------
    # acquire / release
    # ------------------------------------------------------------------

    def acquire(
        self,
        name: str,
        *,
        blocking: bool = True,
        max_lock_seconds: float = 300.0,
    ) -> Lock | None:
        """Acquire ``name``, returning ``None`` when non-blocking and busy."""

        if not name:
            return None

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        path = self.lock_path(name)
        start = time.monotonic()

        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            except FileExistsError:
                if self._break_if_stale(path, max_lock_seconds):
                    continue
                if not blocking:
                    return None
                if time.monotonic() - start >= max_lock_seconds:
                    raise LockTimeout(f"timed out acquiring lock {name!r}")
                time.sleep(random.uniform(0.1, 0.15))
                continue

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(
                        {"name": name, "pid": os.getpid(), "time": self._clock()},
                        handle,
                        indent=4,
                    )
            except OSError:
                pass

            lock = Lock(name=name, file=path, manager=self)
            self._held[path] = lock
            return lock

    def _break_if_stale(self, path: Path, max_lock_seconds: float) -> bool:
        """Remove ``path`` when older than the threshold; report whether we did."""

        try:
            modified = path.stat().st_mtime
        except OSError:
            return False
        if self._clock() - modified > max_lock_seconds:
            try:
                path.unlink()
            except OSError:
                return False
            return True
        return False

    def release(self, lock: Lock) -> None:
        try:
            lock.file.unlink()
        except OSError:
            pass
        self._held.pop(lock.file, None)

    def cleanup(self) -> None:
        """Remove locks still held at interpreter shutdown (PHP does the same)."""

        for path in list(self._held):
            try:
                path.unlink()
            except OSError:
                pass
        self._held.clear()

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------

    def lock_test(self, test_id: str, **kwargs: object) -> Lock | None:
        """``LockTest($id)`` -- locks ``"Test <id>"``."""

        return self.acquire(f"Test {test_id}", **kwargs)  # type: ignore[arg-type]


def lock_test(manager: LockManager, test_id: str, **kwargs: object) -> Lock | None:
    """Functional wrapper for :meth:`LockManager.lock_test`."""

    return manager.lock_test(test_id, **kwargs)
