# R1A-01 — Kickoff baseline and focused task plan

**Status:** IN PROGRESS — baseline and test infrastructure only (2026-10-10, +07).
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
| Exact-start-commit release gate | **PASS**, exit code **0**, for `5c6db41c0139e1da6a2178b36d838e4da57074b1` | Previously verified result supplied by owner for this reconciliation (2026-10-10): isolated Docker environment on paolo-core, not Windows or GitHub CI. Not rerun; raw transcript/container details not supplied here |
| Gate checks | Ruff, mypy, import contracts, ShellCheck and frontend build **PASS** | Same owner-supplied full-gate evidence; not new local execution |
| Earlier Windows attempt | Git Bash startup failed (`NtCreateDirectoryObject`, `0xC0000022`), before any gate stage; uv unavailable on PATH | Historical local failure preserved; does not invalidate the separate Docker gate PASS or establish Windows compatibility |
| CI | Exact-start-commit Ubuntu / Windows backend and Ubuntu frontend results **unavailable** | GitHub rechecked 2026-10-10: combined-status lookup returned `statuses: []`; workflow lookup returned `workflow_runs: []`. Workflow tool filters to PR-triggered runs / first page only; neither response proves that no other runs exist. `.github/workflows/ci.yml` defines the matrix, not execution evidence |
| Existing test counts | Backend **1,510 passed / 1 skipped**; Discord **22 passed**; Brain **28 passed**; frontend **204 passed** | Owner-supplied Docker full-gate summary for exact starting commit; skip reason and per-test output unavailable. Historical 389 R-01 tests overlap the backend suite and are not additive |
| Pinned 30-day simulation digest | `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917` | Read from `backend/tests/core/test_simulation.py::test_thirty_day_digest_is_pinned`; expected regression value, not a newly computed result or identity fingerprint |
| Approved route reference | Final Design Spec §T6, "Walk lengths between the canonical activity points"; T4 points and T7 legacy projection | Source located/read only; no new route computation or oracle validation. Longest documented walk: 53 steps |
| Schema / view | Repository latest schema v10; legacy production default retained | No schema, runtime or view changes in this step; prior owner production schema evidence v10, not freshly measured |

## Source references and existing fixtures

- Pinned simulation expectation: `backend/tests/core/test_simulation.py:48-51`,
  `test_thirty_day_digest_is_pinned`. Master Plan §3 / R1A-01 requires recording it;
  the literal is in the regression test, not a separate digest literal in the design
  spec. It remains an expected value, not a new computed-output record.
- Simulation fixture: the same file's `START`, `DAYS`, `run()` and cached `baseline()`
  define 30 days from 2026-01-01 UTC, default parameters, daily owner routine and
  explicit behavior inputs. `backend/tests/core/support.py` supplies synthetic test
  seeds, `PARAMS`, explicit-time helpers and `make_state()`; no production identity
  or database is used or recorded here.
- Approved route matrix: `docs/architecture/maple-room-final-design-spec.md:644-656`,
  §T6 **Walk lengths between the canonical activity points**. The 7×7 matrix uses
  sleep/rest/read/think/write/observe/idle, diagonal zero, longest walk 53 steps.
  T4 supplies resolved points; T7 is the legacy projection. The spec's historical
  scratch-check record is not a new repository oracle result.
- `frontend/src/test/fixtures.ts` provides synthetic DTO snapshots, fixed time and
  legacy room points. These are compatibility fixtures, not the new grid oracle.
  T1–T7 remain the approved input for the later test-side oracle; no oracle fixture
  implementation or route recomputation was performed in this reconciliation.
- No baseline gate transcript/log was located in the inspected repository evidence
  paths. Full-gate counts and exit status above are attributed to the owner's supplied
  summary; runner image/tool versions, skip rationale and raw output remain unavailable.

## R1A-01 focused task plan

This breaks down the existing workstream; it does not change its acceptance criteria.

1. **Kickoff (this change):** record owner decisions, branch, starting baseline and
   evidence gaps; update checklist/counters and append worklog. No engine or oracle code.
2. **Baseline evidence reconciliation:** exact-start-commit full gate and counts are
   recorded from owner-supplied isolated Docker evidence; no gate rerun needed for
   reconciliation. Collect missing CI/platform evidence and separately captured computed
   digest output when available. Preserve the earlier Windows attempt and retained
   paolo-core build environment; local check-environment readiness remains unverified.
3. **Test-side spec oracle (prepared):** `backend/tests/world/` covers T1–T7 and the
   T6 walk matrix as immutable test input, with parsing and deliberate-mutation
   rejection tests. It must never become runtime geometry data.
4. **Harness boundaries (prepared):** docstring-only markers reserve `core/world`
   and `maplegotchi/world_catalog/`; three import-linter contracts and AST checks
   have positive/planted-violation tests. No world behavior or catalog content.
5. **Fixture/property conventions (prepared):** exhaustive mutations with seeded
   stdlib ordering, immutable oracle, explicit-time synthetic core fixtures, isolated
   scratch databases and allowlisted evidence. No new dependency; see harness README.
6. **R1A-01 acceptance:** collect baseline/harness/contract evidence, update docs,
   obtain review and merge under existing policy. R1A-02–R1A-20 remain TODO until
   separately started according to dependencies; no DONE claim from preparation alone.

## Completion gaps and safeguards

Full baseline gate PASS and suite counts are now reconciled from owner-supplied
Docker evidence. Still missing: complete CI/platform evidence, separately captured
computed digest output, review/acceptance of the prepared harness and actual
CI execution of the new contracts. Harness/fixture conventions are now documented. The gate summary supports the pinned assertion only
to the extent it was included in the suite; no individual test transcript or newly
computed digest is claimed. Owner clearance does not waive completion requirements.

ADR-locked values > accepted ADR rules > Final Design Spec > PROPOSED text.
Keep schema v10 and the legacy default view; no production deployment/restart,
database/backup changes, R-01 rework or paolo-core build-environment removal.
Any architecture conflict follows Master Plan §8's stop rule. Test Oracle and
harness are prepared; no World Model or Engine behavior is implemented.

## Test infrastructure evidence (2026-10-10)

- **Oracle:** `backend/tests/world/approved_tables.json` transcribes all columns/rows
  of T1–T7 at approved base `5c6db41`; independently checked against the base spec.
  Counts: 8 / 7 / 28 / 17 / 12 / 7 / 10 rows, 635 data cells, plus 49 walk lengths.
  Frozen tuple models preserve symbolic/provisional fields without implementing rules.
  Parsing is separate from exact approval comparison; a changed snapshot needs review.
- **Fixtures / property decision:** stdlib `Random(101)` orders exhaustive mutations;
  no dependency change. See `backend/tests/world/README.md` for scratch SQLite,
  explicit-time synthetic data and allowlisted exclusive evidence capture. Scratch
  v10 migration test creates no life; production state/config is never used.
- **Contracts:** three added to the existing seven; pure world cannot import catalog
  or implementations, only runtime directly loads catalog, runtime cannot import tests.
  AST checks handle relative imports, world purity, data-only catalog markers and
  literal oracle/spec references. Existing pytest/import-linter CI commands discover
  them; no CI execution result is inferred. Static checks are not an anti-obfuscation sandbox.
- **Environment:** local Windows, Python 3.12.14, pytest 9.1.1, Ruff 0.17.0,
  mypy 2.3.1, import-linter 2.15 / grimp 3.17; existing cached tools, not a fresh
  locked dependency sync. `PYTHONPATH` set to repo `var/r01-deps`, `backend/src`,
  `backend`; interpreter `var/probe-venv/Scripts/python.exe`. Linux-platform mypy is
  static typing on Windows, not Linux runtime evidence.
- **Results:** 48 distinct new tests passed across focused runs (19 oracle, 24
  contracts, 5 fixtures); 2 existing source-boundary tests passed. All 635 cells
  and 49 walk values are deliberately mutated and rejected. Initial new-test run
  was 43 passed / 5 failed in contract harness setup; corrected and affected tests
  rerun successfully. Initial snapshot parsing rejected T7's legitimate repeated
  activity; fixed to composite key. Initial lint/type setup issues were corrected;
  final targeted Ruff lint/format and Linux-platform mypy passed (10 Python files).
  Real import-linter graph: **10 contracts kept / 0 broken**, 125 files / 749 dependencies.
- **Not run:** full gate, simulation or production checks. Prior base gate PASS
  remains owner-supplied Docker evidence; CI and computed-digest gaps remain.
  New package markers have no executable world behavior; schema, legacy view,
  existing simulation pin and dependencies are unchanged. No commit/push/merge.
