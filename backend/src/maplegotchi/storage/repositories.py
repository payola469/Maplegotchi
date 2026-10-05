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
from datetime import date, datetime
from typing import Any

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.audit import ActionEvent, DecisionRecord
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import Goal, GoalEndReason, GoalSource, GoalType
from maplegotchi.core.identity import Identity
from maplegotchi.core.journal import (
    BrainKind,
    Importance,
    JournalCategory,
    JournalEntry,
    TriggerKind,
)
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.priority import Priority
from maplegotchi.core.reflection import INITIAL_REFLECTION, ReflectionState
from maplegotchi.core.rng import RngState
from maplegotchi.core.room import PathPoint, Route
from maplegotchi.core.state import (
    Expression,
    InteractionKind,
    InteractionRecord,
    MapleState,
    Needs,
    Reaction,
    ReactionKind,
)
from maplegotchi.core.tasks import Task, Tool, ToolOp, ToolRecord
from maplegotchi.core.timeline import (
    ActivityChanged,
    Born,
    DowntimeGap,
    GoalAbandoned,
    GoalCompleted,
    GoalResumed,
    GoalStarted,
    GoalSuspended,
    InteractionAccepted,
    LifeEvent,
)
from maplegotchi.storage import audit_rows, tool_rows
from maplegotchi.storage.audit_rows import StoredActionEvent, StoredDecision
from maplegotchi.storage.errors import ConcurrentWriteError, CorruptStateError, StorageError
from maplegotchi.storage.tool_rows import StoredDocument, StoredToolUse

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


@contextmanager
def read_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """One consistent read snapshot: every SELECT inside sees the same committed state."""
    conn.execute("BEGIN")
    try:
        yield
    finally:
        if conn.in_transaction:
            conn.execute("COMMIT")  # read-only: nothing to commit, just ends the snapshot


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
class StoredObservation:
    id: int
    revision: int
    tick_id: int
    observation: Observation


@dataclass(frozen=True, slots=True)
class StoredJournalEntry:
    id: int
    revision: int
    entry: JournalEntry
    observation_ids: tuple[int, ...]  # the facts it interprets, in reference order


@dataclass(frozen=True, slots=True)
class PersistedView:
    """Everything a snapshot needs, read from one committed database state."""

    life: StoredLife
    reflection: ReflectionState
    observations: tuple[StoredObservation, ...]  # the latest observed heartbeat's
    journal: tuple[StoredJournalEntry, ...]  # most recent, oldest first
    timeline: tuple[StoredEvent, ...]  # most recent, oldest first


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
        case GoalStarted(at=at, goal=goal):
            kind, payload = (
                "goal_started",
                {
                    "goal_id": goal.id,
                    "goal_type": goal.type.value,
                    "summary": goal.summary,
                    "source": goal.source.value,
                    "horizon_until": _ts(goal.horizon_until),
                },
            )
        case GoalSuspended(at=at, goal_id=goal_id, goal_type=goal_type, cause=cause):
            kind, payload = (
                "goal_suspended",
                {"goal_id": goal_id, "goal_type": goal_type.value, "cause": cause},
            )
        case GoalResumed(at=at, goal_id=goal_id, goal_type=goal_type):
            kind, payload = "goal_resumed", {"goal_id": goal_id, "goal_type": goal_type.value}
        case GoalCompleted(at=at, goal_id=goal_id, goal_type=goal_type, reason=reason):
            kind, payload = (
                "goal_completed",
                {"goal_id": goal_id, "goal_type": goal_type.value, "reason": reason.value},
            )
        case GoalAbandoned(at=at, goal_id=goal_id, goal_type=goal_type, reason=reason):
            kind, payload = (
                "goal_abandoned",
                {"goal_id": goal_id, "goal_type": goal_type.value, "reason": reason.value},
            )
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
    if kind == "goal_started":
        return GoalStarted(
            at=at,
            goal=Goal(
                id=int(payload["goal_id"]),
                type=GoalType(payload["goal_type"]),
                summary=str(payload["summary"]),
                source=GoalSource(payload["source"]),
                started_at=at,
                horizon_until=_parse_ts(payload["horizon_until"]),
            ),
        )
    if kind == "goal_suspended":
        return GoalSuspended(
            at=at,
            goal_id=int(payload["goal_id"]),
            goal_type=GoalType(payload["goal_type"]),
            cause=str(payload["cause"]),
        )
    if kind == "goal_resumed":
        return GoalResumed(
            at=at, goal_id=int(payload["goal_id"]), goal_type=GoalType(payload["goal_type"])
        )
    if kind in ("goal_completed", "goal_abandoned"):
        cls = GoalCompleted if kind == "goal_completed" else GoalAbandoned
        return cls(
            at=at,
            goal_id=int(payload["goal_id"]),
            goal_type=GoalType(payload["goal_type"]),
            reason=GoalEndReason(payload["reason"]),
        )
    raise CorruptStateError(f"unknown timeline event kind {kind!r}")


# ---------------------------------------------------------------- repository

_STATE_COLUMNS = (
    "mood, energy, curiosity, social, activity, location, activity_started_at, "
    "activity_until, last_tick_at, last_updated_at, tick_counter, interaction_counter, "
    "reaction_kind, reaction_variant, reaction_started_at, reaction_until, "
    "point_id, route_departed_at, route_from_activity, route_path, "
    "needs_at, decision_counter, action_counter, goal_counter, action_priority, "
    "active_goal_id, suspended_goal_id, suspended_action, decision_due_since, critical_since, "
    "task_tool, task_target, task_title, task_category"
)
_STATE_PLACEHOLDERS = ", ".join("?" * len(_STATE_COLUMNS.split(",")))


def encode_route_path(route: Route) -> str:
    """Route corners as JSON. Python floats round-trip exactly through JSON."""
    return json.dumps([[p.x, p.y, p.distance, p.node] for p in route.path], separators=(",", ":"))


def decode_route(departed: str, arrives: str, from_activity: str, path_text: str) -> Route:
    corners = json.loads(path_text)
    if not isinstance(corners, list):
        raise ValueError("route path must be a list")
    path = tuple(
        PathPoint(x=float(x), y=float(y), distance=float(d), node=None if n is None else str(n))
        for x, y, d, n in corners
    )
    return Route(
        departed_at=_parse_ts(departed),
        arrives_at=_parse_ts(arrives),
        path=path,
        from_activity=Activity(from_activity),
    )


def _state_values(state: MapleState) -> tuple[object, ...]:
    r = state.reaction
    route = state.route
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
        state.point_id,
        _ts(route.departed_at) if route else None,
        route.from_activity.value if route else None,
        encode_route_path(route) if route else None,
        _ts(state.needs_at) if state.needs_at else None,
        state.rng.decision_counter,
        state.action_id,
        state.goal_counter,
        state.action_priority.value,
        state.goal.id if state.goal else None,
        state.suspended_goal.id if state.suspended_goal else None,
        state.suspended_action.value if state.suspended_action else None,
        _ts(state.reevaluate_since) if state.reevaluate_since else None,
        _ts(state.critical_since) if state.critical_since else None,
        state.task.tool.value if state.task else None,
        state.task.target if state.task else None,
        state.task.title if state.task else None,
        state.task.category if state.task else None,
    )


def _goal_row(goal: Goal, revision: int) -> tuple[object, ...]:
    return (
        goal.id,
        MAPLE_ID,
        revision,
        goal.type.value,
        goal.summary,
        goal.source.value,
        _ts(goal.started_at),
        _ts(goal.horizon_until),
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
                f" VALUES (?, 1, {_STATE_PLACEHOLDERS})",
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
         r_kind, r_variant, r_start, r_until,
         point_id, route_departed, route_from, route_path,
         needs_at, decisions, action_id, goal_counter, action_priority,
         goal_id, suspended_id, suspended_action, reevaluate, critical,
         task_tool, task_target, task_title, task_category) = state_row  # fmt: skip
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
            rng=RngState(
                seed_hex=seed,
                tick_counter=ticks,
                interaction_counter=interactions,
                decision_counter=decisions,
            ),
            recent_interactions=tuple(
                InteractionRecord(kind=InteractionKind(kind), at=_parse_ts(at))
                for _, kind, at in ledger
            ),
            reaction=reaction,
            point_id=point_id,
            route=(
                decode_route(route_departed, started, route_from, route_path)
                if route_path is not None
                else None
            ),
            needs_at=_parse_ts(needs_at) if needs_at else None,
            action_id=action_id,
            action_priority=Priority(action_priority),
            goal=self._goal(goal_id),
            suspended_goal=self._goal(suspended_id),
            suspended_action=Activity(suspended_action) if suspended_action else None,
            goal_counter=goal_counter,
            reevaluate_since=_parse_ts(reevaluate) if reevaluate else None,
            critical_since=_parse_ts(critical) if critical else None,
            task=(
                Task(Tool(task_tool), task_target, task_title, task_category)
                if task_tool is not None
                else None
            ),
        )
        return StoredLife(state=state, revision=revision)

    def _goal(self, goal_id: int | None) -> Goal | None:
        if goal_id is None:
            return None
        row = self._conn.execute(
            "SELECT goal_type, summary, source, started_at, horizon_until FROM goal WHERE id = ?",
            (goal_id,),
        ).fetchone()
        if row is None:
            raise CorruptStateError(f"goal {goal_id} is missing")
        goal_type, summary, source, started, horizon = row
        return Goal(
            id=goal_id,
            type=GoalType(goal_type),
            summary=summary,
            source=GoalSource(source),
            started_at=_parse_ts(started),
            horizon_until=_parse_ts(horizon),
        )

    def decisions(
        self,
        *,
        limit: int | None = None,
        revision: int | None = None,
        since_revision: int | None = None,
    ) -> list[StoredDecision]:
        """Decision audit rows, oldest first (ADR-0026 §8)."""
        return audit_rows.decisions(
            self._conn, limit=limit, revision=revision, since_revision=since_revision
        )

    def action_events(
        self,
        *,
        limit: int | None = None,
        revision: int | None = None,
        since_revision: int | None = None,
    ) -> list[StoredActionEvent]:
        """Action lifecycle rows, oldest first (ADR-0028 §2)."""
        return audit_rows.action_events(
            self._conn, limit=limit, revision=revision, since_revision=since_revision
        )

    def events_since(self, revision: int, *, limit: int) -> list[StoredEvent]:
        """Timeline rows committed after `revision`, oldest first (at most `limit`)."""
        rows = self._conn.execute(
            "SELECT id, revision, tick_id, kind, at, payload FROM timeline_event"
            " WHERE revision > ? ORDER BY id LIMIT ?",
            (revision, limit),
        ).fetchall()
        try:
            return [
                StoredEvent(id=i, revision=rev, tick_id=tick, event=decode_event(kind, at, p))
                for i, rev, tick, kind, at, p in rows
            ]
        except (ValueError, TypeError, KeyError) as exc:
            raise CorruptStateError(f"timeline event is invalid: {exc}") from exc

    def tool_uses(
        self,
        *,
        limit: int | None = None,
        revision: int | None = None,
        since_revision: int | None = None,
        operation: ToolOp | None = None,
    ) -> list[StoredToolUse]:
        """Reader/writer provenance, oldest first (ADR-0029 §5)."""
        return tool_rows.tool_uses(
            self._conn,
            limit=limit,
            revision=revision,
            since_revision=since_revision,
            operation=operation,
        )

    def documents(self, *, limit: int | None = None) -> list[StoredDocument]:
        """Maple's workspace documents, oldest first."""
        return tool_rows.documents(self._conn, limit=limit)

    def document(self, document_id: int) -> StoredDocument | None:
        return tool_rows.document(self._conn, document_id)

    def goals(self, *, limit: int | None = None) -> list[Goal]:
        """Goal definitions, oldest first (all, or only the most recent `limit`)."""
        if limit is None:
            rows = self._conn.execute("SELECT id FROM goal ORDER BY id DESC").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM goal ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        found = [self._goal(int(r[0])) for r in reversed(rows)]
        return [g for g in found if g is not None]

    def commit(
        self,
        state: MapleState,
        *,
        expected_revision: int,
        events: Sequence[LifeEvent],
        tick_id: int | None = None,
        observations: Sequence[Observation] = (),
        journal: Sequence[JournalEntry] = (),
        reflection: ReflectionState | None = None,
        actions: Sequence[ActionEvent] = (),
        decisions: Sequence[DecisionRecord] = (),
        tools: Sequence[ToolRecord] = (),
    ) -> int:
        """Atomically replace Maple's state and append events (and, for a heartbeat, the
        observations it used), action lifecycle events, and decision audit rows.
        Returns the new revision."""
        if observations and tick_id is None:
            raise ValueError("observations are recorded with the heartbeat that used them")
        new_revision = expected_revision + 1
        started = [e.goal for e in events if isinstance(e, GoalStarted)]
        with transaction(self._conn):
            # Decisions, then goals (which name the decision that started them), then
            # life_state (which references the active/suspended goal).
            decided_goal: dict[int, int] = {}
            for record in decisions:
                row_id = audit_rows.insert_decision(self._conn, new_revision, record)
                if record.executed is not None and record.executed.goal_id is not None:
                    decided_goal.setdefault(record.executed.goal_id, row_id)
            self._conn.executemany(
                "INSERT INTO goal (id, maple_id, revision, goal_type, summary, source,"
                " started_at, horizon_until, decision_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(*_goal_row(goal, new_revision), decided_goal.get(goal.id)) for goal in started],
            )
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
                f" = ({_STATE_PLACEHOLDERS})"
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
            audit_rows.insert_actions(self._conn, new_revision, actions)
            tool_rows.insert_tools(self._conn, new_revision, tools)
            if tick_id is not None and observations:
                self._insert_observations(new_revision, tick_id, observations)
            for entry in journal:
                self._insert_journal_entry(new_revision, entry)
            if reflection is not None:
                self._save_reflection(reflection)
        return new_revision

    # ------------------------------------------------------------ journal

    def _insert_journal_entry(self, revision: int, entry: JournalEntry) -> None:
        observation_ids = []
        for metric, subject in entry.observation_keys:
            row = self._conn.execute(
                "SELECT id FROM observation WHERE tick_id = ? AND metric = ? AND subject = ?",
                (entry.tick_id, metric.value, subject),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"journal entry cites an unrecorded observation {metric}:{subject}"
                )
            observation_ids.append(int(row[0]))
        cursor = self._conn.execute(
            "INSERT INTO journal_entry (maple_id, revision, tick_id, created_at, category,"
            " trigger_kind, topic, text, importance, brain_kind, brain_name, brain_version,"
            " template_id, activity, expression)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                MAPLE_ID,
                revision,
                entry.tick_id,
                _ts(entry.created_at),
                entry.category.value,
                entry.trigger.value,
                entry.topic,
                entry.text,
                entry.importance.value,
                entry.brain_kind.value,
                entry.brain_name,
                entry.brain_version,
                entry.template_id,
                entry.activity.value,
                entry.expression.value,
            ),
        )
        self._conn.executemany(
            "INSERT INTO journal_entry_observation (entry_id, observation_id, position)"
            " VALUES (?, ?, ?)",
            [(cursor.lastrowid, oid, i) for i, oid in enumerate(observation_ids)],
        )

    def read_view(self, *, recent: int) -> PersistedView:
        """State, reflection, latest observations, journal and timeline in ONE read transaction.

        With WAL, a read transaction sees a single committed snapshot of the
        database, so no part of the view can be from a later transition than
        another part.
        """
        with read_transaction(self._conn):
            life = self.load()
            reflection = self.reflection_state()
            tick = self.latest_observation_tick()
            observations = () if tick is None else tuple(self.observations(tick_id=tick))
            journal = tuple(self.journal(limit=recent))
            timeline = tuple(self.events(limit=recent))
        return PersistedView(life, reflection, observations, journal, timeline)

    def journal(
        self, *, limit: int | None = None, revision: int | None = None
    ) -> list[StoredJournalEntry]:
        """Entries oldest first: all, only the most recent `limit`, or one revision's."""
        sql = (
            "SELECT id, revision, tick_id, created_at, category, trigger_kind, topic, text,"
            " importance, brain_kind, brain_name, brain_version, template_id, activity,"
            " expression FROM journal_entry"
        )
        if revision is not None:
            rows = self._conn.execute(
                sql + " WHERE revision = ? ORDER BY id", (revision,)
            ).fetchall()
        elif limit is None:
            rows = self._conn.execute(sql + " ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(sql + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            rows.reverse()
        stored = []
        try:
            for (row_id, rev, tick, created, category, trigger, topic, text, importance,
                 kind, name, version, template, activity, expression) in rows:  # fmt: skip
                refs = self._conn.execute(
                    "SELECT o.id, o.metric, o.subject FROM journal_entry_observation j"
                    " JOIN observation o ON o.id = j.observation_id"
                    " WHERE j.entry_id = ? ORDER BY j.position",
                    (row_id,),
                ).fetchall()
                entry = JournalEntry(
                    created_at=_parse_ts(created),
                    category=JournalCategory(category),
                    trigger=TriggerKind(trigger),
                    topic=topic,
                    text=text,
                    importance=Importance(importance),
                    brain_kind=BrainKind(kind),
                    brain_name=name,
                    brain_version=version,
                    template_id=template,
                    activity=Activity(activity),
                    expression=Expression(expression),
                    observation_keys=tuple((Metric(m), sub) for _, m, sub in refs),
                    tick_id=tick,
                )
                stored.append(StoredJournalEntry(row_id, rev, entry, tuple(r[0] for r in refs)))
        except (ValueError, TypeError) as exc:
            raise CorruptStateError(f"journal entry is invalid: {exc}") from exc
        return stored

    def _save_reflection(self, rs: ReflectionState) -> None:
        self._conn.execute(
            "INSERT INTO journal_state (maple_id, journal_day, daily_seen, interactions_today,"
            " notices_today, last_interaction_entry_at, active_alerts, last_reflection_day,"
            " milestones) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (maple_id) DO UPDATE SET journal_day = excluded.journal_day,"
            " daily_seen = excluded.daily_seen, interactions_today = excluded.interactions_today,"
            " notices_today = excluded.notices_today,"
            " last_interaction_entry_at = excluded.last_interaction_entry_at,"
            " active_alerts = excluded.active_alerts,"
            " last_reflection_day = excluded.last_reflection_day,"
            " milestones = excluded.milestones",
            (
                MAPLE_ID,
                rs.journal_day.isoformat() if rs.journal_day else None,
                json.dumps(sorted(rs.daily_seen)),
                rs.interactions_today,
                rs.notices_today,
                _ts(rs.last_interaction_entry_at) if rs.last_interaction_entry_at else None,
                json.dumps([list(a) for a in rs.active_alerts]),
                rs.last_reflection_day.isoformat() if rs.last_reflection_day else None,
                json.dumps(sorted(rs.milestones)),
            ),
        )

    def reflection_state(self) -> ReflectionState:
        row = self._conn.execute(
            "SELECT journal_day, daily_seen, interactions_today, notices_today,"
            " last_interaction_entry_at, active_alerts, last_reflection_day, milestones"
            " FROM journal_state WHERE maple_id = ?",
            (MAPLE_ID,),
        ).fetchone()
        if row is None:
            return INITIAL_REFLECTION  # a life from before the journal existed
        try:
            day, seen, interactions, notices, last_entry, alerts, reflected, milestones = row
            return ReflectionState(
                journal_day=date.fromisoformat(day) if day else None,
                daily_seen=frozenset(str(x) for x in json.loads(seen)),
                interactions_today=interactions,
                notices_today=notices,
                last_interaction_entry_at=_parse_ts(last_entry) if last_entry else None,
                active_alerts=tuple((str(t), str(c)) for t, c in json.loads(alerts)),
                last_reflection_day=date.fromisoformat(reflected) if reflected else None,
                milestones=frozenset(str(x) for x in json.loads(milestones)),
            )
        except (ValueError, TypeError) as exc:
            raise CorruptStateError(f"journal state is invalid: {exc}") from exc

    def _insert_observations(
        self, revision: int, tick_id: int, observations: Sequence[Observation]
    ) -> None:
        self._conn.executemany(
            "INSERT INTO observation (maple_id, revision, tick_id, observed_at, metric,"
            " subject, status, value, state, unit, source, reason)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    MAPLE_ID,
                    revision,
                    tick_id,
                    _ts(o.observed_at),
                    o.metric.value,
                    o.subject,
                    o.status.value,
                    o.value,
                    o.state.value if o.state else None,
                    o.unit.value,
                    o.source,
                    o.reason,
                )
                for o in observations
            ],
        )

    def observations(self, *, tick_id: int | None = None) -> list[StoredObservation]:
        sql = (
            "SELECT id, revision, tick_id, observed_at, metric, subject, status, value, state,"
            " unit, source, reason FROM observation"
        )
        params: tuple[object, ...] = ()
        if tick_id is not None:
            sql += " WHERE tick_id = ?"
            params = (tick_id,)
        rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        try:
            stored = []
            for (row_id, rev, tick, at, metric, subject, status, value, state,
                 unit, source, reason) in rows:  # fmt: skip
                observation = Observation(
                    metric=Metric(metric),
                    subject=subject,
                    status=ObservationStatus(status),
                    observed_at=_parse_ts(at),
                    source=source,
                    value=value,
                    state=ServiceState(state) if state is not None else None,
                    reason=reason,
                )
                if observation.unit.value != unit:
                    raise ValueError(f"unit {unit!r} does not match metric {metric!r}")
                stored.append(StoredObservation(row_id, rev, tick, observation))
            return stored
        except (ValueError, TypeError) as exc:
            raise CorruptStateError(f"observation row is invalid: {exc}") from exc

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

    def latest_observation_tick(self) -> int | None:
        row = self._conn.execute("SELECT max(tick_id) FROM observation").fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def events(self, *, limit: int | None = None, revision: int | None = None) -> list[StoredEvent]:
        """Timeline oldest first: all, only the most recent `limit`, or one revision's."""
        sql = "SELECT id, revision, tick_id, kind, at, payload FROM timeline_event"
        if revision is not None:
            rows = self._conn.execute(
                sql + " WHERE revision = ? ORDER BY id", (revision,)
            ).fetchall()
        elif limit is None:
            rows = self._conn.execute(sql + " ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(sql + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            rows.reverse()
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
