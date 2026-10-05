# ADR-0029: Real reading and writing — approved sources, Maple's workspace, provenance

- **Status:** Accepted — FIXED (CLAUDE.md D28)
- **Date:** 2026-10-05
- **Decided by:** owner (v0.2 autonomy program, Phase A5: "upgrade read/write from
  visual activities to actual permitted work"; read only approved sources; write
  only inside Maple-owned locations; provenance for every read/write).
  Details marked [PROPOSED] may be adjusted.
- **Related:** ADR-0016 (security principles), ADR-0020 (writable area), ADR-0024
  (backup), ADR-0026 (Director), ADR-0028 (events).

## Context

`read` and `write` were animations. Maple should actually read something and
actually write something, without gaining broad filesystem access or any way to
change code, configuration, systemd, secrets, other `/data` directories, or
arbitrary repositories.

## Decision

1. **Maple's workspace is a table in `maple.db`** (`document`: note, summary,
   reflection, research; title ≤ 80 chars, body ≤ 4,000 chars; append-only).
   It lives inside `/data/maple`, is covered by the existing integrity checks and
   the nightly backup (ADR-0024), and needs **no new filesystem write path**: the
   `DataDir` write jail and the systemd sandbox are unchanged.
2. **Reading is limited to an allowlisted catalog**, addressed by id, never by path:
   - `library:<id>` — approved documentation shipped read-only inside the release
     (`maplegotchi/library/`, root-owned under `/opt/maplegotchi/releases`), loaded
     with `importlib.resources` from a fixed manifest;
   - `document:<id>` — Maple's own workspace documents;
   - `journal:recent` — Maple's recent journal entries;
   - `server:status` — the latest stored observations (facts only).
   Memory sources are added by ADR-0030. There is no directory listing, glob,
   path argument, symlink following, or network fetch in the reader.
3. **Who chooses what to read/write**: the decision that starts a `read` or
   `write` action assigns its task. Rule direction picks a target from the catalog
   by goal; a Director may name one via the optional `action.target` of
   `maple.decision.v1` (a catalog id for `read`, a document kind for `write`).
   Core rejects unknown targets (`unknown_target`) and falls back.
4. **Writing is composed by core** from facts already in Maple's life (recent
   reading extracts, journal lines, the goal, server status): deterministic,
   template-based, plain text. A document is written when a `write` action
   *completes*; an interrupted write produces no document and a `write_failed`
   (`interrupted`) record. Brain/Director wording of documents is deferred.
5. **Provenance** (`tool_use`, append-only): every task records `read_started`
   (with success/failure and a short extract), `read_completed` / `read_failed`,
   `write_started`, `write_completed` (with the document id) / `write_failed`,
   with target, title, category, time, status, and character counts. These join
   the life-event envelope stream as store `tool`.
6. **Truthful UI**: the snapshot's activity carries the current task (tool,
   target, title, category), so the room can say *what* Maple is reading or
   writing, from backend state.
7. **Authority levels (unchanged boundary)**: reading the catalog and writing the
   workspace are autonomous. Anything else — system configuration, service
   management, other repositories, external data deletion, privileged commands —
   is not implemented and would need its own ADR and explicit owner approval.

## Schema v6 and rollback

`ALTER TABLE life_state ADD COLUMN task_*` and two new append-only tables. Like
every migration from v4 on, it is preceded by the verified automatic
`pre-migration/` copy and is forward-only; ADR-0028 R1-R8 apply unchanged.

## Consequences

- Maple's real work is small, inspectable text inside its own database.
- The approved library changes only with a reviewed release.
- Document wording is plain until a validated Brain wording path is designed.
