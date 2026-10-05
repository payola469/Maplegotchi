"""Real reading and writing (ADR-0029), as pure rules and pure text work.

- A `Task` says what a `read` or `write` action is actually about: the tool,
  the target (a catalog id to read, or a workspace document kind to write), a
  title and a category. It is part of Maple's state, so the UI can show it.
- Reading is limited to a catalog of `SourceRef`s, addressed by id (never by
  path). The static part, approved documentation shipped with the release, is
  `LIBRARY_CATALOG`; the runtime adds Maple's own documents, recent journal,
  and server status.
- `extract` and `compose_document` are deterministic text functions; the I/O of
  fetching source text and storing documents belongs to runtime and storage.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import GoalType
from maplegotchi.core.rng import RngStream

MAX_TITLE = 80
MAX_BODY = 4000
MAX_EXTRACT = 280
MAX_DETAIL = 200
_TARGET = re.compile(r"[a-z][a-z0-9_]*:[a-z0-9_.-]{1,48}")


class Tool(StrEnum):
    READER = "reader"
    WRITER = "writer"


class WriteKind(StrEnum):
    NOTE = "note"
    SUMMARY = "summary"
    REFLECTION = "reflection"
    RESEARCH = "research"


class SourceKind(StrEnum):
    LIBRARY = "library"  # approved documentation in the release (read-only)
    DOCUMENT = "document"  # Maple's own workspace
    JOURNAL = "journal"  # Maple's recent journal
    SERVER = "server"  # latest stored observations
    MEMORY = "memory"  # Maple's long-term memory (ADR-0030)


class ToolOp(StrEnum):
    READ_STARTED = "read_started"
    READ_COMPLETED = "read_completed"
    READ_FAILED = "read_failed"
    WRITE_STARTED = "write_started"
    WRITE_COMPLETED = "write_completed"
    WRITE_FAILED = "write_failed"


def one_line(text: str, limit: int) -> str:
    """Collapse whitespace, drop non-printables, and cut to `limit` characters."""
    flat = " ".join("".join(c if c.isprintable() else " " for c in text).split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class SourceRef:
    id: str  # "<kind>:<name>"
    kind: SourceKind
    title: str
    category: str

    def __post_init__(self) -> None:
        if not _TARGET.fullmatch(self.id) or not self.id.startswith(self.kind.value + ":"):
            raise ValueError(f"bad source id {self.id!r}")
        if not 1 <= len(self.title) <= MAX_TITLE or not self.title.isprintable():
            raise ValueError("source title must be one short line")


@dataclass(frozen=True, slots=True)
class Task:
    tool: Tool
    target: str
    title: str
    category: str

    def __post_init__(self) -> None:
        if not isinstance(self.tool, Tool):
            raise TypeError("tool must be a Tool")
        if not _TARGET.fullmatch(self.target):
            raise ValueError(f"bad task target {self.target!r}")
        if not 1 <= len(self.title) <= MAX_TITLE or not self.title.isprintable():
            raise ValueError("task title must be one short line")
        if not 1 <= len(self.category) <= 40:
            raise ValueError("task category must be 1-40 characters")

    def fits(self, activity: Activity) -> bool:
        return (self.tool is Tool.READER and activity is Activity.READ) or (
            self.tool is Tool.WRITER and activity is Activity.WRITE
        )


# Approved documentation shipped with the release (maplegotchi/library/; a test
# checks every id has a file and every file has an id).
LIBRARY_CATALOG: tuple[SourceRef, ...] = (
    SourceRef("library:about_maple", SourceKind.LIBRARY, "About Maple", "self"),
    SourceRef("library:the_room", SourceKind.LIBRARY, "Maple's room", "home"),
    SourceRef("library:paolo_core", SourceKind.LIBRARY, "paolo-core, the server", "server"),
    SourceRef("library:caring_for_a_server", SourceKind.LIBRARY, "Caring for a server", "server"),
    SourceRef("library:keeping_notes", SourceKind.LIBRARY, "Keeping good notes", "writing"),
)
JOURNAL_SOURCE = SourceRef("journal:recent", SourceKind.JOURNAL, "My recent journal", "self")
SERVER_SOURCE = SourceRef("server:status", SourceKind.SERVER, "paolo-core status", "server")

WRITE_TITLES = {
    WriteKind.NOTE: "A note",
    WriteKind.SUMMARY: "A summary",
    WriteKind.REFLECTION: "A reflection",
    WriteKind.RESEARCH: "A research note",
}

_READ_PREFERENCE: dict[GoalType, tuple[SourceKind, ...]] = {
    GoalType.MONITOR: (SourceKind.SERVER,),
    GoalType.MAINTAIN: (SourceKind.SERVER, SourceKind.LIBRARY),
    GoalType.HELP: (SourceKind.SERVER, SourceKind.LIBRARY),
    GoalType.INVESTIGATE: (SourceKind.SERVER, SourceKind.LIBRARY),
    GoalType.REFLECT: (SourceKind.JOURNAL, SourceKind.DOCUMENT, SourceKind.MEMORY),
    GoalType.REMEMBER: (SourceKind.MEMORY, SourceKind.JOURNAL, SourceKind.DOCUMENT),
    GoalType.ORGANIZE: (SourceKind.DOCUMENT, SourceKind.JOURNAL),
}
_WRITE_KIND: dict[GoalType, WriteKind] = {
    GoalType.CREATE: WriteKind.NOTE,
    GoalType.PRACTICE: WriteKind.NOTE,
    GoalType.PLAY: WriteKind.NOTE,
    GoalType.ORGANIZE: WriteKind.SUMMARY,
    GoalType.PLAN: WriteKind.SUMMARY,
    GoalType.MAINTAIN: WriteKind.SUMMARY,
    GoalType.REFLECT: WriteKind.REFLECTION,
    GoalType.REMEMBER: WriteKind.REFLECTION,
    GoalType.RECOVER: WriteKind.REFLECTION,
    GoalType.WAIT: WriteKind.REFLECTION,
    GoalType.SOCIALIZE: WriteKind.REFLECTION,
}


def write_task(kind: WriteKind) -> Task:
    return Task(Tool.WRITER, f"workspace:{kind.value}", WRITE_TITLES[kind], kind.value)


def read_task(source: SourceRef) -> Task:
    return Task(Tool.READER, source.id, source.title, source.category)


def rule_task(
    activity: Activity,
    goal: GoalType | None,
    catalog: Sequence[SourceRef],
    rng: RngStream,
) -> Task | None:
    """Rule direction's choice of what to read or write (a seeded draw among fits)."""
    if activity is Activity.WRITE:
        kind = _WRITE_KIND.get(goal, WriteKind.RESEARCH) if goal else WriteKind.NOTE
        return write_task(kind)
    if activity is not Activity.READ or not catalog:
        return None
    preferred = (
        _READ_PREFERENCE.get(goal, (SourceKind.LIBRARY, SourceKind.DOCUMENT)) if goal else ()
    )
    pool = [s for s in catalog if s.kind in preferred] or list(catalog)
    return read_task(pool[rng.randint(0, len(pool) - 1)])


def proposed_task(
    activity: Activity, target: str | None, catalog: Sequence[SourceRef]
) -> Task | str | None:
    """A Director's `action.target`, resolved against the catalog.

    Returns the task (or None when the action has no task and none was asked
    for), or the rejection code string "unknown_target" / "malformed".
    """
    if target is None:
        return None if activity not in (Activity.READ, Activity.WRITE) else "malformed"
    if activity is Activity.READ:
        source = next((s for s in catalog if s.id == target), None)
        return read_task(source) if source else "unknown_target"
    if activity is Activity.WRITE:
        try:
            return write_task(WriteKind(target))
        except ValueError:
            return "unknown_target"
    return "malformed"


# ---------------------------------------------------------------- reading

_HEADING = re.compile(r"^\s{0,3}#+\s*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def extract(text: str) -> str:
    """The gist of a text: its first paragraph's first sentences, one short line."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = [p for p in paragraphs if not _HEADING.match(p)] or paragraphs
    if not body:
        return ""
    first = " ".join(_HEADING.sub("", line) for line in body[0].splitlines())
    sentences = _SENTENCE.split(" ".join(first.split()))
    gist = ""
    for sentence in sentences:
        candidate = f"{gist} {sentence}".strip()
        if len(candidate) > MAX_EXTRACT and gist:
            break
        gist = candidate
    return one_line(gist, MAX_EXTRACT)


# ---------------------------------------------------------------- writing


@dataclass(frozen=True, slots=True)
class Reading:
    title: str
    extract: str
    target: str


@dataclass(frozen=True, slots=True)
class WritingInputs:
    """Facts already in Maple's life that a document may draw on."""

    now: datetime
    name: str
    goal_type: GoalType | None
    goal_summary: str | None
    readings: tuple[Reading, ...] = ()  # most recent last
    journal: tuple[str, ...] = ()  # most recent last
    server: str | None = None  # one factual line about the server
    memories: tuple[str, ...] = ()  # relevant long-term memories (ADR-0030)

    def __post_init__(self) -> None:
        require_utc(self.now, "now")


@dataclass(frozen=True, slots=True)
class DocumentDraft:
    kind: WriteKind
    title: str
    body: str
    sources: tuple[str, ...]  # catalog ids it drew on

    def __post_init__(self) -> None:
        if not 1 <= len(self.title) <= MAX_TITLE or not self.title.isprintable():
            raise ValueError("document title must be one short line")
        if not 1 <= len(self.body) <= MAX_BODY:
            raise ValueError("document body must be 1-4000 characters")


def _bullets(lines: Sequence[str]) -> list[str]:
    return [f"- {one_line(line, 300)}" for line in lines if line.strip()]


def compose_document(kind: WriteKind, inputs: WritingInputs) -> DocumentDraft:
    """Write a plain-text document from facts in Maple's life. Deterministic."""
    readings = inputs.readings[-3:]
    journal = inputs.journal[-3:]
    goal = inputs.goal_summary
    lines: list[str] = []
    if kind is WriteKind.RESEARCH:
        topic = readings[-1].title if readings else "what I have been reading"
        title = f"Research note: {topic}"
        lines += [f"What I read about {topic}:"]
        lines += _bullets([f"{r.title}: {r.extract}" for r in readings]) or ["- (nothing yet)"]
        if goal:
            lines += ["", f"Why it matters to me now: {goal}."]
    elif kind is WriteKind.SUMMARY:
        title = "Summary of my recent time"
        lines += ["What I have been doing and noticing:"]
        lines += _bullets([f"Read {r.title}." for r in readings])
        lines += _bullets(journal)
        if inputs.server:
            lines += _bullets([f"Server: {inputs.server}"])
        if len(lines) == 1:
            lines += ["- A quiet stretch; not much to summarise yet."]
    elif kind is WriteKind.REFLECTION:
        title = "A reflection"
        lines += ["How things feel from here:"]
        lines += _bullets(journal) or ["- I have not written much in my journal yet."]
        lines += _bullets([f"I remember: {m}" for m in inputs.memories[-2:]])
        if goal:
            lines += ["", f"What I am reaching for: {goal}."]
    else:
        title = f"A note while {goal.lower()}" if goal else "A small note"
        lines += [f"{inputs.name}'s note."]
        lines += _bullets([f"From {r.title}: {r.extract}" for r in readings[-1:]])
        lines += _bullets(journal[-1:])
    body = "\n".join(lines).strip()
    if len(body) > MAX_BODY:
        body = body[: MAX_BODY - 1].rstrip() + "…"
    sources = tuple(dict.fromkeys(r.target for r in readings))
    return DocumentDraft(kind, one_line(title, MAX_TITLE), body, sources)


# ---------------------------------------------------------------- provenance


@dataclass(frozen=True, slots=True)
class ToolRecord:
    """Provenance of one reader/writer step (ADR-0029 §5)."""

    op: ToolOp
    at: datetime
    action_id: int
    goal_id: int | None
    task: Task
    success: bool
    detail: str | None = None  # an extract, or a failure code; one short line
    chars: int | None = None
    document: DocumentDraft | None = None  # written by this step (write_completed)

    def __post_init__(self) -> None:
        require_utc(self.at, "tool.at")
        if self.detail is not None and (
            len(self.detail) > MAX_DETAIL or not self.detail.isprintable()
        ):
            raise ValueError("tool detail must be one short printable line")
        if self.document is not None and not (self.op is ToolOp.WRITE_COMPLETED and self.success):
            raise ValueError("only a successful write_completed may carry a document")
