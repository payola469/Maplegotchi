"""30-day canonical semantic evidence; explicitly NOT per-tick SQLite evidence.

Uses the real pure life engine, approved manifest seeds/clock and complete frame,
action and goal-event traces. Durable process/COMMIT proofs remain separate.
No golden pin, storage substitute, admission bypass or fake restart claim.
"""

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import Needs
from maplegotchi.core.world.canonical_lifecycle import step
from maplegotchi.core.world.resolution import ResolutionSnapshot
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.schema_v11.integrated_corpus import corpus
from tests.world.test_canonical_lifecycle import initial


def wire(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: wire(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [wire(v) for v in value]
    return value


def collect() -> dict[str, Any]:
    layout = load_initial_house()
    world = ResolutionSnapshot(layout, load_initial_catalog(layout))
    results = []
    for definition in corpus():
        reference = None
        for repetition in range(2):
            frame = replace(
                initial(), needs=Needs(60, 80, 60, 50), rng=RngState(definition.seed_hex)
            )
            history = sha256()
            actions = 0
            goals = 0
            activities: set[str] = set()
            cancelled: set[int] = set()
            arrivals: set[int] = set()
            started: set[int] = set()
            trace = []
            inserted = False
            for now in definition.at:
                transition = step(frame, world, now, BehaviorInputs(), CoreParameters())
                outcomes = [transition] if transition is not None else []
                if not inserted and transition is not None and transition.frame.travel is not None:
                    urgent_at = now + timedelta(microseconds=100000)
                    urgent = step(
                        transition.frame,
                        world,
                        urgent_at,
                        BehaviorInputs(server_attention=1),
                        CoreParameters(),
                    )
                    assert urgent is not None and urgent.frame.travel is not None
                    assert urgent.frame.travel.current_at(urgent_at) == (
                        transition.frame.travel.current_at(urgent_at)
                    )
                    outcomes.append(urgent)
                    inserted = True
                for outcome in outcomes:
                    frame = outcome.frame
                    activities.add(frame.activity.value)
                    for event in outcome.actions:
                        if event.kind.value == "walking_cancelled":
                            cancelled.add(event.action_id)
                        if event.kind.value == "arrived":
                            assert event.action_id not in cancelled | arrivals
                            arrivals.add(event.action_id)
                        if event.kind.value == "activity_started":
                            assert event.action_id not in cancelled | started
                            started.add(event.action_id)
                    actions += len(outcome.actions)
                    goals += len(outcome.events)
                    encoded = json.dumps(wire(outcome), sort_keys=True, separators=(",", ":"))
                    history.update(encoded.encode())
                trace.append(history.hexdigest())  # Every full frame/event prefix compared.
            assert inserted and len(trace) == 8640
            evidence = dict(
                seed=definition.seed_hex,
                days=30,
                ordinary_inputs=len(trace),
                tick_counter=frame.rng.tick_counter,
                urgent_ticks=1,
                final_frame=wire(frame),
                trace=trace,
                action_events=actions,
                life_events=goals,
                activities=sorted(activities),
                duplicate_arrivals=0,
                ghost_arrivals=0,
            )
            if repetition == 0:
                reference = evidence
            else:
                assert reference == evidence
        results.append(reference)
    return dict(
        format="maple-30-day-semantic-diagnostic-v1",
        profiles=results,
        repeated_full_frame_and_history_equal=True,
        durable_30_day_per_tick_images_verified=False,
        full_integrated_corpus_passed=False,
        limitation="Pure semantics only; not full SQLite committed-image/restart equivalence",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.source_sha):
        parser.error("exact source SHA required")
    with args.output.open("x", encoding="utf-8") as output:
        evidence = collect()
        evidence["source_sha"] = args.source_sha
        json.dump(evidence, output, sort_keys=True, allow_nan=False)
        output.write("\n")
    print("30-day pure semantic diagnostics PASS; full durable corpus NOT VERIFIED; no pin update.")


if __name__ == "__main__":
    main()
