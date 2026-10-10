# R1A-01 — Kickoff baseline and focused task plan

**Status:** IN PROGRESS — baseline/documentation preparation only (2026-10-10, +07).
Master Plan: `maple-room-r1a-plan.md` §3 R1A-01, §7–§9. Live status:
`maple-room-r1a-checklist.md`; history: `maple-room-r1a-worklog.md`.

## Starting baseline and evidence

| Evidence | Recorded result | Provenance / limitation |
|---|---|---|
| Repository / remote | `C:\GitHub\Maplegotchi`; origin `https://github.com/payola469/Maplegotchi.git` (fetch/push) | Local Git inspection on Windows |
| Starting commit | `5c6db41c0139e1da6a2178b36d838e4da57074b1` | Owner-approved; local HEAD verified |
| Development branch | `codex/r1a-01-baseline` | Created from the exact approved commit; initial working tree clean |
| Target / remote-tracking baseline | Local `v0.2-development` and `origin/v0.2-development` point to the approved commit | No fresh fetch in this kickoff; not a new server synchronization claim |
| Pre-R1 clearance / R1a authorization | APPROVED / AUTHORIZED by owner, 2026-10-10 | Supersedes prior BLOCKED / NOT AUTHORIZED status; only R1A-01 starts now |
| R-01 production | Owner confirms implemented, merged, deployed to paolo-core; HTTP Health PASS | No agent production access; exact deployed SHA, activation time and detailed post-deployment evidence not supplied with this approval |
| Earlier R-01 validation | 389 runtime/API/security tests; Ruff; Linux mypy 179 files; seven import contracts; seven persistence sites guarded | Prior feature-branch evidence recorded in worklog; not a complete exact-start-commit release gate or new run |
| Exact-start-commit release gate | NOT PASSED / incomplete evidence | Previous `scripts/check.sh` invocation failed during Git Bash startup (`NtCreateDirectoryObject`, `0xC0000022`), before any stage; uv was unavailable on PATH. Not rerun here |
| CI | Complete exact-start-commit evidence unavailable | Earlier GitHub lookup returned no statuses / PR-associated runs; not proof that no other runs exist; not re-queried here |
| Existing test counts | Historical R-01 totals above only | Full baseline test count and platform results remain unverified |
| Pinned 30-day simulation digest | `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917` | Read from `backend/tests/core/test_simulation.py::test_thirty_day_digest_is_pinned`; expected regression value, not a newly computed result or identity fingerprint |
| Approved route reference | Final Design Spec §T6, "Walk lengths between the canonical activity points"; T4 points and T7 legacy projection | Source located/read only; no new route computation or oracle validation. Longest documented walk: 53 steps |
| Schema / view | Repository latest schema v10; legacy production default retained | No schema, runtime or view changes in this step; prior owner production schema evidence v10, not freshly measured |

## R1A-01 focused task plan

This breaks down the existing workstream; it does not change its acceptance criteria.

1. **Kickoff (this change):** record owner decisions, branch, starting baseline and
   evidence gaps; update checklist/counters and append worklog. No engine or oracle code.
2. **Baseline verification (next authorized implementation step):** establish a usable
   local check environment without deleting the retained paolo-core build environment;
   collect exact-start-commit check/CI evidence, full counts and the computed pinned
   simulation digest. Preserve failed attempts. No full gate rerun in this kickoff.
3. **Test-side spec oracle (later within R1A-01):** encode T1–T7 and the T6 walk matrix
   as test input, with parsing and deliberate-mutation rejection tests. It must never
   become runtime geometry data. Do not implement it in this step.
4. **Harness boundaries (later within R1A-01):** establish package placement, import
   and AST purity contracts (including catalog at `maplegotchi/world_catalog/`), with
   positive and planted-violation tests; no world behavior or catalog content.
5. **Fixture/property conventions (later within R1A-01):** document deterministic
   generators or a reviewed test dependency, fake time, scratch databases and sanitized
   evidence conventions. No dependency decision is made in this kickoff.
6. **R1A-01 acceptance:** collect baseline/harness/contract evidence, update docs,
   obtain review and merge under existing policy. R1A-02–R1A-20 remain TODO until
   separately started according to dependencies; no DONE claim from preparation alone.

## Completion gaps and safeguards

Still missing: successful full baseline checks, complete CI evidence, current full
test counts, a computed digest match, the usable oracle/harness, enforced contracts
and fixture/property conventions. Owner gate clearance authorizes starting work;
it does not supply these completion results or waive existing check requirements.

ADR-locked values > accepted ADR rules > Final Design Spec > PROPOSED text.
Keep schema v10 and the legacy default view; no production deployment/restart,
database/backup changes, R-01 rework or paolo-core build-environment removal.
Any architecture conflict follows Master Plan §8's stop rule. This kickoff changes
documentation only; no World Model, Test Oracle or Engine is created.
