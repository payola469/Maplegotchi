"""Actual SQLite-per-transition corpus, including independently restarted workers.

Default: all 8,640 manifest inputs for both seeds, continuous versus restarted.
--inputs N is explicitly partial evidence, never full acceptance or a golden pin.
Every operation uses unchanged owned admission, atomic writer and real processes.
"""

import argparse
import json
import os
import subprocess  # noqa: TID251 -- explicitly bounded owned corpus workers
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Any

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import admit, image_of
from tests.schema_v11.integrated_corpus import TICKS, corpus
from tests.schema_v11.restart_worker import birth_snapshot, digest, replace_rows, resources
from tests.schema_v11.test_canonical_runtime import facts, port
from tests.schema_v11.test_restart_process import worker_interpreter


def worker(
    scope: store.OwnedRoot, seed: int, begin: int, end: int, expected: str
) -> dict[str, Any]:
    definition = corpus()[seed]
    binding = port(scope)
    runtime = None
    try:
        if begin == 0 and expected == "new":
            raw = birth_snapshot()
            row = raw.rows("maple")[0]
            raw = replace_rows(raw, "maple", ((*row[:3], definition.seed_hex),))
            runtime = CanonicalPersistenceRuntime.create(
                binding, admit(raw, binding.catalogs, binding.contexts), schema_version=11
            )
        else:
            runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
            assert digest(image_of(runtime.capture())) == expected
        before_digest = digest(image_of(runtime.capture()))
        trace = []
        for index in range(begin, end):
            before = runtime.capture()
            now = definition.at[index]
            runtime.step(
                now,
                BehaviorInputs(),
                CoreParameters(),
                facts(before),
                expected_revision=before.life.record.revision,
                catalog=binding.task_catalog(before),
                task_effects=binding.task_effects,
            )
            selected = runtime.capture()
            # Fixed first-action critical input; independent of process segmentation.
            if index == 2:
                assert selected.life.travel is not None
                runtime.step(
                    now + timedelta(microseconds=100000),
                    BehaviorInputs(server_attention=1),
                    CoreParameters(),
                    facts(selected),
                    expected_revision=selected.life.record.revision,
                    task_effects=binding.task_effects,
                )
            saved = runtime.capture()
            trace.append(
                dict(
                    input=index + 1,
                    image=digest(image_of(saved)),
                    revision=saved.life.record.revision,
                    tick=saved.life.rng.tick_counter,
                    action=saved.life.record.action_counter,
                    decision=saved.life.rng.decision_counter,
                )
            )
            if (index + 1) % 30 == 0:
                print(
                    f"CORPUS_PROGRESS seed={seed} range={begin}:{end} input={index + 1}/{TICKS}",
                    flush=True,
                )
        after = runtime.capture()
        return dict(
            pid=os.getpid(), before=before_digest, after=digest(image_of(after)), trace=trace
        )
    finally:
        if runtime is not None:
            runtime.close()


def child(
    scope: store.OwnedRoot, seed: int, begin: int, end: int, expected: str, cancel: Event
) -> dict[str, Any]:
    executable, env = worker_interpreter()
    process = subprocess.Popen(  # noqa: S603 -- fixed module, bounded indices, owned capability
        [
            executable,
            "-B",
            "-m",
            "tests.schema_v11.durable_corpus",
            "--worker",
            str(scope.path),
            str(scope.identity[0]),
            str(scope.identity[1]),
            str(seed),
            str(begin),
            str(end),
            expected,
        ],
        cwd=Path(__file__).parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks: list[bytes] = []

    def drain() -> None:
        assert process.stdout is not None
        total = 0
        while True:
            line = process.stdout.readline(16 * 1024 * 1024 + 1 - total)
            if not line:
                break
            total += len(line)
            if total > 16 * 1024 * 1024:
                process.kill()
                break
            if line.startswith(b"CORPUS_PROGRESS "):
                print(line.decode().strip(), flush=True)
            else:
                chunks.append(line)
        process.stdout.close()

    thread = Thread(target=drain, daemon=True)
    thread.start()
    try:
        # Hard ownership bound; no arbitrary child scanning or retry on failure.
        deadline = monotonic() + 6 * 60 * 60
        while True:
            if cancel.is_set() or monotonic() > deadline:
                raise ValueError("owned corpus cancelled or timed out; no retry")
            try:
                code = process.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        raise
    finally:
        thread.join(timeout=10)
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if code or thread.is_alive():
        if not cancel.is_set():
            print(
                f"CORPUS_FIRST_FAILURE seed={seed} range={begin}:{end}: {output[-2000:]}",
                flush=True,
            )
        raise ValueError(f"owned corpus worker refused: {output[-2000:]}")
    result: dict[str, Any] = json.loads(output)
    assert result["pid"] == process.pid
    return result


def collect(inputs: int) -> dict[str, Any]:
    if not 3 <= inputs <= TICKS:
        raise ValueError("inputs must include first urgent case and stay within manifest")
    cancel = Event()

    def restarted_profile(
        scope: store.OwnedRoot, seed: int, inputs: int, cancel: Event
    ) -> tuple[Any, ...]:
        definition = corpus()[seed]
        trace = []
        pids = []
        previous, expected = 0, "new"
        for cut in (*[c for c in definition.restart_after if c < inputs], inputs):
            result = child(scope, seed, previous, cut, expected, cancel)
            assert result["pid"] not in pids
            pids.append(result["pid"])
            trace.extend(result["trace"])
            previous, expected = cut, result["after"]
        reader = child(scope, seed, inputs, inputs, expected, cancel)
        assert reader["pid"] not in pids and reader["before"] == reader["after"] == expected
        return trace, pids, reader, expected

    def profile(seed: int) -> dict[str, Any]:
        definition = corpus()[seed]

        continuous, restarted = store.OwnedRoot.new(), store.OwnedRoot.new()
        success = False
        try:
            with ThreadPoolExecutor(max_workers=1) as reference_pool:
                future = reference_pool.submit(child, continuous, seed, 0, inputs, "new", cancel)
                try:
                    restarted_result = restarted_profile(restarted, seed, inputs, cancel)
                except BaseException:
                    cancel.set()
                    raise
                reference = future.result()
            trace, pids, reader, _expected = restarted_result
            assert trace == reference["trace"]
            catalog, context, _ = resources()
            left, _ = store.load(continuous, "maple.db", (catalog,), ((1, context),))
            right, _ = store.load(restarted, "maple.db", (catalog,), ((1, context),))
            assert store.exact(left) == store.exact(right)
            result = dict(
                seed=definition.seed_hex,
                inputs=inputs,
                trace=trace,
                continuous_pid=reference["pid"],
                writers=pids,
                reader=reader["pid"],
                full_typed_final_image_equal=True,
                every_input_image_digest_equal=True,
                final_digest=digest(left),
            )
            success = True
            return result
        except BaseException:
            cancel.set()
            raise
        finally:
            if success:
                continuous.cleanup()
                restarted.cleanup()
            else:
                print(
                    f"Owned failed evidence retained: {continuous.path} {restarted.path}",
                    flush=True,
                )

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        profiles = list(pool.map(profile, range(2)))
    except BaseException:
        cancel.set()
        raise
    finally:
        pool.shutdown(wait=True)
    return dict(
        format="maple-durable-corpus-diagnostic-v1",
        profiles=profiles,
        full_30_day_profiles_executed=inputs == TICKS,
        # The full mandatory suite also needs High/Entry/fault/unavailable proofs.
        full_integrated_corpus_passed=False,
        golden_pin_accepted=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=7)
    parser.add_argument("--inputs", type=int, default=TICKS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        path, dev, ino, seed, begin, end, expected = args.worker
        start, stop = int(begin), int(end)
        if int(seed) not in (0, 1) or not 0 <= start <= stop <= TICKS:
            parser.error("invalid corpus indices")
        result = worker(
            store.OwnedRoot(Path(path), (int(dev), int(ino))), int(seed), start, stop, expected
        )
        print(json.dumps(result, sort_keys=True))
    else:
        if args.output is None:
            parser.error("new output path required")
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(collect(args.inputs), output, sort_keys=True)
            output.write("\n")


if __name__ == "__main__":
    main()
