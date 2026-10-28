"""The daily test-ID counter.

``uniqueId()`` in ``www/common_lib.inc`` keeps ``work/jobs/uniqueId.dat`` as
``{"day": <day-of-year>, "num": <counter>}`` guarded by a named lock. The
counter resets when the day changes. Encoding uses the legacy base-32 alphabet
via :func:`app.domain.testid.num_to_string`.

Failure to take the lock falls back to a random MD5 token, as in PHP.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from ..core import phpjson
from ..domain.testid import num_to_string
from .locks import LockManager

__all__ = ["DailyUniqueId"]


class DailyUniqueId:
    """Allocate monotonically increasing, base-32 encoded test numbers."""

    def __init__(
        self,
        jobs_dir: str | os.PathLike[str],
        locks: LockManager,
        *,
        localtime=None,
    ) -> None:
        self.jobs_dir = Path(jobs_dir)
        self.locks = locks
        self._localtime = localtime or time.localtime
        self.counter = 0

    @property
    def data_file(self) -> Path:
        return self.jobs_dir / "uniqueId.dat"

    def __call__(self) -> str:
        """Allocate the next ID, or fall back to an MD5 token."""

        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        lock = self.locks.acquire("Unique ID")
        if lock is None:
            self.counter = 0
            return _random_token()

        try:
            day = self._day_of_year()
            num = 0
            if self.data_file.is_file():
                try:
                    data = phpjson.loads(self.data_file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    data = None
                if (
                    isinstance(data, dict)
                    and "day" in data
                    and "num" in data
                    and data["day"] == day
                ):
                    try:
                        num = int(data["num"])
                    except (TypeError, ValueError):
                        num = 0

            num += 1
            self.counter = num
            self.data_file.write_text(
                phpjson.dumps({"day": day, "num": num}),
                encoding="utf-8",
            )
            return num_to_string(num)
        finally:
            lock.release()

    def _day_of_year(self) -> int:
        """PHP's ``date('z')``: zero-based day of year in local time."""

        return self._localtime().tm_yday - 1


def _random_token() -> str:
    import hashlib

    return hashlib.md5(os.urandom(16)).hexdigest()
