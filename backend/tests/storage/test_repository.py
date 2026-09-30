"""Repository: exact round trips, atomic commits, and refusal of invalid persisted data."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.state import InteractionKind, Needs, ReactionKind
from maplegotchi.core.timeline import (
    ActivityChanged,
    Born,
    DowntimeGap,
    InteractionAccepted,
    LifeEvent,
)
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.errors import (
    ConcurrentWriteError,
    CorruptDatabaseError,
    CorruptStateError,
    StorageError,
)
from maplegotchi.storage.repositories import LifeRepository, decode_event, encode_event
from tests.persistence_support import BIRTH, new_life, open_runtime, raw_db, run_ticks

# ---------------------------------------------------------------- round trips


def test_state_round_trips_exactly(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 200)
    runtime.interact(InteractionKind.GREET)
    clock.advance(timedelta(seconds=3))
    runtime.interact(InteractionKind.PET)
    live = runtime.state
    assert live.reaction is not None and len(live.recent_interactions) == 2
    runtime.close()
    with open_runtime(data_dir, clock) as reloaded:
        assert reloaded.state == live
        # Exact float identity, not approximate equality.
        assert reloaded.state.needs.mood.hex() == live.needs.mood.hex()


@pytest.mark.parametrize("value", [0.1 + 0.2, 1e-300, 5e-324, 99.99999999999999, 100.0, 0.0])
def test_awkward_floats_round_trip_bit_for_bit(tmp_path: Path, value: float) -> None:
    data_dir, _, runtime = new_life(tmp_path)
    repo = runtime._repository()
    tweaked = replace(
        runtime.state, needs=Needs(mood=value, energy=value, curiosity=value, social=value)
    )
    repo.commit(tweaked, expected_revision=runtime.revision, events=())
    runtime.close()
    with raw_db(data_dir) as conn:
        loaded = LifeRepository(conn).load().state
    assert loaded.needs.mood.hex() == value.hex()


EVENTS: list[LifeEvent] = [
    Born(at=BIRTH, name="Maple"),
    ActivityChanged(at=BIRTH, previous=Activity.IDLE, current=Activity.READ),
    InteractionAccepted(at=BIRTH, kind=InteractionKind.PET, reaction=ReactionKind.PET_SLEEPY),
    DowntimeGap(since=BIRTH - timedelta(days=3), until=BIRTH),
]


@pytest.mark.parametrize("event", EVENTS)
def test_event_codec_round_trips(event: LifeEvent) -> None:
    assert decode_event(*encode_event(event)) == event


def test_unknown_event_kind_is_corrupt() -> None:
    with pytest.raises(CorruptStateError):
        decode_event("teleported", "2026-01-01T00:00:00+00:00", "{}")


# ---------------------------------------------------------------- atomicity


def _db_snapshot(data_dir: DataDir) -> tuple[object, ...]:
    with raw_db(data_dir) as conn:
        return (
            conn.execute("SELECT * FROM life_state").fetchall(),
            conn.execute("SELECT * FROM interaction_ledger ORDER BY position").fetchall(),
            conn.execute("SELECT * FROM timeline_event ORDER BY id").fetchall(),
        )


def test_failure_after_partial_writes_rolls_everything_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    before_db = _db_snapshot(data_dir)
    before_state, before_revision = runtime.state, runtime.revision

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("disk full while appending events")

    # The life_state UPDATE and ledger rewrite have already run when this fires.
    monkeypatch.setattr(LifeRepository, "_insert_events", explode)
    with pytest.raises(OSError):
        runtime.interact(InteractionKind.GREET)
    assert runtime.state == before_state and runtime.revision == before_revision
    assert _db_snapshot(data_dir) == before_db

    monkeypatch.undo()
    outcome = runtime.interact(InteractionKind.GREET)  # same transition succeeds on retry
    assert runtime.revision == before_revision + 1
    assert outcome.__class__.__name__ == "Accepted"
    runtime.close()


def test_uncommitted_transaction_is_lost_on_crash(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    expected = runtime.state
    runtime.close()
    crashed = sqlite3.connect(data_dir.path("maple.db"), isolation_level=None)
    crashed.execute("BEGIN IMMEDIATE")
    crashed.execute("UPDATE life_state SET revision = revision + 1, mood = 0, tick_counter = 999")
    crashed.execute("DELETE FROM interaction_ledger")
    crashed.close()  # process dies before COMMIT
    with open_runtime(data_dir, clock) as reloaded:
        assert reloaded.state == expected


def test_stale_revision_is_rejected(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    with runtime:
        repo = runtime._repository()
        with pytest.raises(ConcurrentWriteError):
            repo.commit(runtime.state, expected_revision=runtime.revision + 5, events=())


def test_identity_and_seed_cannot_change(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    with runtime:
        repo = runtime._repository()
        s = runtime.state
        impostor = replace(s, identity=replace(s.identity, name="Impostor"))
        reseeded = replace(s, rng=replace(s.rng, seed_hex="00" * 32))
        for bad in (impostor, reseeded):
            with pytest.raises(StorageError, match="never change"):
                repo.commit(bad, expected_revision=runtime.revision, events=())


# ---------------------------------------------------------------- invalid persisted data


def _damage(data_dir: DataDir, *statements: str) -> None:
    with raw_db(data_dir) as conn:
        conn.execute("PRAGMA ignore_check_constraints = ON")
        for sql in statements:
            conn.execute(sql)


BUMP = "UPDATE life_state SET revision = revision + 1, "

DAMAGE = {
    "location impossible for activity": [BUMP + "activity = 'sleep', location = 'desk'"],
    "tick after update": [BUMP + "last_tick_at = '2030-01-01T00:00:00+00:00'"],
    "non-UTC timestamp": [BUMP + "last_updated_at = '2026-01-01T07:00:00+07:00'"],
    "unknown activity": [BUMP + "activity = 'dance'"],
    "need out of range": [BUMP + "mood = 150.0"],
    "reaction ends before it starts": [
        BUMP + "reaction_kind = 'pet_happy', reaction_variant = 0,"
        " reaction_started_at = '2026-01-01T00:00:08+00:00',"
        " reaction_until = '2026-01-01T00:00:00+00:00'"
    ],
    "ledger gap": [
        "INSERT INTO interaction_ledger VALUES (1, 1, 'greet', '2026-01-01T00:00:00+00:00')"
    ],
    "unknown interaction kind": [
        "INSERT INTO interaction_ledger VALUES (1, 0, 'feed', '2026-01-01T00:00:00+00:00')"
    ],
    "missing life state": ["DROP TRIGGER life_state_no_delete", "DELETE FROM life_state"],
    "second birth": [
        "DROP INDEX timeline_event_one_birth",
        "INSERT INTO timeline_event (maple_id, revision, kind, at, payload)"
        " VALUES (1, 1, 'born', '2026-01-01T00:00:00+00:00', '{\"name\":\"Twin\"}')",
    ],
    "no birth": ["DROP TRIGGER timeline_event_append_only_delete", "DELETE FROM timeline_event"],
    "bad seed": [
        "DROP TRIGGER maple_immutable_update",
        "UPDATE maple SET life_seed = 'NOT-HEX'",
    ],
}


# Values smuggled past SQL CHECK constraints are caught by SQLite's integrity
# check; values that satisfy SQL but break a core invariant are caught when
# core rebuilds the state. Either way: loud failure, no repair.
CAUGHT_BY_INTEGRITY_CHECK = {
    "non-UTC timestamp",
    "unknown activity",
    "need out of range",
    "unknown interaction kind",
    "bad seed",
}


@pytest.mark.parametrize("case", sorted(DAMAGE))
def test_invalid_persisted_state_fails_loudly_and_is_not_repaired(
    tmp_path: Path, case: str
) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 2)
    runtime.close()
    _damage(data_dir, *DAMAGE[case])
    damaged = _db_snapshot(data_dir)
    expected = CorruptDatabaseError if case in CAUGHT_BY_INTEGRITY_CHECK else CorruptStateError
    with pytest.raises(expected):
        open_runtime(data_dir, clock)
    assert _db_snapshot(data_dir) == damaged


def test_room_location_values_are_the_stored_strings() -> None:
    assert {loc.value for loc in RoomLocation} >= {"desk", "bed"}
