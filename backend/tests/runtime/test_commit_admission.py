"""Shutdown/commit arbitration with real temporary storage and event barriers."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from maplegotchi.core.audit import Verdict
from maplegotchi.core.conversation import Channel, IncomingMessage, ReplyContext, Speaker
from maplegotchi.core.journal import Trigger, TriggerKind, accept_drafts
from maplegotchi.core.proposal import DirectorLabel
from maplegotchi.core.reflection import ReflectionState, interaction_triggers
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.life import LifeRuntime, RuntimeClosedError
from maplegotchi.runtime.service import MapleService, fake_senses
from tests.persistence_support import PARAMS, TICK, new_life, open_runtime
from tests.runtime.test_director_runtime import GOOD, FakeDirector
from tests.runtime.test_journal_isolation import Call, external


def storage_open(runtime: LifeRuntime) -> bool:
    """Read storage ownership after a cross-thread barrier, without stale narrowing."""
    return runtime._repo is not None


@pytest.mark.parametrize("path", ["rule", "external", "receive", "reply", "stale_audit"])
def test_shutdown_wins_before_commit_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    data, clock, runtime = new_life(tmp_path)
    message = IncomingMessage("probe", Channel.DISCORD, Speaker.PAOLO, "Hello", clock.now())
    pending = None
    received = None
    if path == "reply":
        received = runtime.receive_message_committed(message)
    if path == "stale_audit":
        clock.advance(TICK * 4)
        pending = runtime.pending_decision()
        assert pending is not None
        runtime.decide_committed()
    before = runtime.state, runtime.revision, runtime.reflection_state
    journal, timeline, messages = runtime.journal(), runtime.timeline(), runtime.messages(limit=10)
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
    original_stop = runtime._calls.stop

    def stop() -> None:
        original_stop()
        stopped.set()

    def pause() -> None:
        entered.set()
        assert release.wait(10)

    monkeypatch.setattr(runtime._calls, "stop", stop)
    if path == "rule":
        from maplegotchi.runtime import life

        def triggers(*args: object, **kwargs: object) -> object:
            pause()
            return interaction_triggers(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(life, "interaction_triggers", triggers)
    elif path == "external":
        from maplegotchi.runtime import life

        brain = external(runtime)
        brain.release.set()

        def accept(*args: object, **kwargs: object) -> object:
            pause()
            return accept_drafts(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(life, "accept_drafts", accept)
    else:
        original_commit = runtime._calls.commit

        @contextmanager
        def commit() -> Iterator[None]:
            pause()
            with original_commit():
                yield

        monkeypatch.setattr(runtime._calls, "commit", commit)

    def operation() -> object:
        if path == "receive":
            return runtime.receive_message_committed(message)
        if path == "reply":
            assert received is not None
            return runtime.record_reply_committed(
                received.message_id,
                "Hello.",
                replier_kind="rule",
                replier_name="rule_replier",
                fallback_code=None,
            )
        if path == "stale_audit":
            assert pending is not None
            return runtime.decide_proposal_committed(
                pending, director=DirectorLabel("external", "test", "1"), raw=GOOD
            )
        return runtime.interact_committed(InteractionKind.GREET)

    caller = Call(operation)
    closer: Call | None = None
    try:
        assert entered.wait(10)  # preparation/validation owns writer lock first
        closer = Call(runtime.close)
        assert stopped.wait(10)  # shutdown owns gate first, then waits for writer
        assert storage_open(runtime) and not closer.done.is_set()
        release.set()
        with pytest.raises(RuntimeClosedError, match="commit admission"):
            caller.finish()
        closer.finish()
        assert (runtime.state, runtime.revision, runtime.reflection_state) == before
        with open_runtime(data, clock) as reopened:
            assert (reopened.state, reopened.revision, reopened.reflection_state) == before
            assert reopened.journal() == journal and reopened.timeline() == timeline
            assert reopened.messages(limit=10) == messages
    finally:
        release.set()
        caller.done.wait(10)
        if closer is not None:
            closer.finish()
        runtime.close()


@pytest.mark.parametrize("path", ["rule", "external"])
def test_commit_permit_wins_before_shutdown_and_storage_drains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    data, clock, runtime = new_life(tmp_path)
    service = MapleService(runtime, fake_senses(), clock, PARAMS)
    if path == "external":
        external(runtime).release.set()
    before = runtime.revision
    admitted, release, stopped = threading.Event(), threading.Event(), threading.Event()
    original_commit, original_stop = runtime._calls.commit, runtime._calls.stop

    @contextmanager
    def commit() -> Iterator[None]:
        with original_commit():
            admitted.set()  # permit issued; SQLite transaction has not started
            assert release.wait(10)
            yield

    def stop() -> None:
        original_stop()
        stopped.set()

    monkeypatch.setattr(runtime._calls, "commit", commit)
    monkeypatch.setattr(runtime._calls, "stop", stop)
    caller = Call(lambda: service.interact(InteractionKind.GREET))
    closer: Call | None = None
    try:
        assert admitted.wait(10)
        closer = Call(service.close)
        assert stopped.wait(10)  # gate lock is not retained by permitted transaction
        assert storage_open(runtime) and not closer.done.is_set()
        with pytest.raises(RuntimeClosedError):
            service.snapshot()
        release.set()
        caller.finish()  # includes publication and nested final snapshot
        closer.finish()
        assert runtime._repo is None
        assert runtime.revision == before + 1
        with open_runtime(data, clock) as reopened:
            assert reopened.revision == before + 1
            assert len(reopened.state.recent_interactions) == 1
            assert len(reopened.journal()) == 1
            assert reopened.reflection_state.last_interaction_entry_at is not None
            assert len(reopened.timeline()) == 2  # birth and one interaction
    finally:
        release.set()
        caller.done.wait(10)
        if closer is not None:
            closer.finish()
        service.close()


def test_external_proposal_overtaken_during_journal_composition_is_audit_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, clock, runtime = new_life(tmp_path)
    clock.advance(TICK * 4)
    pending = runtime.pending_decision()
    assert pending is not None

    def triggers(
        rs: ReflectionState, **kwargs: object
    ) -> tuple[tuple[Trigger, ...], ReflectionState]:
        return (Trigger(TriggerKind.MILESTONE, "milestone:first_heartbeat", "first_heartbeat"),), rs

    monkeypatch.setattr("maplegotchi.runtime.life.settle_triggers", triggers)
    brain = external(runtime)
    caller = Call(
        lambda: runtime.decide_proposal_committed(
            pending, director=DirectorLabel("external", "test", "1"), raw=GOOD
        )
    )
    try:
        assert brain.entered.wait(10)
        assert runtime.decide_committed() is not None
        winning = runtime.state
        revision = runtime.revision
        brain.release.set()
        assert caller.finish() is None
        assert runtime.state == winning and runtime.revision == revision + 1
        assert runtime.decisions(limit=1)[-1].record.verdict is Verdict.STALE
        assert runtime.journal() == [] and len(brain.contexts) == 1
    finally:
        brain.release.set()
        caller.done.wait(10)
        runtime.close()


@pytest.mark.parametrize("provider", ["director", "replier"])
def test_shutdown_drains_active_provider_call_without_new_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    data, clock, runtime = new_life(tmp_path)
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()

    def answer() -> None:
        entered.set()
        assert release.wait(10)

    def propose(context: object) -> object:
        answer()
        return GOOD

    class Replier:
        kind = "external"
        name = "test"

        def reply(self, context: ReplyContext) -> str:
            answer()
            return "Hello."

    service = MapleService(
        runtime,
        fake_senses(),
        clock,
        PARAMS,
        director=FakeDirector(propose) if provider == "director" else None,
        replier=Replier() if provider == "replier" else None,
        director_timeout_seconds=60,
    )
    original_stop = runtime._calls.stop

    def stop() -> None:
        original_stop()
        stopped.set()

    monkeypatch.setattr(runtime._calls, "stop", stop)
    clock.advance(TICK * 4)
    before = runtime.revision
    message = IncomingMessage("probe", Channel.DISCORD, Speaker.PAOLO, "Hello", clock.now())
    caller = Call(service.decide if provider == "director" else lambda: service.converse(message))
    closer: Call | None = None
    try:
        assert entered.wait(10)
        closer = Call(service.close)
        assert stopped.wait(10)
        assert storage_open(runtime) and not closer.done.is_set()
        release.set()
        with pytest.raises(RuntimeClosedError):
            caller.finish()
        closer.finish()
        with open_runtime(data, clock) as reopened:
            assert reopened.revision == before + (provider == "replier")
            assert len(reopened.messages(limit=10)) == (provider == "replier")
            assert not reopened.decisions(limit=10)
    finally:
        release.set()
        caller.done.wait(10)
        if closer is not None:
            closer.finish()
        service.close()
