"""Synthetic-owned diagnostic evidence, never an accepted D05 pin or live service.

Produce: python -m tests.schema_v11.life_evidence --output NEW.json --source-sha SHA
Compare: python tests/schema_v11/life_evidence.py --compare linux.json windows.json
The comparator is stdlib-only and performs no database/runtime access.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

FORMAT = "maple-life-diagnostic-v2"


def compare(left: dict[str, Any], right: dict[str, Any]) -> None:
    for value in (left, right):
        if (
            value.get("format") != FORMAT
            or value.get("diagnostic_only") is not True
            or not re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_sha", "")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(value.get("checkout_sha", "")))
            or type(value.get("portable")) is not dict
            or type(value.get("runtime")) is not dict
            or type(value.get("processes")) is not dict
        ):
            raise ValueError("invalid diagnostic evidence")
        portable = value["portable"]
        trace = portable.get("trace")
        writers = value["processes"].get("writers")
        reader = value["processes"].get("reader")
        if (
            type(trace) is not list
            or len(trace) != 12
            or portable.get("ticks") != 12
            or portable.get("continuous_runs") != 3
            or portable.get("restarted_segments") != 6
            or portable.get("exact_typed_image_equal") is not True
            or portable.get("duplicate_arrivals") != 0
            or portable.get("mid_edge_restore_verified") is not True
            or portable.get("critical_mid_edge") != "persisted_exact_entry:D01_APPROVED"
            or type(writers) is not list
            or len(writers) != 6
            or any(type(pid) is not int or pid <= 0 for pid in writers)
            or len(set(writers)) != 6
            or type(reader) is not int
            or reader <= 0
            or reader in writers
            or value["processes"].get("exit_order_verified") is not True
        ):
            raise ValueError("incomplete diagnostic proof")
        for tick, row in enumerate(trace, 1):
            if (
                type(row) is not dict
                or row.get("tick") != tick
                or row.get("revision") != tick + 1
                or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("digest", "")))
            ):
                raise ValueError("incomplete diagnostic trace")
        if (
            portable.get("final_digest") != trace[-1]["digest"]
            or portable.get("final_revision") != trace[-1]["revision"]
        ):
            raise ValueError("inconsistent final image")
    if {left.get("runtime", {}).get("platform"), right.get("runtime", {}).get("platform")} != {
        "Linux",
        "Windows",
    }:
        raise ValueError("independent Linux and Windows evidence required")
    if left["source_sha"] != right["source_sha"] or left["checkout_sha"] != right["checkout_sha"]:
        raise ValueError("different tested revisions")
    if left["portable"] != right["portable"]:
        raise ValueError("diagnostic trace/image mismatch")


def collect() -> dict[str, Any]:
    # Imports are deliberately deferred: comparison never opens SQLite or imports the app.
    from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
    from tests.schema_v11 import owned_store as store
    from tests.schema_v11.canonical_binding import image_of
    from tests.schema_v11.life_simulation import boundary_segment, simulation_initial
    from tests.schema_v11.restart_worker import digest, resources
    from tests.schema_v11.test_canonical_runtime import port
    from tests.schema_v11.test_runtime_restart import child

    reference: list[dict[str, str | int]] = []
    final: store.Snapshot | None = None
    for repetition in range(3):
        owned = store.OwnedRoot.new()
        runtime = None
        try:
            binding = port(owned)
            runtime = CanonicalPersistenceRuntime.create(
                binding, simulation_initial(binding), schema_version=11
            )
            trace = []
            for _ in range(6):
                trace.extend(boundary_segment(runtime))
            image = image_of(runtime.capture())
            if repetition == 0:
                reference, final = trace, image
            else:
                assert reference == trace and final is not None
                assert store.exact(image) == store.exact(final)
        finally:
            if runtime is not None:
                runtime.close()
            owned.cleanup()
    assert final is not None
    owned = store.OwnedRoot.new()
    pids = []
    actual_trace = []
    try:
        for chunk in range(6):
            pid, code, result = child(
                owned, "writer" if chunk == 0 else "resave", "boundary_simulation"
            )
            assert code == 0 and pid not in pids
            pids.append(pid)  # child() waits for actual interpreter exit before returning.
            actual_trace.extend(result["trace"])
            assert actual_trace == reference[: len(actual_trace)]
        reader, _, read = child(owned, "reader", "boundary_simulation")
        assert reader not in pids and read["before"] == read["after"] == digest(final)
        catalog, context, _ = resources()
        actual, life = store.load(owned, "maple.db", (catalog,), ((1, context),))
        assert store.exact(actual) == store.exact(final)
        arrivals = [
            (r[3], r[5])
            for r in actual.rows("action_event")
            if r[5] in {"arrived", "activity_started"}
        ]
        assert len(arrivals) == len(set(arrivals))
        assert actual.rows("world_event") == ()
        probe = store.OwnedRoot.new()
        try:
            urgent_writer, _, urgent = child(probe, "writer", "urgent_critical")
            urgent_reader, _, restored = child(probe, "reader", "urgent_critical")
            assert urgent_writer != urgent_reader
            assert urgent["after"] == restored["before"] == restored["after"]
        finally:
            probe.cleanup()
        return dict(
            portable=dict(
                trace=reference,
                final_digest=digest(final),
                ticks=12,
                continuous_runs=3,
                restarted_segments=6,
                exact_typed_image_equal=True,
                duplicate_arrivals=0,
                mid_edge_restore_verified=True,
                critical_mid_edge="persisted_exact_entry:D01_APPROVED",
                final_revision=life.record.revision,
            ),
            processes=dict(writers=pids, reader=reader, exit_order_verified=True),
        )
    finally:
        owned.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", nargs=2, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--checkout-sha")
    args = parser.parse_args()
    if args.compare:
        left, right = [json.loads(path.read_text(encoding="utf-8")) for path in args.compare]
        compare(left, right)
        print("Diagnostic native trace equality PASS; D05 remains OPEN (no pin update).")
        return
    checkout = args.checkout_sha or args.source_sha
    if args.output is None or any(
        not re.fullmatch(r"[0-9a-f]{40}", value or "") for value in (args.source_sha, checkout)
    ):
        parser.error("a new output path and exact source/checkout SHAs are required")
    with args.output.open("x", encoding="utf-8") as output:
        evidence = collect()
        document = dict(
            format=FORMAT,
            diagnostic_only=True,
            source_sha=args.source_sha,
            checkout_sha=checkout,
            runtime=dict(
                platform=platform.system(), python=sys.version, sqlite=sqlite3.sqlite_version
            ),
            **evidence,
        )
        json.dump(document, output, sort_keys=True, indent=2, allow_nan=False)
        output.write("\n")
    print(f"Synthetic diagnostic evidence written to {args.output}; D05 remains OPEN.")


if __name__ == "__main__":
    main()
