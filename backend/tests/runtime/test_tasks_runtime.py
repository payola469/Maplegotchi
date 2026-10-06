"""Real reading and writing through the runtime and API (ADR-0029)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.tasks import Task, Tool, ToolOp
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService
from maplegotchi.runtime.tasks import SourceUnavailable, TaskWorker
from tests.api.support import make_client, make_service
from tests.persistence_support import BIRTH

Life = tuple[MapleService, Path]


@pytest.fixture(scope="module")
def life(tmp_path_factory: pytest.TempPathFactory) -> Life:
    root = tmp_path_factory.mktemp("tasks") / "data"
    clock = FakeClock(BIRTH)
    service = make_service(root, clock)
    for _ in range(14 * 12):  # fourteen hours, a step every five minutes
        clock.advance(timedelta(minutes=5))
        service.step()
    return service, root


def test_reading_records_what_was_read_with_success_and_size(life: Life) -> None:
    service, _ = life
    uses = service.runtime.tool_uses(limit=500)
    started = [u.record for u in uses if u.record.op is ToolOp.READ_STARTED]
    completed = [u.record for u in uses if u.record.op is ToolOp.READ_COMPLETED]
    assert started and completed
    for r in started + completed:
        assert r.success and r.chars and r.chars > 0
        assert r.detail  # the extract actually read
        assert r.task.target.split(":")[0] in {"library", "document", "journal", "server"}


def test_writing_produces_real_documents_in_maples_workspace(life: Life) -> None:
    service, _ = life
    uses = service.runtime.tool_uses(limit=500)
    written = [u for u in uses if u.record.op is ToolOp.WRITE_COMPLETED]
    assert written and all(u.document_id for u in written)
    docs = service.runtime.documents(limit=50)
    assert {d.id for d in docs} >= {u.document_id for u in written}
    for doc in docs:
        assert doc.body and doc.title
        assert doc.kind.value in {"note", "summary", "reflection", "research"}


def test_writing_creates_no_files(life: Life) -> None:
    _, root = life
    names = {p.name for p in root.iterdir()}
    assert names <= {"maple.db", "maple.db-wal", "maple.db-shm"}


def test_documents_api_serves_the_workspace(life: Life, tmp_path: Path) -> None:
    service, _ = life
    client = make_client(service, tmp_path)
    listing = client.get("/api/documents?limit=10").json()
    assert listing and {"id", "kind", "title", "created_at", "chars"} <= set(listing[0])
    one = client.get(f"/api/documents/{listing[-1]['id']}").json()
    assert one["body"] and one["id"] == listing[-1]["id"]
    assert client.get("/api/documents/999999").status_code == 404
    assert client.get("/api/documents/0").status_code == 422


def test_life_events_include_tool_provenance(life: Life, tmp_path: Path) -> None:
    service, _ = life
    client = make_client(service, tmp_path)
    events = client.get("/api/life-events?after_revision=0&limit=500").json()["events"]
    tools = [e for e in events if e["id"].startswith("tool:")]
    assert {e["type"] for e in tools} >= {"read_started", "read_completed", "write_started"}
    assert all(e["payload"]["status"] in {"success", "failure"} for e in tools)


def test_snapshot_says_what_maple_is_reading_or_writing(life: Life) -> None:
    service, _ = life
    state = service.snapshot().state
    if state.activity in (Activity.READ, Activity.WRITE):
        assert state.task is not None and state.task.title
    else:
        assert state.task is None


def test_the_reader_only_reads_the_catalog(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    worker = TaskWorker()
    repo = service.runtime._repository()
    for target in (
        "library:../../etc/passwd",
        "file:/etc/passwd",
        "document:abc",
        "document:../maple.db",
        "journal:everything",
        "server:/proc",
        "/etc/shadow",
    ):
        with pytest.raises(SourceUnavailable):
            worker.source_text(repo, target)
    assert worker.source_text(repo, "library:about_maple").startswith("# About Maple")
    service.close()


def test_an_interrupted_read_is_recorded_as_failed(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    worker = TaskWorker()
    repo = service.runtime._repository()
    state = service.runtime.state
    reading = replace(
        state,
        activity=Activity.READ,
        location=RoomLocation.BOOKSHELF,
        point_id=None,
        task=Task(Tool.READER, "library:the_room", "Maple's room", "home"),
        activity_until=state.last_updated_at + timedelta(minutes=30),
    )
    after = replace(
        reading,
        action_id=reading.action_id + 1,
        activity=Activity.IDLE,
        location=RoomLocation.RUG,
        task=None,
    )
    records = worker.effects(repo, reading, after, state.last_updated_at + timedelta(minutes=5))
    assert [(r.op, r.success, r.detail) for r in records] == [
        (ToolOp.READ_FAILED, False, "interrupted")
    ]
    service.close()
