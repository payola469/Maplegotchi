"""Complete isolated life_state row proof; no runtime state, DB or new wire format.

Contract §§3/5-10: scalar columns retain exact supplied values/UTC text. The
40-column representation is not a JSON envelope and has no invented digest.
Travel MUST be an explicitly supplied, previously validated immutable value
or bounded synthetic fixture. Persisted route text is compared to its approved
encoding, never decoded here. Untrusted Travel admission still needs budgets.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import Goal, GoalSource, GoalType
from maplegotchi.core.identity import Identity
from maplegotchi.core.parameters import GLOBAL_INTERACTION_LIMIT, GLOBAL_INTERACTION_WINDOW
from maplegotchi.core.priority import Priority
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import InteractionKind, InteractionRecord, Needs, Reaction, ReactionKind
from maplegotchi.core.tasks import Task, Tool
from maplegotchi.core.timeline import Born
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.resolution import requirement_for
from maplegotchi.core.world.walkability import validate_safe_layout
from maplegotchi.persistence.layout_keys import (
    LayoutKeys,
    V11LayoutKeysError,
    validate_layout_keys,
)
from maplegotchi.persistence.revision_snapshot import LayoutSnapshotProof, LifeReference
from maplegotchi.persistence.travel_codec import V11TravelFormatError, encode_travel_path

Cell = int | float | str | None

LIFE_FIELDS = tuple(
    """maple_id revision mood energy curiosity social activity
activity_started_at activity_until last_tick_at last_updated_at tick_counter
interaction_counter reaction_kind reaction_variant reaction_started_at reaction_until
point_id route_departed_at route_from_activity route_path needs_at decision_counter
action_counter goal_counter action_priority active_goal_id suspended_goal_id
suspended_action decision_due_since critical_since task_tool task_target task_title
task_category layout_revision point_host tx ty route_arrives_at""".split()
)
NULLABLE_FIELDS = frozenset(
    """reaction_kind reaction_variant reaction_started_at reaction_until
route_departed_at route_from_activity route_path needs_at active_goal_id suspended_goal_id
suspended_action decision_due_since critical_since task_tool task_target task_title task_category
route_arrives_at""".split()
)
INTEGER_FIELDS = frozenset(
    """maple_id revision tick_counter interaction_counter reaction_variant
decision_counter action_counter goal_counter active_goal_id suspended_goal_id
layout_revision tx ty""".split()
)
TIME_FIELDS = frozenset(
    """activity_started_at activity_until last_tick_at last_updated_at
reaction_started_at reaction_until route_departed_at needs_at decision_due_since
critical_since route_arrives_at""".split()
)
NEED_FIELDS = ("mood", "energy", "curiosity", "social")
IdentityRow = tuple[int, str, str, str]
LedgerRow = tuple[int, int, str, str]
GoalRow = tuple[int, int, int, str, str, str, int | None, str, str]
DecisionReference = tuple[int, int, int]
ErrorCategory = Literal[
    "fields",
    "type",
    "null",
    "identity",
    "revision",
    "needs",
    "rng",
    "time",
    "reaction",
    "goal",
    "task",
    "ledger",
    "layout",
    "travel",
    "conservation",
]


class V11LifeError(ValueError):
    """Fixed category only; confidential row/payload/seed values never appear."""

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(category)


def _core[T](category: ErrorCategory, construct: Callable[[], T]) -> T:
    try:
        return construct()
    except (ValueError, TypeError, OverflowError):
        raise V11LifeError(category) from None


def _utc(value: str) -> datetime:
    if (
        type(value) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}.*\+00:00", value)
        is None
    ):
        raise V11LifeError("time")
    return _core("time", lambda: datetime.fromisoformat(value))


def _integer(value: object, minimum: int, category: ErrorCategory) -> None:
    if type(value) is not int or value < minimum:
        raise V11LifeError(category)


@dataclass(frozen=True, slots=True)
class CanonicalLifeRecord:
    """All 40 frozen SQL columns. Cross-document admission requires reconstruct_life."""

    maple_id: int
    revision: int
    mood: float
    energy: float
    curiosity: float
    social: float
    activity: str
    activity_started_at: str
    activity_until: str
    last_tick_at: str
    last_updated_at: str
    tick_counter: int
    interaction_counter: int
    reaction_kind: str | None
    reaction_variant: int | None
    reaction_started_at: str | None
    reaction_until: str | None
    point_id: str
    route_departed_at: str | None
    route_from_activity: str | None
    route_path: str | None
    needs_at: str | None
    decision_counter: int
    action_counter: int
    goal_counter: int
    action_priority: str
    active_goal_id: int | None
    suspended_goal_id: int | None
    suspended_action: str | None
    decision_due_since: str | None
    critical_since: str | None
    task_tool: str | None
    task_target: str | None
    task_title: str | None
    task_category: str | None
    layout_revision: int
    point_host: str
    tx: int
    ty: int
    route_arrives_at: str | None

    def __post_init__(self) -> None:
        for name in LIFE_FIELDS:
            value = getattr(self, name)
            if value is None:
                if name not in NULLABLE_FIELDS:
                    raise V11LifeError("null")
            elif name in INTEGER_FIELDS:
                if type(value) is not int:
                    raise V11LifeError("type")
            elif name in NEED_FIELDS:
                if type(value) not in (int, float):
                    raise V11LifeError("type")
                if not math.isfinite(value) or not 0 <= value <= 100:
                    raise V11LifeError("needs")
            elif type(value) is not str:
                raise V11LifeError("type")
            if value is not None and name in TIME_FIELDS:
                _utc(value)
        _integer(self.maple_id, 1, "identity")
        if self.maple_id != 1:
            raise V11LifeError("identity")
        for name in ("revision", "layout_revision", "active_goal_id", "suspended_goal_id"):
            value = getattr(self, name)
            if value is not None:
                _integer(value, 1, "revision")
        for name in (
            "tick_counter",
            "interaction_counter",
            "decision_counter",
            "action_counter",
            "goal_counter",
        ):
            _integer(getattr(self, name), 0, "rng")
        _integer(self.tx, 0, "layout")
        _integer(self.ty, 0, "layout")
        if (
            self.tx > 43
            or self.ty > 25
            or not 1 <= len(self.point_id) <= 128
            or not 1 <= len(self.point_host) <= 128
        ):
            raise V11LifeError("layout")
        for name, maximum in (("task_target", 60), ("task_title", 80), ("task_category", 40)):
            value = getattr(self, name)
            if value is not None and not 1 <= len(value) <= maximum:
                raise V11LifeError("task")
        for bundle, category in (
            (
                (
                    self.reaction_kind,
                    self.reaction_variant,
                    self.reaction_started_at,
                    self.reaction_until,
                ),
                "reaction",
            ),
            (
                (
                    self.route_path,
                    self.route_departed_at,
                    self.route_from_activity,
                    self.route_arrives_at,
                ),
                "travel",
            ),
            ((self.task_tool, self.task_target, self.task_title, self.task_category), "task"),
            ((self.suspended_goal_id, self.suspended_action), "goal"),
        ):
            if any(value is None for value in bundle) and not all(
                value is None for value in bundle
            ):
                raise V11LifeError(cast(ErrorCategory, category))


@dataclass(frozen=True, slots=True)
class CanonicalLife:
    """Complete pure record plus reconstructed immutable referenced domain values.

    Not MapleState, a DB view, a lifecycle transition, or a durable-load result.
    All fact rows retain their original text; derived values use existing core
    constructors. Only reconstruct_life performs the complete validation.
    """

    record: CanonicalLifeRecord
    identity_row: IdentityRow
    identity: Identity
    births: tuple[Born, ...]
    rng: RngState
    needs: Needs
    activity: Activity
    priority: Priority
    ledger_rows: tuple[LedgerRow, ...]
    recent_interactions: tuple[InteractionRecord, ...]
    goal_rows: tuple[GoalRow, ...]
    goals: tuple[Goal, ...]
    active_goal: Goal | None
    suspended_goal: Goal | None
    suspended_action: Activity | None
    reaction: Reaction | None
    task: Task | None
    travel: Travel | None
    decisions: tuple[DecisionReference, ...]
    layout: LayoutSnapshotProof


def life_fields(record: CanonicalLifeRecord) -> tuple[tuple[str, Cell], ...]:
    """Lossless SQL-column values only; no aggregate JSON, new format or digest."""
    if type(record) is not CanonicalLifeRecord:
        raise V11LifeError("type")
    return tuple((name, getattr(record, name)) for name in LIFE_FIELDS)


def _record(values: tuple[tuple[str, object], ...]) -> CanonicalLifeRecord:
    if type(values) is not tuple or any(
        type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str for pair in values
    ):
        raise V11LifeError("fields")
    data = dict(values)
    if len(data) != len(values) or set(data) != set(LIFE_FIELDS):
        raise V11LifeError("fields")
    return CanonicalLifeRecord(**data)  # type: ignore[arg-type]


def _identity(row: IdentityRow, record: CanonicalLifeRecord) -> tuple[Identity, RngState]:
    if (
        type(row) is not tuple
        or len(row) != 4
        or type(row[0]) is not int
        or row[0] != record.maple_id
        or any(type(cell) is not str for cell in row[1:])
    ):
        raise V11LifeError("identity")
    if re.fullmatch(r"[0-9a-f]{64}", row[3]) is None:
        raise V11LifeError("rng")
    identity = _core("identity", lambda: Identity(row[1], _utc(row[2])))
    rng = _core(
        "rng",
        lambda: RngState(
            row[3], record.tick_counter, record.interaction_counter, record.decision_counter
        ),
    )
    return identity, rng


def _ledger(
    rows: tuple[LedgerRow, ...], record: CanonicalLifeRecord, born: datetime
) -> tuple[InteractionRecord, ...]:
    if type(rows) is not tuple or len(rows) > GLOBAL_INTERACTION_LIMIT:
        raise V11LifeError("ledger")
    updated = _utc(record.last_updated_at)
    result: list[InteractionRecord] = []
    for position, row in enumerate(rows):
        if (
            type(row) is not tuple
            or len(row) != 4
            or type(row[0]) is not int
            or row[0] != record.maple_id
            or type(row[1]) is not int
            or row[1] != position
            or any(type(value) is not str for value in row[2:])
        ):
            raise V11LifeError("ledger")
        at = _utc(row[3])
        if (
            not born <= at <= updated
            or updated - at >= GLOBAL_INTERACTION_WINDOW
            or (result and result[-1].at > at)
        ):
            raise V11LifeError("ledger")
        result.append(_interaction(row, at))
    return tuple(result)


def _interaction(row: LedgerRow, at: datetime) -> InteractionRecord:
    return _core("ledger", lambda: InteractionRecord(InteractionKind(row[2]), at))


def _goal(row: GoalRow) -> Goal:
    return _core(
        "goal",
        lambda: Goal(
            row[0], GoalType(row[3]), row[4], GoalSource(row[5]), _utc(row[7]), _utc(row[8])
        ),
    )


def _goals(
    rows: tuple[GoalRow, ...],
    decisions: tuple[DecisionReference, ...],
    record: CanonicalLifeRecord,
    born: datetime,
) -> tuple[Goal, ...]:
    if type(rows) is not tuple or type(decisions) is not tuple:
        raise V11LifeError("goal")
    decision_ids = set()
    for decision in decisions:
        if (
            type(decision) is not tuple
            or len(decision) != 3
            or any(type(value) is not int for value in decision)
            or decision[0] < 1
            or decision[1] != record.maple_id
            or not 1 <= decision[2] <= record.revision
            or decision[0] in decision_ids
        ):
            raise V11LifeError("goal")
        decision_ids.add(decision[0])
    result: list[Goal] = []
    ids: set[int] = set()
    for row in rows:
        if (
            type(row) is not tuple
            or len(row) != 9
            or any(type(row[index]) is not int for index in (0, 1, 2))
            or any(type(row[index]) is not str for index in (3, 4, 5, 7, 8))
        ):
            raise V11LifeError("goal")
        if (
            row[0] in ids
            or not 1 <= row[0] <= record.goal_counter
            or row[1] != record.maple_id
            or not 1 <= row[2] <= record.revision
        ):
            raise V11LifeError("goal")
        if row[6] is not None and (type(row[6]) is not int or row[6] not in decision_ids):
            raise V11LifeError("goal")
        goal = _goal(row)
        if not born <= goal.started_at <= _utc(record.last_updated_at):
            raise V11LifeError("goal")
        ids.add(goal.id)
        result.append(goal)
    referenced = {id for id in (record.active_goal_id, record.suspended_goal_id) if id is not None}
    if not referenced <= ids or (
        record.active_goal_id is not None and record.active_goal_id == record.suspended_goal_id
    ):
        raise V11LifeError("goal")
    return tuple(sorted(result, key=lambda goal: goal.id))


def reconstruct_life(
    values: tuple[tuple[str, object], ...],
    *,
    identity_row: IdentityRow,
    births: tuple[Born, ...],
    ledger_rows: tuple[LedgerRow, ...],
    goal_rows: tuple[GoalRow, ...],
    decisions: tuple[DecisionReference, ...],
    layout: LayoutSnapshotProof,
    keys: LayoutKeys,
    travel: Travel | None,
) -> CanonicalLife:
    """Reconstruct all fields from bounded synthetic rows and validated context.

    No missing scalar is defaulted. No real time, RNG draw, birth, repair, Travel
    parsing, Legacy projection or database operation occurs. Context objects
    must originate from their existing pure validation boundaries.
    """
    record = _record(values)
    identity, rng = _identity(identity_row, record)
    if type(births) is not tuple or len(births) != 1 or type(births[0]) is not Born:
        raise V11LifeError("identity")
    _core("identity", lambda: require_utc(births[0].at))
    if (
        type(births[0].name) is not str
        or births[0].name != identity.name
        or births[0].at != identity.born_at
    ):
        raise V11LifeError("identity")
    needs = _core(
        "needs", lambda: Needs(record.mood, record.energy, record.curiosity, record.social)
    )
    activity = _core("type", lambda: Activity(record.activity))
    priority = _core("type", lambda: Priority(record.action_priority))
    started, until = _utc(record.activity_started_at), _utc(record.activity_until)
    tick, updated = _utc(record.last_tick_at), _utc(record.last_updated_at)
    born = identity.born_at
    if not born <= started <= until or not born <= tick <= updated:
        raise V11LifeError("time")
    if record.needs_at is not None and not tick <= _utc(record.needs_at) <= updated:
        raise V11LifeError("time")
    for text in (record.decision_due_since, record.critical_since):
        if text is not None and not born <= _utc(text) <= updated:
            raise V11LifeError("time")
    if (
        type(layout) is not LayoutSnapshotProof
        or record.layout_revision != layout.active_revision
        or layout.life_reference
        != LifeReference(
            record.maple_id, record.layout_revision, record.point_host, record.point_id
        )
    ):
        raise V11LifeError("layout")
    try:
        validate_layout_keys(layout.active.layout, record.layout_revision, keys)
    except V11LayoutKeysError:
        raise V11LifeError("layout") from None
    world, catalog = layout.active.layout.world, layout.active.layout.catalog
    mask = _core("layout", lambda: validate_safe_layout(world, catalog))
    matches = tuple(
        point
        for point in catalog.points
        if (point.instance_id, point.template.id) == (record.point_host, record.point_id)
    )
    if len(matches) != 1:
        raise V11LifeError("layout")
    point = matches[0]
    host = next(instance for instance in catalog.instances if instance.id == point.instance_id)
    room = next(region for region in world.regions if region.id == host.room_id)
    requirement = requirement_for(activity)
    if requirement.room_tier(room.kind) is None or not any(
        all(cap in point.template.provides for cap in group) for group in requirement.alternatives
    ):
        raise V11LifeError("layout")
    tile = Tile(record.tx, record.ty)
    destination = Tile(point.template.approach.x, point.template.approach.y)
    if tile not in mask.walkable:
        raise V11LifeError("layout")
    if record.route_path is None:
        if travel is not None or tile != destination or started > updated:
            raise V11LifeError("travel")
    else:
        if type(travel) is not Travel:
            raise V11LifeError("travel")
        try:
            encoded = encode_travel_path(travel, walkability=mask)
        except V11TravelFormatError:
            raise V11LifeError("travel") from None
        if (
            record.route_path != encoded
            or _utc(cast(str, record.route_departed_at)) != travel.departed_at
            or _utc(cast(str, record.route_arrives_at)) != travel.arrives_at
            or started != travel.arrives_at
            or travel.route.origin != tile
            or travel.route.destination != destination
        ):
            raise V11LifeError("travel")
        _core("travel", lambda: Activity(cast(str, record.route_from_activity)))
        if travel.departed_at < born or (
            travel.departed_at > updated
            and not (
                travel.route.total_steps == 0
                and travel.entry is None
                and travel.departed_at == travel.arrives_at
            )
        ):
            raise V11LifeError("time")
    ledger = _ledger(ledger_rows, record, born)
    goals = _goals(goal_rows, decisions, record, born)
    active = next((goal for goal in goals if goal.id == record.active_goal_id), None)
    suspended = next((goal for goal in goals if goal.id == record.suspended_goal_id), None)
    suspended_action = (
        None
        if record.suspended_action is None
        else _core("goal", lambda: Activity(cast(str, record.suspended_action)))
    )
    reaction = None
    if record.reaction_kind is not None:
        reaction = _core(
            "reaction",
            lambda: Reaction(
                ReactionKind(cast(str, record.reaction_kind)),
                cast(int, record.reaction_variant),
                _utc(cast(str, record.reaction_started_at)),
                _utc(cast(str, record.reaction_until)),
            ),
        )
        if not born <= reaction.started_at <= updated:
            raise V11LifeError("reaction")
    task = None
    if record.task_tool is not None:
        task = _core(
            "task",
            lambda: Task(
                Tool(cast(str, record.task_tool)),
                cast(str, record.task_target),
                cast(str, record.task_title),
                cast(str, record.task_category),
            ),
        )
        if not task.fits(activity):
            raise V11LifeError("task")
    return CanonicalLife(
        record,
        identity_row,
        identity,
        births,
        rng,
        needs,
        activity,
        priority,
        ledger_rows,
        ledger,
        tuple(sorted(goal_rows, key=lambda row: row[0])),
        goals,
        active,
        suspended,
        suspended_action,
        reaction,
        task,
        travel,
        tuple(sorted(decisions)),
        layout,
    )
