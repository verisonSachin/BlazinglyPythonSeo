"""Daily test-ID counter parity with ``uniqueId()``."""

from __future__ import annotations

from pathlib import Path

from app.storage.locks import LockManager
from app.storage.uniqueid import DailyUniqueId


class FakeLocaltime:
    def __init__(self, yday: int) -> None:
        self.tm_yday = yday


def make_allocator(tmp_path: Path, yday: int = 1) -> DailyUniqueId:
    return DailyUniqueId(
        tmp_path / "work" / "jobs",
        LockManager(tmp_path / "tmp"),
        localtime=lambda: FakeLocaltime(yday),
    )


def test_counter_increments(tmp_path: Path) -> None:
    allocator = make_allocator(tmp_path)
    assert allocator() == "1"
    assert allocator() == "2"
    assert allocator.counter == 2


def test_data_file_format(tmp_path: Path) -> None:
    allocator = make_allocator(tmp_path)
    allocator()
    data = (tmp_path / "work" / "jobs" / "uniqueId.dat").read_text()
    assert data == '{"day":0,"num":1}'


def test_counter_resets_on_new_day(tmp_path: Path) -> None:
    jobs = tmp_path / "work" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "uniqueId.dat").write_text('{"day":0,"num":9}')

    allocator = make_allocator(tmp_path, yday=2)
    assert allocator() == "1"


def test_counter_continues_same_day(tmp_path: Path) -> None:
    jobs = tmp_path / "work" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "uniqueId.dat").write_text('{"day":0,"num":9}')

    allocator = make_allocator(tmp_path, yday=1)
    assert allocator() == "A"  # 10 in base 32


def test_encoded_beyond_32(tmp_path: Path) -> None:
    allocator = make_allocator(tmp_path)
    for _ in range(32):
        result = allocator()
    assert result == "10"
