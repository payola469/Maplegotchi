"""The replaceable Brain boundary (D10, CLAUDE.md §3.6).

A Brain receives a `BrainContext` — plain, immutable data: Maple's state and
expression, the current observation snapshot, and core-detected triggers — and
returns `JournalDraft`s: proposed wording, one per trigger. It holds no handles,
cannot read files, clocks, the network, or storage, and its output is untrusted
until `core.journal.accept_drafts` validates it.

A Brain never decides whether Maple writes, what an entry refers to, or anything
about Maple's behavior or state.

External brains (`BrainKind.EXTERNAL`) are defined by this same protocol but are
not implemented, and the runtime refuses to wire any Brain other than the
built-in RuleBrain in v0.1 (D6: an ordinary heartbeat never invokes an external
Brain).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from maplegotchi.core.journal import BrainContext, BrainKind, JournalDraft


class Brain(Protocol):
    @property
    def kind(self) -> BrainKind: ...

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def compose_journal(self, context: BrainContext) -> Sequence[JournalDraft]: ...
