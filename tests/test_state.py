"""Lifecycle marker helpers."""

from __future__ import annotations

from pathlib import Path

from app.storage import state


def test_mark_and_has(tmp_path: Path) -> None:
    state.mark(tmp_path, state.WAITING)
    assert state.has(tmp_path, state.WAITING) is True
    assert state.has(tmp_path, state.RUNNING) is False


def test_unmark_is_idempotent(tmp_path: Path) -> None:
    state.unmark(tmp_path, state.WAITING)
    state.mark(tmp_path, state.WAITING)
    state.unmark(tmp_path, state.WAITING)
    assert state.has(tmp_path, state.WAITING) is False


def test_run_complete_markers(tmp_path: Path) -> None:
    state.run_complete(tmp_path, 2)
    state.run_complete(tmp_path, 1)
    state.run_complete(tmp_path, 10)
    assert (tmp_path / "run.complete.2").is_file()
    assert state.completed_runs(tmp_path) == [1, 2, 10]


def test_completed_runs_ignores_other_files(tmp_path: Path) -> None:
    (tmp_path / "run.complete.x").write_text("")
    (tmp_path / "test.complete").write_text("")
    assert state.completed_runs(tmp_path) == []


def test_clear_all_preserves_requested(tmp_path: Path) -> None:
    state.mark(tmp_path, state.COMPLETE)
    state.mark(tmp_path, state.ARCHIVED)
    state.clear_all(tmp_path, keep=(state.ARCHIVED,))
    assert state.has(tmp_path, state.COMPLETE) is False
    assert state.has(tmp_path, state.ARCHIVED) is True
