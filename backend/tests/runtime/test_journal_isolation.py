"""R-01: controlled synchronization, fake time, temporary databases only."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from maplegotchi.core.journal import (
    BrainContext,
    BrainKind,
    Importance,
    JournalDraft,
    Trigger,
    TriggerKind,
)
from maplegotchi.core.proposal import DirectorLabel
from maplegotchi.core.reflection import ReflectionState
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.journal_composition import JournalComposer
from maplegotchi.runtime.life import LifeRuntime, PendingDecision, RuntimeClosedError
from maplegotchi.runtime.service import MapleService, fake_senses
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import PARAMS, TICK, new_life
from tests.runtime.test_external_brain import make_context
from tests.runtime.test_movement_runtime import walk_starts


class BlockingBrain:
    kind = BrainKind.EXTERNAL
    name = "test"
    version = "1"

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.contexts: list[BrainContext] = []
        self.daemon = False

    def compose_journal(self, context: BrainContext) -> Sequence[JournalDraft]:
        self.daemon = threading.current_thread().daemon
        self.contexts.append(context)
        self.entered.set()
        if not self.release.wait(10):
            raise RuntimeError("test did not release worker")
        return tuple(
            JournalDraft(i, "I felt calm.", Importance.NORMAL, "test")
            for i in range(len(context.triggers))
        )


class Call:
    def __init__(self, operation: Callable[[], object]) -> None:
        self.result: object = None
        self.error: BaseException | None = None
        self.done = threading.Event()

        def run() -> None:
            try:
                self.result = operation()
            except BaseException as exc:
                self.error = exc
            finally:
                self.done.set()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def finish(self) -> object:
        assert self.done.wait(10), "caller did not finish"
        self.thread.join()
        if self.error is not None:
            raise self.error
        return self.result


def external(runtime: LifeRuntime) -> BlockingBrain:
    brain = BlockingBrain()
    runtime._brain = brain
    runtime._composer = JournalComposer(brain)
    return brain


def cleanup(runtime: LifeRuntime, brain: BlockingBrain, call: Call) -> None:
    brain.release.set()
    assert call.done.wait(10)
    runtime.close()


@pytest.mark.parametrize("path", ["heartbeat", "interaction", "arrival", "decision", "proposal"])
def test_every_journal_path_composes_without_writer_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    _, clock, runtime = new_life(tmp_path)
    if path == "arrival":
        walk_starts(runtime, clock)
        route = runtime.state.route
        assert route is not None
        clock.set(route.arrives_at)
    else:
        clock.advance(timedelta(minutes=16))

    # Guarantee a wording opportunity even when a particular seeded decision
    # does not begin a notable daily activity. Persistence remains real.
    def triggers(
        rs: ReflectionState, **kwargs: object
    ) -> tuple[tuple[Trigger, ...], ReflectionState]:
        return (Trigger(TriggerKind.MILESTONE, "milestone:first_heartbeat", "first_heartbeat"),), rs

    monkeypatch.setattr("maplegotchi.runtime.life.settle_triggers", triggers)
    pending = runtime.pending_decision() if path == "proposal" else None
    brain = external(runtime)
    operations: dict[str, Callable[[], object]] = {
        "heartbeat": runtime.heartbeat_committed,
        "interaction": lambda: runtime.interact_committed(InteractionKind.GREET),
        "arrival": runtime.settle_committed,
        "decision": runtime.decide_committed,
        "proposal": lambda: runtime.decide_proposal_committed(
            cast(PendingDecision, pending),
            director=DirectorLabel("external", "test", "1"),
            failure=None,
        ),
    }
    before = runtime.revision
    call = Call(operations[path])
    try:
        assert brain.entered.wait(10)
        assert runtime._lock.acquire(blocking=False)
        runtime._lock.release()
        assert runtime.revision == before
        brain.release.set()
        assert call.finish() is not None
        assert runtime.revision == before + 1 and runtime.journal()
        assert brain.daemon
    finally:
        cleanup(runtime, brain, call)


def test_busy_transition_overtakes_and_stale_interaction_is_not_duplicated(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    brain = external(runtime)
    before = runtime.revision
    call = Call(lambda: runtime.interact_committed(InteractionKind.GREET))
    try:
        assert brain.entered.wait(10)
        second = runtime.interact_committed(InteractionKind.GREET)
        assert second.revision == before + 1 and not second.journal
        brain.release.set()
        first = call.finish()
        assert first is not None
        assert runtime.revision == before + 1
        assert len(runtime.state.recent_interactions) == 1
        assert runtime.journal() == [] and len(brain.contexts) == 1
        assert runtime.reflection_state.last_interaction_entry_at is None
    finally:
        cleanup(runtime, brain, call)


def test_concurrent_heartbeat_preserves_both_updates_and_retry_markers(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    clock.advance(TICK)
    brain = external(runtime)
    before = runtime.revision
    call = Call(lambda: runtime.interact_committed(InteractionKind.GREET))
    try:
        assert brain.entered.wait(10)
        assert runtime.heartbeat_committed() is not None
        brain.release.set()
        call.finish()
        assert runtime.revision == before + 2
        assert runtime.state.ticks_lived == 1
        assert len(runtime.state.recent_interactions) == 1
        assert runtime.journal() == []
        assert "first_heartbeat" not in runtime.reflection_state.milestones
        # An ordinary later opportunity still writes the unmarked milestone.
        clock.advance(TICK)
        runtime.heartbeat_committed()
        assert "first_heartbeat" in runtime.reflection_state.milestones
    finally:
        cleanup(runtime, brain, call)


def test_timeout_retains_slot_until_worker_cleanup_and_late_result_is_dropped() -> None:
    brain = BlockingBrain()
    now = [0.0]
    composer = JournalComposer(brain, monotonic=lambda: now[0])
    call = Call(lambda: composer.compose(make_context()))
    try:
        assert brain.entered.wait(10)
        with composer._condition:
            now[0] = 30
            composer._condition.notify_all()
        assert call.finish() == ()
        assert composer._attempt is not None
        assert composer.compose(make_context()) == ()
        assert len(brain.contexts) == 1
        brain.release.set()
        with composer._condition:
            assert composer._condition.wait_for(lambda: composer._attempt is None, timeout=10)
        assert composer.compose(make_context())
        assert len(brain.contexts) == 2
    finally:
        composer.stop()
        brain.release.set()


def test_shutdown_wakes_caller_aborts_uncommitted_work_and_does_not_join_worker(
    tmp_path: Path,
) -> None:
    _, _, runtime = new_life(tmp_path)
    brain = external(runtime)
    before = runtime.revision
    call = Call(lambda: runtime.interact_committed(InteractionKind.GREET))
    try:
        assert brain.entered.wait(10)
        runtime.close()
        with pytest.raises(RuntimeClosedError):
            call.finish()
        assert runtime.revision == before and runtime._repo is None
        assert not brain.release.is_set()  # close did not wait for blocked worker
        brain.release.set()
        with runtime._composer._condition:
            assert runtime._composer._condition.wait_for(
                lambda: runtime._composer._attempt is None, timeout=10
            )
        assert runtime.revision == before
    finally:
        cleanup(runtime, brain, call)


def test_close_drains_postcommit_service_caller_before_storage_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, clock, runtime = new_life(tmp_path)
    service = MapleService(runtime, fake_senses(), clock, PARAMS)
    published, release = threading.Event(), threading.Event()
    original = service._publish

    def publish(kind: str, data: dict[str, object]) -> None:
        if kind == "interaction":
            published.set()
            assert release.wait(10)
        original(kind, data)

    monkeypatch.setattr(service, "_publish", publish)
    call = Call(lambda: service.interact(InteractionKind.GREET))
    closer: Call | None = None
    try:
        assert published.wait(10)
        service.begin_shutdown()
        closer = Call(service.close)
        assert runtime._repo is not None and not closer.done.is_set()
        with pytest.raises(RuntimeClosedError):
            service.snapshot()
        release.set()
        call.finish()
        closer.finish()
        assert runtime._repo is None
    finally:
        release.set()
        call.done.wait(10)
        if closer is not None:
            closer.finish()
        service.close()


@pytest.mark.parametrize("failure", ["journal", "commit"])
def test_external_journal_commit_failure_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _, clock, runtime = new_life(tmp_path)
    brain = external(runtime)
    brain.release.set()
    before = runtime.state, runtime.revision, runtime.reflection_state

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("injected storage failure")

    if failure == "journal":
        monkeypatch.setattr(LifeRepository, "_insert_journal_entry", explode)
    else:
        repo = runtime._repo
        assert repo is not None
        original = repo._conn

        class FailCommit:
            fail = True

            def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
                if sql == "COMMIT" and self.fail:
                    self.fail = False
                    raise OSError("injected COMMIT failure")
                return original.execute(sql, parameters)

            def __getattr__(self, name: str) -> object:
                return cast(object, getattr(original, name))

        repo._conn = cast(sqlite3.Connection, FailCommit())
    clock.advance(TICK)
    try:
        with pytest.raises(OSError):
            runtime.heartbeat_committed()
        assert (runtime.state, runtime.revision, runtime.reflection_state) == before
        assert runtime.journal() == [] and runtime.latest_observations() == []
        assert runtime.read_view(recent=10).life.revision == before[1]
    finally:
        runtime.close()


@pytest.mark.parametrize("path", ["heartbeat", "arrival", "decision"])
def test_overtaken_operation_does_not_repeat_completed_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    _, clock, runtime = new_life(tmp_path)
    if path == "arrival":
        walk_starts(runtime, clock)
        route = runtime.state.route
        assert route is not None
        clock.set(route.arrives_at)
    else:
        clock.advance(timedelta(minutes=16))

    def triggers(
        rs: ReflectionState, **kwargs: object
    ) -> tuple[tuple[Trigger, ...], ReflectionState]:
        return (Trigger(TriggerKind.MILESTONE, "milestone:first_heartbeat", "first_heartbeat"),), rs

    monkeypatch.setattr("maplegotchi.runtime.life.settle_triggers", triggers)
    brain = external(runtime)
    operations: dict[str, Callable[[], object]] = {
        "heartbeat": runtime.heartbeat_committed,
        "arrival": runtime.settle_committed,
        "decision": runtime.decide_committed,
    }
    operation = operations[path]
    revision = runtime.revision
    existing_journal = runtime.journal()
    call = Call(operation)
    try:
        assert brain.entered.wait(10)
        assert operation() is not None
        brain.release.set()
        assert call.finish() is None
        assert runtime.revision == revision + 1
        assert runtime.journal() == existing_journal and len(brain.contexts) == 1
    finally:
        cleanup(runtime, brain, call)


def test_draft_order_validation_and_markers_stay_with_the_atomic_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, clock, runtime = new_life(tmp_path)
    brain = external(runtime)
    contexts: list[BrainContext] = []

    def compose(context: BrainContext) -> Sequence[JournalDraft]:
        contexts.append(context)
        # Reverse order, plus invalid and duplicate indices. Core remains final authority.
        return (
            *(
                JournalDraft(i, "I felt calm.", Importance.NORMAL, "test")
                for i in reversed(range(len(context.triggers)))
            ),
            JournalDraft(0, "duplicate", Importance.NORMAL, "test"),
            JournalDraft(1000, "invalid index", Importance.NORMAL, "test"),
            JournalDraft(0, "invalid\ntext", Importance.NORMAL, "test"),
        )

    monkeypatch.setattr(brain, "compose_journal", compose)
    clock.advance(TICK)
    committed = runtime.heartbeat_committed(fake_senses().observe(clock.now()))
    try:
        assert committed is not None
        assert [(e.trigger, e.topic) for e in committed.journal] == [
            (t.kind, t.topic) for t in contexts[0].triggers
        ]
        assert "first_heartbeat" in runtime.reflection_state.milestones
        assert all(e.revision == committed.revision for e in runtime.journal())
        assert runtime.latest_observations()
    finally:
        runtime.close()


@pytest.mark.parametrize("phase", ["construct", "start"])
def test_startup_failure_releases_request_slot(monkeypatch: pytest.MonkeyPatch, phase: str) -> None:
    brain = BlockingBrain()
    composer = JournalComposer(brain)

    def fail(self: threading.Thread) -> None:
        raise RuntimeError("thread start failed")

    if phase == "start":
        monkeypatch.setattr(threading.Thread, "start", fail)
    else:

        def construct(**kwargs: object) -> threading.Thread:
            raise RuntimeError("thread construction failed")

        monkeypatch.setattr(threading, "Thread", construct)
    assert composer.compose(make_context()) == () and composer._attempt is None
    assert not brain.contexts


def test_slot_is_retained_through_transport_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = BlockingBrain()
    cleanup_entered, cleanup_release = threading.Event(), threading.Event()
    now = [0.0]

    def compose(context: BrainContext) -> Sequence[JournalDraft]:
        try:
            return ()
        finally:
            cleanup_entered.set()
            assert cleanup_release.wait(10)

    monkeypatch.setattr(brain, "compose_journal", compose)
    composer = JournalComposer(brain, monotonic=lambda: now[0])
    call = Call(lambda: composer.compose(make_context()))
    try:
        assert cleanup_entered.wait(10)
        with composer._condition:
            now[0] = 30
            composer._condition.notify_all()
        assert call.finish() == ()
        assert composer._attempt is not None and composer.compose(make_context()) == ()
        composer.stop()
        assert not cleanup_release.is_set()
    finally:
        cleanup_release.set()
        with composer._condition:
            assert composer._condition.wait_for(lambda: composer._attempt is None, timeout=10)


def test_shutdown_allows_an_already_executing_transaction_to_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, clock, runtime = new_life(tmp_path)
    entered, release, admission_closed = threading.Event(), threading.Event(), threading.Event()
    original = LifeRepository._save_reflection
    original_stop = runtime._calls.stop

    def save(repo: LifeRepository, reflection: ReflectionState) -> None:
        entered.set()
        assert release.wait(10)
        original(repo, reflection)

    def stop() -> None:
        original_stop()
        admission_closed.set()

    monkeypatch.setattr(LifeRepository, "_save_reflection", save)
    monkeypatch.setattr(runtime._calls, "stop", stop)
    clock.advance(TICK)
    revision = runtime.revision
    caller = Call(runtime.heartbeat_committed)
    closer: Call | None = None
    try:
        assert entered.wait(10)
        closer = Call(runtime.close)
        assert admission_closed.wait(10)
        assert runtime._repo is not None and not closer.done.is_set()
        release.set()
        assert caller.finish() is not None
        closer.finish()
        assert runtime.revision == revision + 1 and runtime._repo is None
    finally:
        release.set()
        caller.done.wait(10)
        if closer is not None:
            closer.finish()
        runtime.close()


def test_external_failure_commits_life_without_advancing_wording_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, clock, runtime = new_life(tmp_path)
    brain = external(runtime)

    def broken(context: BrainContext) -> Sequence[JournalDraft]:
        raise ValueError("malformed response")

    monkeypatch.setattr(brain, "compose_journal", broken)
    clock.advance(TICK)
    try:
        assert runtime.heartbeat_committed() is not None
        assert runtime.state.ticks_lived == 1 and runtime.journal() == []
        assert "first_heartbeat" not in runtime.reflection_state.milestones
    finally:
        runtime.close()
