"""Test lifecycle markers.

The legacy state machine is file-presence based inside the test directory. There
is no status column anywhere; ``testStatus.php`` and the agent endpoints derive
everything from these files plus ``run.complete.N`` markers.

Markers (see ``www/common_lib.inc`` and ``www/work/*``):

===================  =========================================================
``test.waiting``     queued, not yet picked up
``test.scheduled``   queued through the Catchpoint scheduler
``test.running``     an agent has started
``test.requeued``    returned to the queue after a failure
``test.complete``    all runs finished / post-processing done
``run.complete.N``   run N finished
``.archived``        moved to archival storage
===================  =========================================================
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "WAITING",
    "SCHEDULED",
    "RUNNING",
    "REQUEUED",
    "COMPLETE",
    "ARCHIVED",
    "mark",
    "unmark",
    "has",
    "run_complete",
    "completed_runs",
]

WAITING = "test.waiting"
SCHEDULED = "test.scheduled"
RUNNING = "test.running"
REQUEUED = "test.requeued"
COMPLETE = "test.complete"
ARCHIVED = ".archived"

_ALL_MARKERS = (WAITING, SCHEDULED, RUNNING, REQUEUED, COMPLETE, ARCHIVED)


def mark(test_dir: str | os.PathLike[str], marker: str) -> Path:
    """Create ``marker`` in ``test_dir`` and return its path."""

    path = Path(test_dir) / marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return path


def unmark(test_dir: str | os.PathLike[str], marker: str) -> None:
    try:
        (Path(test_dir) / marker).unlink()
    except FileNotFoundError:
        pass


def has(test_dir: str | os.PathLike[str], marker: str) -> bool:
    return (Path(test_dir) / marker).is_file()


def run_complete(test_dir: str | os.PathLike[str], run: int) -> Path:
    """Create ``run.complete.N``."""

    return mark(test_dir, f"run.complete.{run}")


def completed_runs(test_dir: str | os.PathLike[str]) -> list[int]:
    """Return the run numbers that have a completion marker, ascending."""

    directory = Path(test_dir)
    if not directory.is_dir():
        return []
    runs: list[int] = []
    for entry in directory.iterdir():
        name = entry.name
        if name.startswith("run.complete."):
            suffix = name[len("run.complete.") :]
            if suffix.isdigit():
                runs.append(int(suffix))
    return sorted(runs)


def clear_all(test_dir: str | os.PathLike[str], *, keep: tuple[str, ...] = ()) -> None:
    """Remove lifecycle markers, optionally preserving some."""

    for marker in _ALL_MARKERS:
        if marker not in keep:
            unmark(test_dir, marker)
