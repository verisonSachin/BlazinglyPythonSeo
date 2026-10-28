"""Work queue format and recovery behaviour."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from app.storage.queue import JobQueue, empty_queue, queue_path, work_dir_for


def make_queue(tmp_path: Path, jobs: Path | None = None) -> JobQueue:
    work_dir = work_dir_for("Test")
    return JobQueue(tmp_path / "tmp", work_dir, jobs_root=jobs)


def test_queue_path_is_sha1_of_work_dir(tmp_path: Path) -> None:
    work_dir = "./work/jobs/Test"
    expected = hashlib.sha1(work_dir.encode()).hexdigest()
    assert queue_path(tmp_path, work_dir).name == f"{expected}.queue"


def test_empty_queue_shape() -> None:
    assert empty_queue() == [[] for _ in range(10)]


def test_save_writes_php_style_json(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    queue.add("250102_AB_x.url", 0)
    queue.add("250102_AB_x.p3", 3)

    raw = gzip.decompress(Path(f"{queue.path}.gz").read_bytes())
    assert json.loads(raw) == [
        ["250102_AB_x.url"],
        [],
        [],
        ["250102_AB_x.p3"],
        [],
        [],
        [],
        [],
        [],
        [],
    ]


def test_roundtrip(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    queue.add("a.url", 0)
    queue.add("b.p9", 9)

    reloaded = make_queue(tmp_path)
    assert reloaded.load() == queue.load()


def test_add_respects_queue_limit(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    assert queue.add("a.url", 0, queue_limit=1) is True
    assert queue.add("b.url", 0, queue_limit=1) is False
    assert queue.lengths()[0] == 1


def test_rebuild_from_job_directory(tmp_path: Path) -> None:
    jobs = tmp_path / "work" / "jobs" / "Test"
    jobs.mkdir(parents=True)
    (jobs / "a.url").write_text("")
    (jobs / "b.p3").write_text("")
    (jobs / "c.p0").write_text("")  # .p0 is not a valid priority suffix

    queue = make_queue(tmp_path, jobs)
    loaded = queue.load()
    assert loaded[0] == ["a.url"]
    assert loaded[3] == ["b.p3"]
    assert all("c.p0" not in priority for priority in loaded)


def test_empty_queue_file_triggers_rescan(tmp_path: Path) -> None:
    jobs = tmp_path / "work" / "jobs" / "Test"
    jobs.mkdir(parents=True)
    (jobs / "later.url").write_text("")

    queue = make_queue(tmp_path, jobs)
    queue.save(empty_queue())
    assert queue.load()[0] == ["later.url"]


def test_find_position(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    queue.add("first.url", 0)
    queue.add("second.p4", 4)

    assert queue.find_position("first") == 0
    assert queue.find_position("second") == 1
    assert queue.find_position("absent") == -1


def test_find_position_is_case_insensitive(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    queue.add("250102_AB_X.url", 0)
    assert queue.find_position("250102_ab_x") == 0


def test_invalid_priority_rejected(tmp_path: Path) -> None:
    queue = make_queue(tmp_path)
    try:
        queue.add("x.url", 10)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
