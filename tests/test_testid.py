"""Test ID generation, sharding and validation."""

from __future__ import annotations

import datetime as dt

import pytest

from app.domain.testid import (
    generate_test_id,
    is_private_id,
    num_to_string,
    shard_key,
    validate_test_id,
)
from app.core.errors import InvalidTestId
from app.domain.testid import require_valid_test_id


@pytest.mark.parametrize(
    "num,expected",
    [(0, "0"), (-1, "0"), (1, "1"), (9, "9"), (10, "A"), (31, "Z"), (32, "10"), (1024, "100")],
)
def test_num_to_string(num: int, expected: str) -> None:
    assert num_to_string(num) == expected


def test_shard_key_default_width() -> None:
    assert shard_key(1, rand_digit=lambda _: "A") == "AA_"


def test_shard_key_custom_width() -> None:
    assert shard_key(1, shard=4, rand_digit=lambda _: "B") == "BBBB_"


@pytest.mark.parametrize("size", [0, 20, -1])
def test_shard_key_disabled_width(size: int) -> None:
    assert shard_key(1, shard=size, rand_digit=lambda _: "A") == ""


def test_shard_key_bucket_grouping() -> None:
    # 25 // 10 == 2 -> "2_"
    assert shard_key(25, bucket_size=10) == "2_"


def test_shard_key_prefixes() -> None:
    key = shard_key(
        1,
        rand_digit=lambda _: "A",
        capture_prefix="cp",
        location_id="Node 1",
        server_id="srv-1",
    )
    # Order is server 'i', location 'x', capture 'c', then the shard.
    assert key == "srv1iNode1xcpcAA_"


def test_shard_key_skips_location_when_no_shard() -> None:
    assert shard_key(1, shard=0, location_id="Node1") == ""


@pytest.mark.parametrize(
    "test_id,ok",
    [
        ("250102_AB_x7k2", True),
        ("080101_x", True),
        ("070101_x", False),
        ("990101_x", False),
        ("250102_AB_x-y", False),
        ("", False),
        ("abc", False),
        ("_250102", False),
    ],
)
def test_validate_test_id(test_id: str, ok: bool) -> None:
    assert validate_test_id(test_id, current_year=2026) is ok


def test_require_valid_test_id_raises() -> None:
    with pytest.raises(InvalidTestId):
        require_valid_test_id("bad id", current_year=2026)


class FakeAllocator:
    def __init__(self, counter: int, value: str) -> None:
        self.counter = counter
        self.value = value

    def __call__(self) -> str:
        return self.value


def test_generate_public_id() -> None:
    test_id = generate_test_id(
        unique_id=FakeAllocator(15, "F"),
        now=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
        rand_digit=lambda _: "A",
    )
    assert test_id == "250102_AA_F"


def test_generate_private_id_uses_md5_suffix() -> None:
    test_id = generate_test_id(
        unique_id=FakeAllocator(15, "F"),
        now=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
        private=True,
        rand_digit=lambda _: "A",
    )
    assert test_id.startswith("250102_AA_")
    assert len(test_id.split("_")[-1]) == 32
    assert is_private_id(test_id)


def test_generate_bucket_size_uses_counter() -> None:
    test_id = generate_test_id(
        unique_id=FakeAllocator(25, "P"),
        now=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
        bucket_size=10,
    )
    assert test_id == "250102_2_P"


def test_generate_avoids_existing_directory() -> None:
    seen = {"250102_AA_F"}

    def exists(candidate: str) -> bool:
        return candidate in seen

    test_id = generate_test_id(
        unique_id=FakeAllocator(15, "F"),
        now=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
        rand_digit=lambda _: "A",
        path_exists=exists,
    )
    assert test_id != "250102_AA_F"
    assert len(test_id.split("_")[-1]) == 32


def test_generate_allocates_counter_even_for_private() -> None:
    calls = []

    class Counting:
        counter = 0

        def __call__(self) -> str:
            calls.append(1)
            self.counter += 1
            return "1"

    generate_test_id(
        unique_id=Counting(),
        now=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
        private=True,
        rand_digit=lambda _: "A",
    )
    assert len(calls) == 1
