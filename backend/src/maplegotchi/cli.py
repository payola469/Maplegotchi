"""Command-line entry point. Phase 1 provides only `simulate` (pure, fake time)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta

from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.simulation import SimulationReport, daily_owner_routine, simulate
from maplegotchi.core.state import birth

# A fixed, documented demo seed so simulation runs are comparable.
DEMO_SEED = hashlib.sha256(b"maplegotchi-demo-seed").hexdigest()
DEFAULT_START = "2026-01-01T00:00:00+00:00"


def _report_json(report: SimulationReport) -> dict[str, object]:
    s = report.final_state
    return {
        "digest": report.digest,
        "started_at": report.started_at.isoformat(),
        "ended_at": report.ended_at.isoformat(),
        "ticks": report.ticks,
        "activity_changes": report.activity_changes,
        "activity_ticks": {a.value: n for a, n in report.activity_ticks},
        "night_sleep_ratio": round(report.night_sleep_ratio, 4),
        "day_sleep_ratio": round(report.day_sleep_ratio, 4),
        "need_ranges": {
            name: [round(r.minimum, 3), round(r.maximum, 3)] for name, r in report.need_ranges
        },
        "interactions": {
            "accepted": report.interactions_accepted,
            "rejected": report.interactions_rejected,
        },
        "final_state": {
            "name": s.identity.name,
            "age": str(s.age(report.ended_at)),
            "ticks_lived": s.ticks_lived,
            "activity": s.activity.value,
            "location": s.location.value,
            "expression": s.expression_at(report.ended_at).value,
            "activity_until": s.activity_until.isoformat(),
            "needs": {
                "mood": round(s.needs.mood, 3),
                "energy": round(s.needs.energy, 3),
                "curiosity": round(s.needs.curiosity, 3),
                "social": round(s.needs.social, 3),
            },
            "rng": {
                "tick_counter": s.rng.tick_counter,
                "interaction_counter": s.rng.interaction_counter,
            },
            "recent_interactions": len(s.recent_interactions),
        },
    }


def _simulate(args: argparse.Namespace) -> int:
    start = datetime.fromisoformat(args.start)
    params = CoreParameters(heartbeat_interval=timedelta(seconds=args.interval))
    maple = birth(name="Maple", born_at=start, seed_hex=args.seed)
    plan = () if args.no_owner else daily_owner_routine(start, args.days, params)
    report = simulate(maple, days=args.days, params=params, interactions=plan)
    print(json.dumps(_report_json(report), indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maplegotchi")
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("simulate", help="simulate Maple's life in fake time (no I/O)")
    sim.add_argument("--days", type=int, default=30)
    sim.add_argument("--seed", default=DEMO_SEED, help="64 lowercase hex chars")
    sim.add_argument("--start", default=DEFAULT_START, help="ISO-8601 UTC birth time")
    sim.add_argument("--interval", type=int, default=300, help="heartbeat seconds")
    sim.add_argument("--no-owner", action="store_true", help="no Greet/Pet interactions")
    sim.set_defaults(handler=_simulate)
    args = parser.parse_args(argv)
    handler = args.handler
    result: int = handler(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
