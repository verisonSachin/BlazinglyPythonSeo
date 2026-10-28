"""The work queue.

The legacy queue is a gzip-compressed JSON document at
``tmp/<sha1(workDir)>.queue`` whose payload is a **10-element list of lists**:
priority ``0`` through ``9``, each holding job filenames. PHP's ``json_encode``
emits a JSON array (not an object) because the keys are sequential, so keeping a
``list[list[str]]`` in Python is what preserves byte compatibility.

When the file is missing or effectively empty, the queue is rebuilt by scanning
``work/jobs/<location>`` in sorted order: ``*.url`` files become priority 0 and
``*.pN`` files become priority N. That rescan is a recovery mechanism, not a
fallback -- dropping it would strand jobs after a lost ``tmp/`` volume.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ..core import phpjson
from .gzipio import gz_file_get_contents, gz_file_put_contents

__all__ = [
    "PRIORITIES",
    "work_dir_for",
    "queue_path",
    "empty_queue",
    "JobQueue",
]

PRIORITIES = range(10)
_PRIORITY_FILE_RE = re.compile(r"\.p([1-9])", re.IGNORECASE)


def work_dir_for(location: str) -> str:
    """Return the legacy work-directory string (note the leading ``./``)."""

    return f"./work/jobs/{location}"


def queue_path(tmp_dir: str | os.PathLike[str], work_dir: str) -> Path:
    """Return ``tmp/<sha1(work_dir)>.queue`` (the gzip suffix is added on write)."""

    digest = hashlib.sha1(work_dir.encode("utf-8")).hexdigest()
    return Path(tmp_dir) / f"{digest}.queue"


def empty_queue() -> list[list[str]]:
    return [[] for _ in PRIORITIES]


class JobQueue:
    """Read/write the legacy per-location job queue."""

    def __init__(
        self,
        tmp_dir: str | os.PathLike[str],
        work_dir: str,
        *,
        jobs_root: str | os.PathLike[str] | None = None,
        nogzip: bool = False,
        compression: int = 6,
        use_files: bool = True,
    ) -> None:
        self.tmp_dir = Path(tmp_dir)
        self.work_dir = work_dir
        self.path = queue_path(self.tmp_dir, work_dir)
        self.jobs_root = Path(jobs_root) if jobs_root is not None else None
        self.nogzip = nogzip
        self.compression = compression
        self.use_files = use_files

    # ------------------------------------------------------------------
    # load / save
    # ------------------------------------------------------------------

    def load(self) -> list[list[str]]:
        """Load the queue, rescanning the job directory when it is empty."""

        if not self.use_files:
            return empty_queue()

        queue: list[list[str]] | None = None
        if self.path.is_file() or Path(f"{self.path}.gz").is_file():
            raw = gz_file_get_contents(self.path)
            if raw is not None:
                try:
                    decoded = phpjson.loads(raw)
                except ValueError:
                    decoded = None
                queue = _normalise(decoded)

        if queue is not None and not _is_effectively_empty(queue):
            return queue

        rebuilt = self._scan_jobs()
        if rebuilt is not None:
            self.save(rebuilt)
            return rebuilt

        return queue if queue is not None else empty_queue()

    def save(self, queue: list[list[str]]) -> bool:
        """Persist the queue; creates ``tmp/`` when needed."""

        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        return gz_file_put_contents(
            self.path,
            phpjson.dumps(_normalise(queue)),
            nogzip=self.nogzip,
            compression=self.compression,
        )

    def _scan_jobs(self) -> list[list[str]] | None:
        if self.jobs_root is None:
            return None
        if not self.jobs_root.is_dir():
            return None

        queue = empty_queue()
        for name in sorted(os.listdir(self.jobs_root)):
            lowered = name.lower()
            if ".url" in lowered and lowered.index(".url") > 0:
                queue[0].append(name)
                continue
            match = _PRIORITY_FILE_RE.search(name)
            if match:
                queue[int(match.group(1))].append(name)
        return queue

    # ------------------------------------------------------------------
    # mutation
    # ------------------------------------------------------------------

    def add(self, filename: str, priority: int, *, queue_limit: int = 0) -> bool:
        """Append a job file, honouring the optional per-priority limit."""

        if not 0 <= priority <= 9:
            raise ValueError(f"priority out of range: {priority}")

        queue = self.load()
        if queue_limit and len(queue[priority]) >= queue_limit:
            return False
        queue[priority].append(filename)
        return self.save(queue)

    def lengths(self) -> list[int]:
        return [len(priority) for priority in self.load()]

    def find_position(self, test_id: str) -> int:
        """Return a job's queue position, or ``-1`` when it is not queued.

        Case-insensitive substring match, matching ``stripos($file, $testId)``.
        """

        needle = test_id.lower()
        count = 0
        for priority in self.load():
            for filename in priority:
                if needle in filename.lower():
                    return count
                count += 1
        return -1


def _normalise(value: object) -> list[list[str]]:
    """Coerce a decoded queue into exactly ten lists of strings."""

    queue = empty_queue()
    if isinstance(value, dict):
        for raw_key, items in value.items():
            try:
                index = int(raw_key)
            except (TypeError, ValueError):
                continue
            if index in PRIORITIES and isinstance(items, list):
                queue[index] = [str(item) for item in items]
        return queue
    if isinstance(value, list):
        for index, items in enumerate(value[:10]):
            if isinstance(items, list):
                queue[index] = [str(item) for item in items]
    return queue


def _is_effectively_empty(queue: list[list[str]]) -> bool:
    """PHP treats a queue holding only tester-affinity jobs as empty."""

    for priority in queue:
        for filename in priority:
            if not filename.startswith("AffinityTester"):
                return False
    return True
