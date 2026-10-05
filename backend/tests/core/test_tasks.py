"""Reading and writing as pure rules and text (ADR-0029)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.audit import Verdict
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.direction import DecisionTrigger
from maplegotchi.core.goals import GoalType
from maplegotchi.core.proposal import DirectorLabel, decide_with_proposal
from maplegotchi.core.rng import RngStream
from maplegotchi.core.tasks import (
    JOURNAL_SOURCE,
    LIBRARY_CATALOG,
    MAX_BODY,
    MAX_EXTRACT,
    SERVER_SOURCE,
    Reading,
    SourceKind,
    Task,
    Tool,
    WriteKind,
    WritingInputs,
    compose_document,
    extract,
    proposed_task,
    rule_task,
    write_task,
)
from maplegotchi.library import FILES, library_text
from tests.core.support import PARAMS, SEED, at_local, make_state

NOW = datetime(2026, 3, 1, 5, tzinfo=UTC)
NOON = at_local(12)
AG = DirectorLabel("external", "antigravity", "1")


def test_library_catalog_and_files_match_one_to_one() -> None:
    assert {s.id for s in LIBRARY_CATALOG} == set(FILES)
    for source in LIBRARY_CATALOG:
        text = library_text(source.id)
        assert text.strip() and source.kind is SourceKind.LIBRARY
        assert extract(text)


def test_library_refuses_anything_not_in_its_manifest() -> None:
    for bad in ("library:../../etc/passwd", "library:nope", "/etc/passwd", "document:1"):
        with pytest.raises(KeyError):
            library_text(bad)


def test_extract_takes_the_first_sentences_as_one_line() -> None:
    text = "# Title\n\nFirst sentence. Second one!\nStill second.  Third?\n\n## More\n\nOther."
    gist = extract(text)
    assert gist.startswith("First sentence. Second one!")
    assert "\n" not in gist and "#" not in gist
    long = "# T\n\n" + " ".join(f"Sentence number {i} is here." for i in range(100))
    assert len(extract(long)) <= MAX_EXTRACT


def test_documents_are_deterministic_bounded_and_cite_their_sources() -> None:
    inputs = WritingInputs(
        now=NOW,
        name="Maple",
        goal_type=GoalType.LEARN,
        goal_summary="Learn about the server",
        readings=(Reading("paolo-core, the server", "It runs a collector.", "library:paolo_core"),),
        journal=("I watched the server today.",),
        server="nothing notable in the latest observations",
    )
    for kind in WriteKind:
        a = compose_document(kind, inputs)
        assert a == compose_document(kind, inputs)
        assert a.kind is kind and 1 <= len(a.body) <= MAX_BODY
        assert "\n" not in a.title
    research = compose_document(WriteKind.RESEARCH, inputs)
    assert research.sources == ("library:paolo_core",)
    assert "It runs a collector." in research.body
    empty = compose_document(
        WriteKind.SUMMARY, replace(inputs, readings=(), journal=(), server=None)
    )
    assert empty.body


def test_rule_tasks_follow_the_goal_softly() -> None:
    rng = RngStream(SEED, "decision", 1)
    catalog = (*LIBRARY_CATALOG, JOURNAL_SOURCE, SERVER_SOURCE)
    monitor = rule_task(Activity.READ, GoalType.MONITOR, catalog, rng)
    assert monitor is not None and monitor.target == "server:status"
    reflect = rule_task(Activity.READ, GoalType.REFLECT, catalog, RngStream(SEED, "decision", 2))
    assert reflect is not None and reflect.target == "journal:recent"
    learn = {rule_task(Activity.READ, GoalType.LEARN, catalog, RngStream(SEED, "d", i)).target  # type: ignore[union-attr]
             for i in range(30)}  # fmt: skip
    assert len(learn) > 1 and all(t.startswith("library:") for t in learn)
    write = rule_task(Activity.WRITE, GoalType.REFLECT, catalog, rng)
    assert write == write_task(WriteKind.REFLECTION)
    assert rule_task(Activity.THINK, GoalType.LEARN, catalog, rng) is None


def test_director_targets_resolve_only_against_the_catalog() -> None:
    assert proposed_task(Activity.READ, "library:the_room", LIBRARY_CATALOG) == Task(
        Tool.READER, "library:the_room", "Maple's room", "home"
    )
    assert proposed_task(Activity.READ, "library:secrets", LIBRARY_CATALOG) == "unknown_target"
    assert proposed_task(Activity.READ, "/etc/shadow", LIBRARY_CATALOG) == "unknown_target"
    assert proposed_task(Activity.WRITE, "manifesto", LIBRARY_CATALOG) == "unknown_target"
    assert proposed_task(Activity.WRITE, "research", LIBRARY_CATALOG) == write_task(
        WriteKind.RESEARCH
    )
    assert proposed_task(Activity.THINK, "library:the_room", LIBRARY_CATALOG) == "malformed"


def test_state_task_must_fit_its_activity() -> None:
    reading = make_state(at=NOON, activity=Activity.READ)
    replace(reading, task=Task(Tool.READER, "library:the_room", "Maple's room", "home"))
    with pytest.raises(ValueError):
        replace(reading, task=write_task(WriteKind.NOTE))
    thinking = make_state(at=NOON, activity=Activity.THINK, location=RoomLocation.WINDOW)
    with pytest.raises(ValueError):
        replace(thinking, task=write_task(WriteKind.NOTE))


def proposal(action: dict[str, object]) -> dict[str, object]:
    return {
        "goal": {"op": "new", "type": "learn", "summary": "Learn the room", "horizon_minutes": 60},
        "action": action,
        "reason": "The room guide looks useful.",
    }


def test_a_director_can_choose_what_to_read_and_write() -> None:
    idle = make_state(at=NOON, until=timedelta(0))
    out = decide_with_proposal(
        idle, NOON, DecisionTrigger.ACTION_COMPLETED, BehaviorInputs(), PARAMS, director=AG,
        raw=proposal({"kind": "read", "duration_minutes": 25, "target": "library:the_room"}),
    )  # fmt: skip
    assert out.record is not None and out.record.verdict is Verdict.ACCEPTED
    assert out.state.task == Task(Tool.READER, "library:the_room", "Maple's room", "home")
    bad = decide_with_proposal(
        idle, NOON, DecisionTrigger.ACTION_COMPLETED, BehaviorInputs(), PARAMS, director=AG,
        raw=proposal({"kind": "read", "duration_minutes": 25, "target": "file:/etc/passwd"}),
    )  # fmt: skip
    assert bad.record is not None and bad.record.reason_code == "unknown_target"
    untargeted = decide_with_proposal(
        idle, NOON, DecisionTrigger.ACTION_COMPLETED, BehaviorInputs(), PARAMS, director=AG,
        raw=proposal({"kind": "write", "duration_minutes": 20}),
    )  # fmt: skip
    assert untargeted.record is not None and untargeted.record.verdict is Verdict.ACCEPTED
    assert untargeted.state.task is not None and untargeted.state.task.tool is Tool.WRITER


def test_rule_decisions_give_every_read_and_write_a_task() -> None:
    from maplegotchi.core.direction import decide

    for hour in range(8, 21):
        for seed in (SEED, "12" * 32, "34" * 32):
            s = make_state(at=at_local(hour), seed=seed, until=timedelta(0))
            out = decide(s, at_local(hour), DecisionTrigger.ACTION_COMPLETED, BehaviorInputs(),
                         PARAMS)  # fmt: skip
            if out.state.activity in (Activity.READ, Activity.WRITE):
                assert out.state.task is not None and out.state.task.fits(out.state.activity)
            else:
                assert out.state.task is None
