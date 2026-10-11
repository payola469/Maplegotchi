"""Owned synthetic lives only: no existing database/path input and no production caller."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.goals import Goal, GoalSource, GoalType
from maplegotchi.core.room import POINT_BY_ID, Route, canonical_point, plan_route, whereabouts
from maplegotchi.core.state import InteractionKind
from maplegotchi.core.timeline import GoalStarted
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import BIRTH, open_runtime, run_ticks


@dataclass(frozen=True, slots=True)
class Scenario:
    kind: str = "fresh"
    point: str | None = None
    location: RoomLocation = RoomLocation.RUG
    activity: Activity = Activity.IDLE

    def __post_init__(self) -> None:
        if self.kind not in {
            "fresh",
            "demo",
            "aged",
            "point",
            "null",
            "walking",
            "active",
            "suspended",
        }:
            raise ValueError("unknown synthetic fixture")
        if not isinstance(self.location, RoomLocation) or not isinstance(self.activity, Activity):
            raise ValueError("invalid synthetic activity/location")
        if self.point is not None and self.point not in POINT_BY_ID:
            raise ValueError("unknown synthetic point")


@dataclass(frozen=True, slots=True)
class SyntheticLife:
    """Capability handle; constructing one does not register or grant database access."""

    token: object

    @property
    def conn(self) -> sqlite3.Connection:
        return guarded(self).conn

    @property
    def data_dir(self) -> DataDir:
        return guarded(self).data_dir


@dataclass(slots=True)
class Owned:
    handle: SyntheticLife
    root: Path
    data_dir: DataDir
    conn: sqlite3.Connection
    identity: tuple[int, int]
    closed: bool = False

    def close(self) -> None:
        """The fixture owner releases its source once, including early test release."""
        if not self.closed:
            self.conn.close()
            self.closed = True


_LIVE: dict[int, Owned] = {}


def guarded(handle: SyntheticLife) -> Owned:
    if not isinstance(handle, SyntheticLife):
        raise ValueError("explicit live synthetic handle required; paths/connections forbidden")
    owned = _LIVE.get(id(handle))
    if owned is None or owned.handle is not handle:
        raise ValueError("unregistered or expired synthetic handle")
    path = owned.root / "maple.db"
    info = path.stat()
    if (
        owned.data_dir.root != owned.root
        or path.is_symlink()
        or not path.is_file()
        or path.resolve() != path
        or info.st_nlink != 1
        or (info.st_dev, info.st_ino) != owned.identity
    ):
        raise ValueError("synthetic database ownership/path changed")
    if owned.closed:
        raise ValueError("synthetic source connection is closed")
    if owned.conn.execute("PRAGMA database_list").fetchone()[2] != str(path):
        raise ValueError("synthetic database ownership/path changed")
    return owned


DEFAULT_SCENARIO = Scenario()


@contextmanager
def synthetic_life(scenario: Scenario = DEFAULT_SCENARIO) -> Iterator[SyntheticLife]:
    if not isinstance(scenario, Scenario):
        raise ValueError("only declared synthetic scenarios accepted; no paths")
    base = Path(tempfile.gettempdir()).resolve()
    if any(base == p or base.is_relative_to(p) for p in (Path("/data"), Path("/opt"))):
        raise ValueError("unsafe temporary base")
    with tempfile.TemporaryDirectory(prefix="maple-r1a08-", dir=base) as directory:
        root = Path(directory).resolve()
        root.chmod(0o700)
        data_dir = DataDir(root)
        clock = FakeClock(BIRTH)
        runtime = open_runtime(data_dir, clock)
        try:
            if scenario.kind in {"demo", "aged"}:
                if scenario.kind == "aged":
                    runtime.interact(InteractionKind.GREET)
                run_ticks(runtime, clock, 288 if scenario.kind == "demo" else 96)
                if scenario.kind == "aged":
                    clock.advance(timedelta(days=30))
                    runtime.heartbeat_if_due()
        finally:
            runtime.close()
        path = root / "maple.db"
        path.chmod(0o600)
        info = path.stat()
        handle = SyntheticLife(object())
        conn = sqlite3.connect(path, isolation_level=None)
        owned = Owned(handle, root, data_dir, conn, (info.st_dev, info.st_ino))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            repo = LifeRepository(conn)
            source = repo.load()
            state = source.state
            if scenario.kind in {"point", "null", "walking"}:
                point = (
                    POINT_BY_ID[scenario.point]
                    if scenario.point
                    else canonical_point(scenario.activity, scenario.location)
                )
                at = state.last_updated_at
                route: Route | None = None
                if scenario.kind == "walking":
                    route = plan_route(
                        whereabouts(state.route, state.point, at), point, at, state.activity
                    )
                    if route is None:
                        raise ValueError("walking fixture requires a distinct destination")
                    at += timedelta(milliseconds=1)
                state = replace(
                    state,
                    activity=scenario.activity,
                    location=scenario.location,
                    point_id=None if scenario.kind == "null" else point.id,
                    route=route,
                    activity_started_at=route.arrives_at if route else at,
                    activity_until=(route.arrives_at if route else at) + timedelta(minutes=20),
                    task=None,
                    last_updated_at=at,
                )
                repo.commit(state, expected_revision=source.revision, events=())
            if scenario.kind in {"active", "suspended"}:
                goal = Goal(
                    1,
                    GoalType.LEARN,
                    "Synthetic continuity goal",
                    GoalSource.RULE,
                    state.last_updated_at,
                    state.last_updated_at + timedelta(hours=2),
                )
                state = replace(
                    state,
                    goal_counter=1,
                    goal=goal if scenario.kind == "active" else None,
                    suspended_goal=goal if scenario.kind == "suspended" else None,
                    suspended_action=Activity.READ if scenario.kind == "suspended" else None,
                )
                repo.commit(
                    state,
                    expected_revision=source.revision,
                    events=(GoalStarted(state.last_updated_at, goal),),
                )
            if scenario.kind != "fresh":
                at_text = state.last_updated_at.isoformat()
                conn.execute(
                    "INSERT INTO decision (maple_id,revision,at,trigger,director_kind,"
                    "director_name,director_version,context_summary,verdict) "
                    "VALUES (1,1,?,'no_plan','rule','synthetic','1','Synthetic fixture',"
                    "'fallback')",
                    (at_text,),
                )
                conn.execute(
                    "INSERT INTO action_event (maple_id,revision,action_id,kind,at,payload) "
                    "VALUES (1,1,0,'destination_selected',?,'{}')",
                    (at_text,),
                )
                # Preserve high-water marks even when they exceed current IDs.
                conn.execute("UPDATE sqlite_sequence SET seq=seq+11")
            _LIVE[id(handle)] = owned
            try:
                yield handle
            finally:
                del _LIVE[id(handle)]
        finally:
            owned.close()
