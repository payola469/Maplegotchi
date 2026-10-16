"""Reproducible full-corpus input manifest, not execution evidence or a digest pin.

The 30-day ordinary schedules are fixed fake-time inputs. Mandatory mid-edge
urgency cases are listed explicitly; they cannot be skipped to claim acceptance.
Their executor remains gated on the unresolved integer-score/Entry ordering
clarification. Existing original/R17 fixtures and pins are never changed here.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

START = datetime(2026, 10, 14, 12, tzinfo=UTC)
DAYS = 30
TICK = timedelta(seconds=300)
TICKS = DAYS * 24 * 12
VERSION = "maple-integrated-corpus-candidate-v1"
REQUIRED_CASES = (
    "ordinary_30_days",
    "critical_mid_edge",
    "high_mid_edge",
    "pending_and_entry_restart",
    "late_arrival_no_ghost",
    "goal_task_suspend_resume_expire",
    "read_unavailable_reconnect",
    "before_commit_failure",
    "commit_uncertainty_restore",
)


@dataclass(frozen=True)
class Corpus:
    seed_hex: str
    at: tuple[datetime, ...]
    # Counts of fully committed transitions. Writer exit precedes reader start.
    restart_after: tuple[int, ...]
    required_cases: tuple[str, ...] = REQUIRED_CASES
    status: Literal["candidate_not_acceptance_evidence"] = "candidate_not_acceptance_evidence"


def corpus() -> tuple[Corpus, ...]:
    """Reuse seeds already exercised by the canonical read/write goal scenarios.

    All ordinary inputs have server_attention=0. The mandatory urgency scenarios
    must add existing signals at exact movement boundaries with approved ordering;
    a future executor must report an incomplete corpus if any case is blocked.
    Restart cuts cover pre-action, post-selection, one day, one week and later life.
    """
    times = tuple(START + TICK * i for i in range(1, TICKS + 1))
    return tuple(Corpus(f"{seed:064x}", times, (1, 3, 288, 2016, 4320, 8352)) for seed in (0, 5))
