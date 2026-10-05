"""The reader/writer I/O for task transitions (ADR-0029).

Pure core decides *what* a `read` or `write` action is about (the task). This
module does the small amount of real work when actions start and end:

- reading fetches text only from the approved catalog, by id: the release's
  library (`maplegotchi.library`), Maple's own documents, Maple's recent
  journal, and the latest stored observations — never a path;
- writing composes a document with core's deterministic writer, from facts
  already in Maple's life, and hands it to the commit (Maple's workspace is the
  `document` table in maple.db; no file is written).

Everything runs inside the single writer's transition, so provenance, documents
and the state change commit together or not at all.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from maplegotchi.core.state import MapleState
from maplegotchi.core.tasks import (
    JOURNAL_SOURCE,
    LIBRARY_CATALOG,
    MAX_DETAIL,
    SERVER_SOURCE,
    Reading,
    SourceKind,
    SourceRef,
    Task,
    Tool,
    ToolOp,
    ToolRecord,
    WriteKind,
    WritingInputs,
    compose_document,
    extract,
    one_line,
)
from maplegotchi.library import library_text
from maplegotchi.storage.repositories import LifeRepository

RECENT_DOCUMENTS = 5
RECENT_JOURNAL = 5


class SourceUnavailable(LookupError):
    pass


class TaskWorker:
    def __init__(self, library: Callable[[str], str] = library_text) -> None:
        self._library = library

    # ------------------------------------------------------------ catalog

    def catalog(self, repo: LifeRepository) -> tuple[SourceRef, ...]:
        """Everything Maple may read right now (ADR-0029 §2)."""
        refs: list[SourceRef] = list(LIBRARY_CATALOG)
        for doc in repo.documents(limit=RECENT_DOCUMENTS):
            refs.append(
                SourceRef(
                    f"document:{doc.id}", SourceKind.DOCUMENT, one_line(doc.title, 80), doc.kind
                )
            )
        if repo.journal(limit=1):
            refs.append(JOURNAL_SOURCE)
        if repo.latest_observation_tick() is not None:
            refs.append(SERVER_SOURCE)
        return tuple(refs)

    def source_text(self, repo: LifeRepository, target: str) -> str:
        kind, _, name = target.partition(":")
        if kind == SourceKind.LIBRARY:
            try:
                return self._library(target)
            except KeyError as exc:
                raise SourceUnavailable(target) from exc
        if kind == SourceKind.DOCUMENT and name.isdigit():
            doc = repo.document(int(name))
            if doc is None:
                raise SourceUnavailable(target)
            return f"# {doc.title}\n\n{doc.body}"
        if target == JOURNAL_SOURCE.id:
            entries = repo.journal(limit=RECENT_JOURNAL)
            if not entries:
                raise SourceUnavailable(target)
            return "\n\n".join(e.entry.text for e in entries)
        if target == SERVER_SOURCE.id:
            tick = repo.latest_observation_tick()
            if tick is None:
                raise SourceUnavailable(target)
            lines = [
                f"{o.observation.metric.value} {o.observation.subject}: "
                f"{o.observation.state.value if o.observation.state else o.observation.value}"
                f" ({o.observation.status.value})"
                for o in repo.observations(tick_id=tick)
            ]
            return "The latest facts about paolo-core.\n\n" + "\n".join(lines)
        raise SourceUnavailable(target)

    # ------------------------------------------------------------ effects

    def effects(
        self,
        repo: LifeRepository,
        before: MapleState,
        after: MapleState,
        now: datetime,
        *,
        server_line: str | None = None,
    ) -> tuple[ToolRecord, ...]:
        """Provenance (and any document) for the tasks this transition ends and starts."""
        if after.action_id == before.action_id:
            return ()
        records: list[ToolRecord] = []
        old = before.task
        if old is not None:
            completed = now >= before.activity_until
            records.append(self._finish(repo, before, old, now, completed, server_line))
        new = after.task
        if new is not None:
            records.append(self._start(repo, after, new, now))
        return tuple(records)

    def _goal_id(self, state: MapleState) -> int | None:
        return state.goal.id if state.goal else None

    def _start(
        self, repo: LifeRepository, state: MapleState, task: Task, now: datetime
    ) -> ToolRecord:
        if task.tool is Tool.WRITER:
            return ToolRecord(
                ToolOp.WRITE_STARTED, now, state.action_id, self._goal_id(state), task, True
            )
        try:
            text = self.source_text(repo, task.target)
        except SourceUnavailable:
            return ToolRecord(
                ToolOp.READ_FAILED,
                now,
                state.action_id,
                self._goal_id(state),
                task,
                False,
                detail="unavailable",
            )
        return ToolRecord(
            ToolOp.READ_STARTED,
            now,
            state.action_id,
            self._goal_id(state),
            task,
            True,
            detail=one_line(extract(text), MAX_DETAIL) or None,
            chars=len(text),
        )

    def _finish(
        self,
        repo: LifeRepository,
        state: MapleState,
        task: Task,
        now: datetime,
        completed: bool,
        server_line: str | None,
    ) -> ToolRecord:
        at = min(now, state.activity_until) if completed else now
        goal_id = self._goal_id(state)
        if not completed:
            op = ToolOp.READ_FAILED if task.tool is Tool.READER else ToolOp.WRITE_FAILED
            return ToolRecord(op, at, state.action_id, goal_id, task, False, detail="interrupted")
        if task.tool is Tool.READER:
            try:
                text = self.source_text(repo, task.target)
            except SourceUnavailable:
                return ToolRecord(
                    ToolOp.READ_FAILED, at, state.action_id, goal_id, task, False,
                    detail="unavailable",
                )  # fmt: skip
            return ToolRecord(
                ToolOp.READ_COMPLETED,
                at,
                state.action_id,
                goal_id,
                task,
                True,
                detail=one_line(extract(text), MAX_DETAIL) or None,
                chars=len(text),
            )
        draft = compose_document(
            WriteKind(task.category),
            self.writing_inputs(repo, state, at, server_line),
        )
        return ToolRecord(
            ToolOp.WRITE_COMPLETED,
            at,
            state.action_id,
            goal_id,
            task,
            True,
            detail=one_line(draft.title, 200),
            chars=len(draft.body),
            document=draft,
        )

    def writing_inputs(
        self,
        repo: LifeRepository,
        state: MapleState,
        now: datetime,
        server_line: str | None,
        memories: Sequence[str] = (),
    ) -> WritingInputs:
        reads = repo.tool_uses(operation=ToolOp.READ_COMPLETED, limit=3)
        readings = tuple(
            Reading(r.record.task.title, r.record.detail or "", r.record.task.target)
            for r in reads
            if r.record.success
        )
        journal = tuple(e.entry.text for e in repo.journal(limit=3))
        goal = state.goal
        return WritingInputs(
            now=now,
            name=state.identity.name,
            goal_type=goal.type if goal else None,
            goal_summary=goal.summary if goal else None,
            readings=readings,
            journal=journal,
            server=server_line,
            memories=tuple(memories),
        )
