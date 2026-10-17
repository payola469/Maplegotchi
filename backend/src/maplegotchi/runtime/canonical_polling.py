"""Versioned opt-in committed reads; never wired into shipped API/SSE/startup."""

from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from maplegotchi.core.world.coordinates import Tile, tile_to_feet
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class IdentityRead(ReadModel):
    maple_id: int
    born_at: datetime


class NeedsRead(ReadModel):
    mood: float = Field(ge=0, le=100)
    energy: float = Field(ge=0, le=100)
    curiosity: float = Field(ge=0, le=100)
    social: float = Field(ge=0, le=100)


class SnapshotRead(ReadModel):
    identity: IdentityRead
    life_revision: int = Field(ge=1)
    layout_revision: int = Field(ge=1)
    committed_at: datetime
    position: tuple[int, int]
    activity: str
    phase: Literal["pending", "walking", "performing"]
    needs: NeedsRead
    action_counter: int
    tick_counter: int
    decision_counter: int
    goal: dict[str, Any] | None
    task: dict[str, Any] | None


class LegacyAvailable(ReadModel):
    status: Literal["available"] = "available"
    data: dict[str, Any]


class Unavailable(ReadModel):
    status: Literal["unavailable"] = "unavailable"
    reason: str


class CommittedRead(ReadModel):
    contract_version: Literal["maple-canonical-poll.v1"] = "maple-canonical-poll.v1"
    source: Literal["opt_in_canonical"] = "opt_in_canonical"
    status: Literal["available"] = "available"
    snapshot: SnapshotRead
    legacy: LegacyAvailable | Unavailable


class ReadUnavailable(ReadModel):
    contract_version: Literal["maple-canonical-poll.v1"] = "maple-canonical-poll.v1"
    source: Literal["opt_in_canonical"] = "opt_in_canonical"
    status: Literal["unavailable"] = "unavailable"
    reason: Literal["runtime_stopped", "read_refused"]
    snapshot: None = None
    legacy: None = None


def snapshot_read(snapshot: CanonicalSnapshot) -> SnapshotRead:
    """All fields come from one immutable committed capture, at its saved time.

    No extrapolation to a browser clock and no read-time tick or revision write.
    """
    life = snapshot.life
    row = life.record
    at = datetime.fromisoformat(row.last_updated_at)
    travel = life.travel
    return SnapshotRead(
        identity=IdentityRead(maple_id=row.maple_id, born_at=life.identity.born_at),
        life_revision=row.revision,
        layout_revision=row.layout_revision,
        committed_at=at,
        position=travel.position_at(at) if travel else tile_to_feet(Tile(row.tx, row.ty)),
        activity=life.activity.value,
        phase=cast(Literal["pending", "walking", "performing"], travel.phase_at(at))
        if travel
        else "performing",
        needs=NeedsRead(**asdict(life.needs)),
        action_counter=row.action_counter,
        tick_counter=life.rng.tick_counter,
        decision_counter=life.rng.decision_counter,
        goal=asdict(life.active_goal) if life.active_goal else None,
        task=asdict(life.task) if life.task else None,
    )
