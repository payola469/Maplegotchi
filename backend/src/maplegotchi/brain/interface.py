"""The replaceable Brain boundary (D10, CLAUDE.md §3.6).

A Brain receives a `BrainContext` — plain, immutable data: Maple's state and
expression, the current observation snapshot, and core-detected triggers — and
returns `JournalDraft`s: proposed wording, one per trigger. It holds no handles,
cannot read files, clocks, the network, or storage, and its output is untrusted
until `core.journal.accept_drafts` validates it.

A Brain never decides whether Maple writes, what an entry refers to, or anything
about Maple's behavior or state.

External brains (`BrainKind.EXTERNAL`) use this same protocol. Since v0.2
(ADR-0025) the runtime may wire one when explicitly configured
(`MAPLE_BRAIN=antigravity` selects `runtime/external_brain.py:ExternalHttpBrain`,
which calls the loopback companion's `/generate`); the default is the built-in
RuleBrain. Only the built-in RuleBrain may claim `kind=rule`
(`runtime/life.py:require_supported_brain`). This package stays pure: transport
lives in `runtime`, never here.
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
