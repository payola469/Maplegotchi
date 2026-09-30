"""Shared helpers for storage and runtime tests. All time is fake."""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from maplegotchi.core.parameters import CoreParameters
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import DB_FILENAME

BIRTH = datetime(2026, 1, 1, tzinfo=UTC)  # 07:00 in Asia/Bangkok
SEED = "5e" * 32
PARAMS = CoreParameters()
TICK = PARAMS.heartbeat_interval


def fixed_seed() -> str:
    return SEED


def make_data_dir(tmp_path: Path, name: str = "maple-data") -> DataDir:
    root = tmp_path / name
    root.mkdir()
    return DataDir(root)


def open_runtime(data_dir: DataDir, clock: FakeClock) -> LifeRuntime:
    return LifeRuntime.open(data_dir, clock, PARAMS, new_seed=fixed_seed)


def new_life(tmp_path: Path, name: str = "maple-data") -> tuple[DataDir, FakeClock, LifeRuntime]:
    data_dir = make_data_dir(tmp_path, name)
    clock = FakeClock(BIRTH)
    return data_dir, clock, open_runtime(data_dir, clock)


def run_ticks(runtime: LifeRuntime, clock: FakeClock, count: int) -> None:
    for _ in range(count):
        clock.advance(TICK)
        assert runtime.heartbeat_if_due() is not None


@contextmanager
def raw_db(data_dir: DataDir) -> Iterator[sqlite3.Connection]:
    """A plain connection to maple.db for inspecting or deliberately damaging it."""
    conn = sqlite3.connect(data_dir.path(DB_FILENAME), isolation_level=None)
    try:
        yield conn
    finally:
        conn.close()


def make_dir_link(link: Path, target: Path) -> None:
    """Directory symlink, or an NTFS junction on Windows without symlink privilege."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform == "win32":
            import _winapi  # junctions need no special privilege

            _winapi.CreateJunction(str(target), str(link))
        else:
            pytest.skip("cannot create directory symlinks here")


def make_file_link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("cannot create file symlinks here (Windows needs privilege)")


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)
