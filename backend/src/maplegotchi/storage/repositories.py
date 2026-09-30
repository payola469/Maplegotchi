"""Maple's canonical state <-> SQLite rows.

A logical commit (one heartbeat or one accepted interaction) writes the life
state row, the interaction ledger, and its timeline events in ONE transaction,
guarded by an optimistic revision check. Loading validates rows through core's
own invariants; anything that does not form a valid Maple raises
CorruptStateError rather than being repaired or replaced.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.identity import Identity
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import (
    InteractionKind,
    InteractionRecord,
    MapleState,
    Needs,
    Reaction,
    ReactionKind,
)
from maplegotchi.core.timeline import (
    ActivityChanged,
    Born,
    DowntimeGap,
    InteractionAccepted,
    LifeEvent,
)
from maplegotchi.storage.errors import ConcurrentWriteError, CorruptStateError, StorageError

MAPLE_ID = 1


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any failure (including in COMMIT)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def _parse_ts(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    require_utc(value)
    return value


@dataclass(frozen=True, slots=True)
class StoredLife:
    state: MapleState
    revision: int


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: int
    revision: int
    tick_id: int | None
    event: LifeEvent


# ---------------------------------------------------------------- event codec


def encode_event(event: LifeEvent) -> tuple[str, str, str]:
    """(kind, at, payload JSON) for a timeline row."""
    payload: dict[str, Any]
    match event:
        case Born(at=at, name=name):
            kind, payload = "born", {"name": name}
        case ActivityChanged(at=at, previous=previous, current=current):
            kind, payload = (
                "activity_changed",
                {"previous": previous.value, "current": current.value},
            )
        case InteractionAccepted(at=at, kind=interaction, reaction=reaction):
            kind, payload = (
                "interaction_accepted",
                {"kind": interaction.value, "reaction": reaction.value},
            )
        case DowntimeGap(since=since, until=at):
            kind, payload = "downtime_gap", {"since": _ts(since)}
        case _:
            raise TypeError(f"unknown life event {event!r}")
    return kind, _ts(at), json.dumps(payload, sort_keys=True, separators=(",", ":"))


def decode_event(kind: str, at_text: str, payload_text: str) -> LifeEvent:
    at = _parse_ts(at_text)
    payload = json.loads(payload_text)
    if kind == "born":
        return Born(at=at, name=str(payload["name"]))
    if kind == "activity_changed":
        return ActivityChanged(
            at=at, previous=Activity(payload["previous"]), current=Activity(payload["current"])
        )
    if kind == "interaction_accepted":
        return InteractionAccepted(
            at=at,
            kind=InteractionKind(payload["kind"]),
            reaction=ReactionKind(payload["reaction"]),
        )
    if kind == "downtime_gap":
        return DowntimeGap(since=_parse_ts(payload["since"]), until=at)
    raise CorruptStateError(f"unknown timeline event kind {kind!r}")


# ---------------------------------------------------------------- repository

_STATE_COLUMNS = (
    "mood, energy, curiosity, social, activity, location, activity_started_at, "
    "activity_until, last_tick_at, last_updated_at, tick_counter, interaction_counter, "
    "reaction_kind, reaction_variant, reaction_started_at, reaction_until"
)


def _state_values(state: MapleState) -> tuple[object, ...]:
    r = state.reaction
    return (
        state.needs.mood,
        state.needs.energy,
        state.needs.curiosity,
        state.needs.social,
        state.activity.value,
        state.location.value,
        _ts(state.activity_started_at),
        _ts(state.activity_until),
        _ts(state.last_tick_at),
        _ts(state.last_updated_at),
        state.rng.tick_counter,
        state.rng.interaction_counter,
        r.kind.value if r else None,
        r.variant if r else None,
        _ts(r.started_at) if r else None,
        _ts(r.until) if r else None,
    )


class LifeRepository:
    """Owns the database connection; runtime never touches SQLite directly."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def close(self) -> None:
        self._conn.close()

    def has_life(self) -> bool:
        count: int = self._conn.execute("SELECT count(*) FROM maple").fetchone()[0]
        return count > 0

    def create(self, state: MapleState, born: Born) -> int:
        """Persist a newborn Maple and its birth event. Returns revision 1."""
        if born.at != state.identity.born_at or born.name != state.identity.name:
            raise ValueError("birth event must match the new Maple's identity")
        if state.rng.tick_counter or state.rng.interaction_counter or state.recent_interactions:
            raise ValueError("a newborn Maple has no history")
        with transaction(self._conn):
            existing = self._conn.execute(
                "SELECT (SELECT count(*) FROM maple) + (SELECT count(*) FROM life_state)"
                " + (SELECT count(*) FROM timeline_event)"
            ).fetchone()[0]
            if existing:
                raise StorageError("a Maple life already exists; birth happens once")
            self._conn.execute(
                "INSERT INTO maple (id, name, born_at, life_seed) VALUES (?, ?, ?, ?)",
                (MAPLE_ID, state.identity.name, _ts(state.identity.born_at), state.rng.seed_hex),
            )
            self._conn.execute(
                f"INSERT INTO life_state (maple_id, revision, {_STATE_COLUMNS})"  # noqa: S608
                " VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (MAPLE_ID, *_state_values(state)),
            )
            self._insert_events(1, (born,), None)
        return 1

    def load(self) -> StoredLife:
        try:
            return self._load()
        except CorruptStateError:
            raise
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise CorruptStateError(f"persisted Maple state is invalid: {exc}") from exc

    def _load(self) -> StoredLife:
        identity_row = self._conn.execute(
            "SELECT name, born_at, life_seed FROM maple WHERE id = ?", (MAPLE_ID,)
        ).fetchone()
        state_row = self._conn.execute(
            f"SELECT revision, {_STATE_COLUMNS} FROM life_state WHERE maple_id = ?",  # noqa: S608
            (MAPLE_ID,),
        ).fetchone()
        if identity_row is None or state_row is None:
            raise CorruptStateError("Maple identity or life state row is missing")
        births = self._conn.execute(
            "SELECT count(*) FROM timeline_event WHERE kind = 'born'"
        ).fetchone()[0]
        if births != 1:
            raise CorruptStateError(f"expected exactly one birth event, found {births}")

        name, born_at, seed = identity_row
        (revision, mood, energy, curiosity, social, activity, location, started, until,
         last_tick, last_update, ticks, interactions,
         r_kind, r_variant, r_start, r_until) = state_row  # fmt: skip
        ledger = self._conn.execute(
            "SELECT position, kind, at FROM interaction_ledger WHERE maple_id = ?"
            " ORDER BY position",
            (MAPLE_ID,),
        ).fetchall()
        if [row[0] for row in ledger] != list(range(len(ledger))):
            raise CorruptStateError("interaction ledger positions are not contiguous")

        reaction = None
        if r_kind is not None:
            reaction = Reaction(
                kind=ReactionKind(r_kind),
                variant=r_variant,
                started_at=_parse_ts(r_start),
                until=_parse_ts(r_until),
            )
        state = MapleState(
            identity=Identity(name=name, born_at=_parse_ts(born_at)),
            needs=Needs(mood=mood, energy=energy, curiosity=curiosity, social=social),
            activity=Activity(activity),
            location=RoomLocation(location),
            activity_started_at=_parse_ts(started),
            activity_until=_parse_ts(until),
            last_tick_at=_parse_ts(last_tick),
            last_updated_at=_parse_ts(last_update),
            rng=RngState(seed_hex=seed, tick_counter=ticks, interaction_counter=interactions),
            recent_interactions=tuple(
                InteractionRecord(kind=InteractionKind(kind), at=_parse_ts(at))
                for _, kind, at in ledger
            ),
            reaction=reaction,
        )
        return StoredLife(state=state, revision=revision)

    def commit(
        self,
        state: MapleState,
        *,
        expected_revision: int,
        events: Sequence[LifeEvent],
        tick_id: int | None = None,
    ) -> int:
        """Atomically replace Maple's state and append events. Returns the new revision."""
        new_revision = expected_revision + 1
        with transaction(self._conn):
            identity_row = self._conn.execute(
                "SELECT name, born_at, life_seed FROM maple WHERE id = ?", (MAPLE_ID,)
            ).fetchone()
            if identity_row != (
                state.identity.name,
                _ts(state.identity.born_at),
                state.rng.seed_hex,
            ):
                raise StorageError("identity and life seed can never change")
            updated = self._conn.execute(
                f"UPDATE life_state SET revision = ?, ({_STATE_COLUMNS})"  # noqa: S608
                " = (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " WHERE maple_id = ? AND revision = ?",
                (new_revision, *_state_values(state), MAPLE_ID, expected_revision),
            ).rowcount
            if updated != 1:
                raise ConcurrentWriteError(
                    f"life state is no longer at revision {expected_revision}"
                )
            self._conn.execute("DELETE FROM interaction_ledger WHERE maple_id = ?", (MAPLE_ID,))
            self._conn.executemany(
                "INSERT INTO interaction_ledger (maple_id, position, kind, at) VALUES (?, ?, ?, ?)",
                [
                    (MAPLE_ID, i, r.kind.value, _ts(r.at))
                    for i, r in enumerate(state.recent_interactions)
                ],
            )
            self._insert_events(new_revision, events, tick_id)
        return new_revision

    def _insert_events(
        self, revision: int, events: Sequence[LifeEvent], tick_id: int | None
    ) -> None:
        for event in events:
            kind, at, payload = encode_event(event)
            self._conn.execute(
                "INSERT INTO timeline_event (maple_id, revision, tick_id, kind, at, payload)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (MAPLE_ID, revision, tick_id, kind, at, payload),
            )

    def events(self) -> list[StoredEvent]:
        rows = self._conn.execute(
            "SELECT id, revision, tick_id, kind, at, payload FROM timeline_event ORDER BY id"
        ).fetchall()
        try:
            return [
                StoredEvent(id=i, revision=rev, tick_id=tick, event=decode_event(kind, at, p))
                for i, rev, tick, kind, at, p in rows
            ]
        except (ValueError, TypeError, KeyError) as exc:
            raise CorruptStateError(f"timeline event is invalid: {exc}") from exc

    def birth(self) -> Born:
        births = [e.event for e in self.events() if isinstance(e.event, Born)]
        if len(births) != 1:
            raise CorruptStateError(f"expected exactly one birth event, found {len(births)}")
        return births[0]
