"""``GetTestPath`` layout parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.paths import absolute_test_path, get_test_path


@pytest.mark.parametrize(
    "test_id,expected",
    [
        # Modern ID: ymd_shard_suffix -> results/YY/MM/DD/shard/suffix
        ("250102_AB_x7k2", "results/25/01/02/AB/x7k2"),
        ("250102_AB_", "results/25/01/02/AB"),
        # A private ID's 32-char suffix becomes the final path segment.
        (
            "250102_AB_0123456789abcdef0123456789abcdef",
            "results/25/01/02/AB/0123456789abcdef0123456789abcdef",
        ),
        # Only parts[1] and parts[2] are used; anything after is ignored, exactly
        # like PHP's ``$dir .= '/' . $parts[2]``.
        ("250102_ABC_DEF_x7k2", "results/25/01/02/ABC/DEF"),
        # Prefixed shard keys (capture prefix / location / server id).
        ("250102_cpcAB_x7k2", "results/25/01/02/cpcAB/x7k2"),
        ("250102_Node1xcAB_x7k2", "results/25/01/02/Node1xcAB/x7k2"),
        # IDs whose first underscore is not at index 6 use the legacy branch.
        ("12345_AB_x", "results/12345_AB_x"),
        ("abcdef", "results/abcdef"),
    ],
)
def test_modern_and_legacy_paths(test_id: str, expected: str) -> None:
    assert get_test_path(test_id) == expected


def test_olddir_layout() -> None:
    assert get_test_path("12345_AB_x", olddir="old") == "results/old/12345_AB_x"


def test_olddir_with_oldsubdir_layout() -> None:
    assert get_test_path("12345_AB_x", olddir="old", oldsubdir="1") == (
        "results/old/_1/12345_AB_x"
    )


def test_uppercases_legacy_prefix() -> None:
    assert get_test_path("a2345", olddir="old", oldsubdir="1") == "results/old/_A/a2345"


def test_absolute_test_path(tmp_path: Path) -> None:
    result = absolute_test_path(tmp_path, "250102_AB_x7k2")
    assert result == tmp_path / "results" / "25" / "01" / "02" / "AB" / "x7k2"
