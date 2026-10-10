# Maple Room R1a Work Log

**Append-only implementation history of R1a.** Plan: `maple-room-r1a-plan.md`. Live status: `maple-room-r1a-checklist.md`.

## Rules

- **Append-only**, except factual corrections. A correction is marked `Correction (date):` and keeps the original text visible.
- **Never rewrite history** to make a failed attempt disappear.
- **Record failed experiments** when they materially affect design or implementation.
- **Do not record raw chain-of-thought.** Record decisions, evidence and technical reasoning at a concise engineering level.
- **Record only what happened.** No planned or expected results are written as if they occurred.
- Every entry follows the documentation policy (plan §8): plan → implement → test → evidence → checklist → worklog → docs → review → commit.
- An architecture conflict triggers the stop rule (plan §8). The entry records the conflict, the proposed amendment and the owner decision when it arrives.

### BEFORE → CHANGE → EVIDENCE

Every entry states:
- **Before:** the verifiable state before the change;
- **Change:** what was actually changed;
- **Evidence:** the tests, measurements or review results that prove the new state.

Example format (illustrative only; this did **not** happen):

> **Before:**
> - Canonical room walkability mask does not exist.
>
> **Change:**
> - Added walkable mask generation from room regions, doors and blocking masks.
> - Excluded closed rooms.
>
> **Evidence:**
> - expected open walkable tiles reachable
> - zero closed-room tiles reachable
> - validation/tests PASS

## Entry template

```
### <YYYY-MM-DD HH:MM +07> — <R1A-NN[, R1A-NN]> — <short title>

- **Work item(s):**
- **Branch:**
- **Starting commit:**
- **Ending commit:**
- **Goal:**
- **Before:**
- **Changes made:**
- **Files changed:**
- **Tests run:**
- **Evidence / results:**
- **Problems found:**
- **Decisions made:**
- **ADR / spec impact:**
- **Checklist status changes:**
- **Remaining risks:**
- **Next step:**
- **Deployment status:**
```

---

## Entries

### 2026-10-09 — Bootstrap (no R1A item) — R1a planning framework created

- **Work item(s):** none. The planning framework is not an R1A work item.
- **Branch:** `docs/maple-room-r1a-plan`
- **Starting commit:** `dfd5972` (`v0.2-development`)
- **Ending commit:** not yet committed (recorded when the framework is committed after review)
- **Goal:** make the whole R1a path, its dependencies and its acceptance gate visible before any coding starts.
- **Before:**
  - The Room Final Design Spec (`docs/architecture/maple-room-final-design-spec.md`) is merged into `v0.2-development` (`dfd5972`) and owner-approved in principle.
  - ADR-0035..0041 are accepted; the technical spike values are locked (ADR-0041 L1–L22, C1–C8).
  - No R1a plan, checklist or worklog exists.
  - R1a implementation has **not** started and is **not** authorized.
- **Changes made:**
  - Created the master plan with workstreams R1A-01 … R1A-20, the dependency graph and critical path, the risk classification, the R1a/R1b boundary, the work-item policy and the documentation policy.
  - Created the live checklist with all 20 items at TODO.
  - Created this work log.
- **Files changed:**
  - `docs/implementation/maple-room-r1a-plan.md` (new)
  - `docs/implementation/maple-room-r1a-checklist.md` (new)
  - `docs/implementation/maple-room-r1a-worklog.md` (new)
- **Tests run:** none applicable (documentation only); `git diff --check` for whitespace.
- **Evidence / results:** documentation only. No R1a implementation result exists.
- **Problems found:** none.
- **Decisions made:** none beyond the plan's structure. No accepted decision was changed.
- **ADR / spec impact:** none. The Room Final Design Spec, ADR-0035..0041, the art contract, the future architecture and `docs/roadmap/maple-roadmap.md` are unchanged.
- **Checklist status changes:** created; R1A-01 … R1A-20 = TODO.
- **Remaining risks:** see plan §5. The only blocker is R1a authorization (plan §9).
- **Next step:** after this planning framework is approved, write a focused implementation breakdown for **R1A-01** only, once the owner authorizes R1a.
- **Deployment status:** no runtime, schema, service, configuration, script or deployment change. Nothing deployed. Production remains schema v10 with the legacy Room view.

> **Correction (2026-10-09)** — a factual correction to the historical record above, **not** an implementation entry. The bootstrap text is kept unchanged.
> - The bootstrap statement "The only blocker is R1a authorization." is superseded by the reconciled Pre-R1 Gate (plan §9; checklist "Pre-R1 Gate").
> - R1a authorization is currently blocked by three open items:
>   1. OD-01 inside-service boundary probe;
>   2. OD-01 restore test;
>   3. R-01 fixed or explicitly accepted.
> - Stage C authorization and Phase 8 status are already resolved (see the next entry).

### 2026-10-09 — Pre-R1 gate (no R1A item) — Stage C and Phase 8 status clarified; pre-R1 gate made explicit

- **Work item(s):** none (documentation/planning; pre-R1 gate).
- **Branch:** `docs/maple-room-r1a-plan`
- **Starting commit:** `dfd5972` (uncommitted framework on top)
- **Ending commit:** not yet committed
- **Goal:** record the owner's decisions on the OD-01 items and make the pre-R1 gate explicit before R1a.
- **Before:**
  - The repository's last record of Stage C was "NOT authorized" (2026-09-30), although the release `160ed4f…` is installed and active.
  - Phase 8 had no recorded status.
  - The plan left OD-01/R-01 as an "owner decision at authorization time".
- **Changes made:**
  - Recorded the owner decision (2026-10-09): the Stage C install of release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d` is **retroactively authorized**; Stage C stays **open** until the inside-service boundary probe and the restore test pass; M3 is not claimed.
  - Recorded the owner decision (2026-10-09): Phase 8 is **not authorized, not started, deferred** until Stage C is closed; it blocks neither R1a nor R1b (ADR-0009).
  - Added a dated pointer in future-architecture §2.7 and a status note under §22 item 1; the 2026-10-08 statements are kept as history.
  - Plan §9 and §5 and the checklist now classify the three remaining pre-R1 items as **BLOCKER before R1A-01**; the checklist has a Pre-R1 Gate section.
- **Files changed:** `CLAUDE.md`, `docs/architecture.md`, `docs/architecture/maple-future-architecture.md`, `docs/implementation/maple-room-r1a-plan.md`, `docs/implementation/maple-room-r1a-checklist.md`, this work log.
- **Tests run:** none applicable (documentation only); `git diff --check`.
- **Evidence / results:** owner decisions given in conversation on 2026-10-09; no production evidence was collected and no production command was run.
- **Problems found:** none.
- **Decisions made:** owner: Stage C option (a); Phase 8 option (a); known pre-R1 gates are resolved before R1a.
- **ADR / spec impact:** none. No ADR, spec or roadmap change.
- **Checklist status changes:** Pre-R1 Gate added (Stage C authorization RESOLVED, Phase 8 status RESOLVED, boundary probe OPEN, restore test OPEN, R-01 OPEN, R1a authorization BLOCKED). R1A-01 … R1A-20 remain TODO.
- **Remaining risks:** OD-01 now has only two open evidence items (boundary probe, restore test). R-01 remains separately open. The bootstrap entry's "only blocker is R1a authorization" is superseded by this entry.
- **Next step:** resolve the three OPEN pre-R1 items (owner-run probe and restore on paolo-core; R-01 fix or explicit acceptance), then request R1a authorization and write the R1A-01 breakdown.
- **Deployment status:** no production behaviour changed; nothing deployed; no production command run. R1a has not started.

### 2026-10-10 (+07) — Pre-R1 gate (no R1A item) — Boundary probe safety patch prepared

- **Work item(s):** none; pre-R1 OD-01 tooling safety only.
- **Branch:** `pre-r1/boundary-probe-safety`
- **Starting commit:** `f497cf70210b330d93f0bf7d4211e6f3d6f27ee3`; verified against `origin/v0.2-development` before branching.
- **Ending commit:** uncommitted, not pushed (owner instruction).
- **Before:** the existing shell probe used a predictable temporary file with truncating creation and no robust cleanup. The live HTTP checker sent a production interaction POST that could mutate application state if the Origin guard failed. The runbook instructed stopping Maple after a failed probe.
- **Changes made:**
  - Shell entry point delegates to a stdlib Python helper for random exclusive probe-only paths, exact-path cleanup, explicit denial errno handling and mode/marker verification.
  - Parent pins PID/start time/release/mount namespace and checks actual service credentials/capabilities/seccomp and listeners before/after; namespace child clears groups/capabilities. Catchable signals defer registration and permit cleanup; parent waits for child completion.
  - Removed mutating production POST. Live HTTP is restricted to allowlisted GETs without proxies/redirects or response-body output; GET CORS absence explicitly does not prove POST Origin rejection.
  - Updated manual runbook with sudo scope, artifacts, cleanup, PASS/STOP criteria, evidence and limitations. No automated service remediation.
- **Files changed:** `deploy/verify/sandbox_probe.sh`, new `deploy/verify/sandbox_probe.py`, `deploy/verify/check_boundaries.py`, `deploy/install.md`, new `backend/tests/deploy/test_probe_safety.py`, checklist, this worklog.
- **Tests run:** from `backend`, `python -m pytest tests/deploy/test_check_boundaries.py tests/deploy/test_probe_safety.py --basetemp=../var/probe-tests-2 -q --tb=short`: **51 passed, 1 skipped**. The skipped existing test needs POSIX permissions and a non-root user. All tests used isolated local files or mocked HTTP/process calls.
- **Static checks:** targeted Ruff lint and format check passed on the two Python probe files and new test module; targeted strict mypy (`--platform linux --follow-imports=silent`) passed on those three files; `bash -n deploy/verify/sandbox_probe.sh` and `git diff --check` passed. No full suite was run.
- **Problems found:** initial pytest temporary-directory access failed in the Windows sandbox; failed tests were retried with a workspace-local temporary directory. The sentinel test exposed Windows text-mode newline conversion, fixed with binary exclusive creation. No production failures or evidence are implied.
- **Evidence / results:** local tooling validation only; **no production execution yet**. The two existing isolated POST Origin-denial tests remain the documented behavior coverage; they were not rerun because application code is unchanged.
- **Checklist status changes:** tooling safety patch prepared / pending production execution. OD-01 boundary probe **OPEN**, restore **OPEN**, R-01 **OPEN**, R1a authorization **BLOCKED**. R1A-01 through R1A-20 remain TODO; counters unchanged.
- **Remaining risks:** Linux namespace/identity behavior still requires owner-run verification. SIGKILL/power loss can prevent cleanup; exact-path recovery is required. No claim of polkit denial, cgroup network-filter enforcement, live POST rejection, restore success or restart continuity.
- **ADR / spec impact:** none; existing R1a plan not rewritten.
- **Next step:** owner review, then manual execution of `deploy/install.md` section 6 with reviewed scripts; record evidence before considering OD-01 closure.
- **Deployment status:** nothing deployed; no production, service/configuration, database or network-exposure changes. R1a has not started.

### 2026-10-10 (+07) — Pre-R1 gate (no R1A item) — Final boundary-probe safety review

- **Branch / baseline:** `pre-r1/boundary-probe-safety`, based on `f497cf70210b330d93f0bf7d4211e6f3d6f27ee3`.
- **Before:** prepared tooling had passed isolated validation, but the ordinary checker still emitted snapshot identity fields and cleanup did not detect replacement of a created file.
- **Change:** removed ordinary identity-field output; identity extraction is limited to explicit record/compare work. Cleanup now verifies device/inode identity and rejects replacement files/symlinks. Added two focused regression tests and aligned the runbook.
- **Evidence:** final targeted `test_check_boundaries.py` + `test_probe_safety.py` run: **53 passed, 1 skipped** (existing POSIX/non-root permissions test on Windows). Targeted Ruff lint/format, strict mypy with Linux platform, and shell syntax checks passed. No full suite or live production probe was run.
- **Review verdict:** clean after the two fixes. Scope is exactly the seven probe/tooling, test, runbook, checklist and worklog files named above; no application feature, schema, migration, service/configuration or spike changes.
- **Commit authorization:** owner now authorizes committing as `pre-r1: harden boundary probe safety` and pushing this branch only, superseding the earlier no-commit/no-push instruction. This entry is included in that commit; its SHA and push outcome are reported after Git confirms them. No merge authorized.
- **Status:** tooling **prepared / pending production execution**. Boundary probe OD-01 **OPEN**; restore **OPEN**; R-01 **OPEN**; all R1A-01 through R1A-20 **TODO**. No production commands run; R1a has not started.
- **Remaining limits / next step:** owner review and manual Linux execution per runbook; SIGKILL/power-loss cleanup recovery remains possible. No polkit-denial, cgroup-filter enforcement or live POST Origin-denial claim. Record accepted production evidence before closing OD-01.

### 2026-10-10 (+07) — Pre-R1 gate (no R1A item) — Fix service group false FAIL

- **Branch / baseline:** `pre-r1/fix-boundary-probe-groups`, from `7bddd4e4e79234ffde28ac2483b833e362f7ade4`.
- **Before:** owner reports a manual production probe attempt on paolo-core: PID `1395361`, UID `995` (`maple-svc`), primary GID `979` (`maple-svc`), `Groups: 979`. This was primary-group membership only. The probe falsely failed because its extra service check required an empty Groups field, contradicting `check_boundaries.evaluate_process`.
- **Change:** removed the extra service-only empty-groups requirement. Reuse the existing `evaluate_process` rule: group IDs must be a subset of the account primary GID (empty also remains valid under that existing rule). Any other GID fails. The namespace helper still strictly requires an empty group list after `--clear-groups`; no other security checks changed.
- **Evidence:** targeted group-validation, helper-group and service-identity-change tests: **11 passed, 19 deselected**. Covers observed primary-only membership, empty service membership under the existing validator, mixed primary/extra group and unrelated privileged group rejection, plus strict empty helper groups. Targeted Ruff lint/format and strict mypy (`--platform linux --follow-imports=silent`) passed on the changed helper/test files. No full suite run.
- **Status:** production probe attempted by owner; false FAIL discovered; probe tooling bug identified and fixed. OD-01 boundary probe remains **OPEN pending rerun**. Restore test and R-01 untouched; all R1A-01 through R1A-20 remain TODO. R1a has not started.
- **Production / next step:** no production commands run by this agent and no production changes. Commit/push this fix branch as authorized; owner rerun and accepted evidence are still required before OD-01 closure.

### 2026-10-10 (+07) — Pre-R1 gate (no R1A item) — OD-01 boundary probe PASS / CLOSED

- **Branch / baseline:** `v0.2-development` at `a3edcf10dc3584bb2322a8ca5a5850458338e187`.
- **Before:** boundary probe OPEN pending owner rerun after the primary-group false FAIL fix.
- **Change:** record the owner's successful manual production evidence and close the **boundary-probe item only**. The separate OD-01 restore item remains OPEN; historical attempts and failures above are preserved.
- **Evidence source:** owner-supplied paolo-core results, recorded 2026-10-10. Exact execution timestamp and script hashes were not supplied; this is not an agent-executed or independently repeated probe.
- **Expected deployed release:** `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`.
- **Checker:** `check_boundaries.py`: **59 checks, 0 failed, 0 warnings, 1 OWNER_CHECK**. Owner resolved that check: `/etc/polkit-1/rules.d/50-maplegotchi-deny.rules` was `root:root 644`, matching expected metadata.
- **Sandbox result:** `sandbox_probe: PASS`. Verified correct `maple-svc` identity, no unexpected supplementary groups, empty capabilities, `NoNewPrivs=1`, `Seccomp=2`, port 8470 loopback-only, protected filesystem creation attempts denied with `EROFS`, successful `/data/maple` marker round-trip and exact-path cleanup, and stable service PID/start time/release.
- **Exposure:** both `tailscale serve status` and `tailscale funnel status` reported `https://paolo-core.tail4bfe27.ts.net (tailnet only)`, with `/` proxying to `http://127.0.0.1:8470`. Interpretation: tailnet-only exposure, no public Funnel exposure.
- **Limitations:** polkit rule ownership/mode is metadata evidence, **not active polkit-denial proof**. No cgroup network-filter enforcement claim. Safe live GET/CORS-header checks are **not live POST Origin-denial proof**.
- **Validation:** documentation/static checks only: scoped diff review, unchanged restore/R-01 rows and R1a TODO statuses, append-only worklog verification, and `git diff --check`. No implementation tests required for this documentation-only update.
- **Final Pre-R1 status:** boundary probe **PASS / CLOSED** (`RESOLVED` in checklist vocabulary); restore test **OPEN**; R-01 **OPEN**; R1a authorization **BLOCKED / not given**. Stage C remains open, M3 not claimed. All R1A-01 through R1A-20 remain TODO; R1a has NOT started.
- **Production / next step:** no production commands run by this agent, no implementation/configuration/schema changes, no restore or R-01 work. Commit/push this evidence update as authorized; remaining gates must be resolved before R1a authorization.

### 2026-10-10 (+07) — Pre-R1 gate (no R1A item) — OD-01 Restore Test PASS / CLOSED

- **Branch / baseline:** `v0.2-development` at `6a97fbe6766e65c6e2d58476534efeaebc826e22`.
- **Before:** restore OPEN; owner execution completed, documentation review pending.
- **Change / acceptance assessment:** close the isolated Restore Test only. Plan §9 and `deploy/install.md` Stage C Backup criterion require a restic restore whose `maple.db` opens and passes `integrity_check`. Owner evidence satisfies these requirements without changing them. Original identity provenance and production replacement/restart are not requirements of this isolated restore gate.
- **Evidence source:** owner-supplied completed execution results, reviewed and recorded 2026-10-10; not independently rerun by this agent. Both snapshots are in `/data/backups/paolo-core-restic`; metadata and exact archived paths verified by owner.
- **Primary restore (October 10):** snapshot `6010566b116a7322d15769bfe2ee5795ebc996e480f16f515a5a6c285487c71e`, archived `/data/backups/paolo-core-staging/run.Sc4vUNMi/maple.db`. Isolated restore PASS; restic `--verify` 1/1 files PASS; 5,627,904 bytes, regular file, mode 0600, one hard link; SQLite `integrity_check=ok`, schema v10, journal DELETE, application ID verifier PASS, WAL/SHM absent. Installed helper SHA-256 matched repository helper (digest not recorded here).
- **Historical restore (October 1 snapshot):** snapshot `d3e3372f0df5f023e51a154dafea957a49255efa21b16b4bf87c1948de7348d9`, archived `/data/backups/paolo-core-staging/run.x9WM3dbv/maple.db`. Isolated restore PASS; restic `--verify` 1/1 files PASS; 581,632 bytes; SQLite integrity ok, journal DELETE, helper exit code 0. Historical schema version was not supplied.
- **Identity comparison:** owner performed a read-only, equality-only comparison of `name`, `born_at`, and `life_seed` between the two isolated restored databases: **IDENTITY_EQUAL — PASS**. No identity values, seeds or fingerprints recorded.
- **Cleanup:** initial preflight failed because restic preserved UID 1000 on two parent directories; this was a cleanup metadata mismatch, not a database-integrity failure. Revised metadata-aware preflight passed before cleanup. `LATEST_CLEANUP_PREFLIGHT`, `HISTORICAL_CLEANUP_PREFLIGHT`, `CLEANUP_PREFLIGHT`, `LATEST_CLEANUP`, `HISTORICAL_CLEANUP`, and `CLEANUP`: all PASS. Exact-path unlink and empty-directory rmdir only; no recursive or wildcard deletion. Both isolated restore roots confirmed absent by the cleanup script.
- **Limitations:** original Maple identity provenance was not independently established; original birth/creation date was not independently authenticated. Equality proves matching identity between the October 1 and October 10 archives, not uninterrupted continuity. Both snapshots share one restic repository trust domain. Production database replacement and service restart/recovery continuity were NOT tested. No production database mutation occurred during the owner restore exercises. Boundary-probe limitations remain: no active polkit-denial, cgroup network-filter enforcement, or live POST Origin-denial proof.
- **Validation:** documentation-only scope and sensitive-information diff review; static status/evidence checks, unchanged R-01 and all 20 R1A TODO items, append-only worklog check, and `git diff --check`. No implementation tests or production commands required.
- **Final status:** boundary probe and Restore Test **PASS / CLOSED**; OD-01 pre-R1 evidence satisfied. R-01 **OPEN**; Pre-R1 Gate **BLOCKED**, not CLEAR; R1a authorization not given and R1a NOT STARTED. R1A-01 through R1A-20 remain TODO. No M3/stable-release claim or Phase 8 authorization is made by this restore closure.

### 2026-10-10 (+07) — Pre-R1 R-01 implementation prepared / pending review

- **Branch / baseline:** `fix/r01-journal-lock-isolation` from clean, fetched/synchronized `v0.2-development` at `629175befce17a8df9aee17a240e1fbbfcd9ce05`.
- **Authorization:** owner approved the separate implementation patch, outside-lock lifecycle and bounded-wait limitation. Deployment requires separate authorization. This is not an R1A work item.
- **Before:** external journal `/generate` ran inside the writer lock on decision, arrival, heartbeat and interaction paths; no client response cap or explicit redirect/proxy policy. R-01 OPEN; OD-01 boundary and Restore Test already PASS / CLOSED.
- **Change:** prepare immutable context/candidate under lock; one managed daemon composes outside the lock/transaction; revalidate lifecycle/revision, then atomically persist the transition, observations, accepted journal entries and reflection markers. Stale operations rebuild against current state without another external call; no stale RNG outcome or draft is reused. RuleBrain keeps its synchronous deterministic path.
- **Transport / worker:** 30 s monotonic caller deadline includes startup, request preparation, I/O and parsing; connect at most 2 s. Streamed HTTP body capped at 64 KiB before parsing; redirects and environment proxies refused, no automatic retries. Compressed responses refused to avoid decompression expansion before the cap. Timeout retains the single request slot until transport cleanup; busy attempts produce no wording. Constructor/start failure releases the reservation.
- **Shutdown:** shared admission gate tracks nested service/runtime operations through final publication/response reads. Shutdown closes admission, invalidates generations, wakes journal waiters, stops scheduling and drains callers before storage closure. Executing commits finish; uncommitted preparations abort. Writer-lock waits/draining during app teardown run off the event loop. App lifespan now closes service storage; post-teardown reads raise `RuntimeClosedError`; close is idempotent.
- **Evidence — targeted:** `python -m pytest tests/runtime/test_journal_isolation.py tests/runtime/test_external_brain.py tests/runtime/test_journal_runtime.py`: **61 passed**. Covers all five journal-producing entry paths, concurrent progress/no lost or duplicate updates, stale revalidation, timeout/busy/late output, slot cleanup/start failures, exact 64-KiB boundary, trickle/prompt/parsing deadlines, redirect/proxy policy, malformed/invalid drafts, ordering/markers/retries, insertion and actual COMMIT rollback, and shutdown before/after commit.
- **Evidence — broader:** shared transition/shutdown behavior justified `python -m pytest tests/runtime tests/api tests/security` with the three targeted files excluded: **317 passed**, including RuleBrain/restart continuity, service/API lifecycle and forbidden-API/purity/security regressions. No full repository suite. Final total: **378 tests passed**.
- **Static validation:** Ruff lint/format checks on changed Python files; strict `python -m mypy --platform linux`: **178 files, no issues**; import-linter **7 contracts kept, 0 broken**; documentation/status/scope review and `git diff --check`. Linux typing is required for unchanged Linux-only probe APIs; a default Windows mypy run reported those existing platform errors. Local Python 3.12 tests used fake transports/providers and temporary databases; owner-restricted Windows fixture directories required local elevated test execution. No production access.
- **Limits / compatibility:** bounded external-journal caller waiting is subject to scheduling and other runtime operations; no forced blocked-daemon termination or bounded whole-process shutdown. A stuck request can keep wording busy until cleanup/restart. No durable queue or eventual-wording guarantee; event-only opportunities may be lost just as with existing failed wording. Concurrent operations may overtake pending work; stale candidates re-evaluate current eligibility/cooldowns. API teardown now rejects subsequent reads. No raw prompts/responses, credentials, identity values, seeds or fingerprints are logged or recorded.
- **Rollback:** schema/stored formats remain v10; same-schema code rollback preserves the database and discards memory-only attempts, restoring the older release's known limitation. No migration, storage/backup-tooling, service/configuration or production changes. Deployment/rollback not executed or authorized by this patch.
- **Final gate status:** implementation and tests prepared for review; **R-01 remains OPEN**, Pre-R1 Gate **BLOCKED**, R1a authorization not given and R1a NOT STARTED. All R1A-01 through R1A-20 remain TODO. Boundary probe and Restore Test stay PASS / CLOSED. No merge/deployment performed.

### 2026-10-10 (+07) — R-01 review finding: shutdown commit-admission race corrected

- **Before:** independent review of `3c90e783f2750aab5ae3e10d181d02234dae20b6` requested changes for one MEDIUM defect: admission could close during preparation/draft validation, after the running-state check but before persistence. The writer lock alone did not serialize shutdown admission with transaction admission.
- **Change:** every runtime persistence call now obtains an irrevocable commit permit under the same condition lock as shutdown admission closure. Shutdown first denies persistence; permit first allows that transaction to finish, even if shutdown arrives before SQLite begins. Existing operation admission drains through persistence, memory adoption, publication and final reads before storage closes. The gate lock is released before persistence and never held while acquiring the writer lock. Revision/generation revalidation, unlocked external composition, triggers/markers/retries and schema v10 are unchanged.
- **Deterministic evidence:** event barriers cover RuleBrain preparation and external validation races, conversation receive/reply and stale-audit admission, both arbitration outcomes, service caller draining/storage lifetime, external Director proposals overtaken during journal composition, active Director/Replier shutdown, and sub-4096-byte trickling with a bounded caller deadline and retained worker slot. Temporary databases are reopened to verify persisted state and atomic journal/marker results. No timing sleeps or real provider requests were added.
- **Validation:** targeted journal/admission/HTTP tests: **72 passed**. Final full runtime/API/security regression suite: **389 passed**, including those targeted cases; counts overlap and are not additive. No test failures. Initial Linux mypy checks found test-only typing issues, corrected before the final run. Final Ruff lint and format checks on all four changed Python files passed; Linux-platform strict mypy: **179 files, no issues**; import-linter: **7 contracts kept, 0 broken**; security/forbidden-API tests included in the regression suite. Documentation/status/scope review and `git diff --check` passed. No full repository suite or production commands.
- **Limits / status:** no new deferred review coverage gaps; existing blocked-daemon, whole-process shutdown, event-only wording and no-durable-queue limitations remain. R-01 **OPEN**, pending another independent review; Pre-R1 **BLOCKED**; OD-01 boundary and Restore Test stay PASS / CLOSED. R1a NOT STARTED; all R1A-01 through R1A-20 remain TODO. No schema, backup, service/configuration, production, merge or deployment change.

### 2026-10-10 (+07) — R-01 owner acceptance / repository-level closure

- **Owner decision:** accepted implementation `3c90e783f2750aab5ae3e10d181d02234dae20b6` and shutdown fix `6f3239ff8f66c60e781d4a50dba9fbaef1f4e951`; explicitly waived another independent review and authorized merging `fix/r01-journal-lock-isolation` into `v0.2-development`. This supersedes the pending-review status above.
- **Closure criterion:** plan §9 / architecture §22 require R-01 fixed or explicitly accepted. Owner acceptance satisfies the repository-level criterion: **R-01 PASS / CLOSED**. Closure does not claim production remediation or new production verification.
- **Accepted evidence:** 389 runtime/API/security tests passed; Ruff lint/format passed; Linux mypy 179 files clean; seven import contracts kept; all seven persistence sites protected by commit admission; no schema migration. These implementation checks were not repeated for the merge. Merge preparation fetched origin, confirmed the clean target at `629175befce17a8df9aee17a240e1fbbfcd9ce05`, both accepted commits and a conflict-free no-fast-forward merge. Documentation/static status checks and `git diff --check` passed.
- **Preserved limits:** bounded external-journal caller waiting does not force daemon termination or guarantee bounded whole-process shutdown/eventual wording. No durable queue. Schema remains v10. Production still runs the older release with the original writer-lock limitation; deployment and rollback execution require separate authorization. No production, database, backup, service/configuration or R1a changes.
- **Gate status:** OD-01 boundary probe and Restore Test remain PASS / CLOSED; R-01 PASS / CLOSED at repository level. **Pre-R1 Gate remains BLOCKED**, not CLEAR: gate clearance is a separate owner decision. R1a authorization NOT GIVEN, R1a NOT STARTED; all R1A-01 through R1A-20 remain TODO.

### 2026-10-10 (+07) — R1A-01 — Owner-authorized kickoff and baseline preparation

- **Work item(s):** R1A-01 only; R1A-02–R1A-20 remain TODO / NOT STARTED.
- **Branch / starting commit:** `codex/r1a-01-baseline` from `5c6db41c0139e1da6a2178b36d838e4da57074b1`.
- **Ending commit:** not committed; kickoff documentation prepared for review.
- **Goal:** record the approved starting point, focused R1A-01 breakdown and evidence gaps; no World Model, Test Oracle or Engine implementation in this step.
- **Before:** clean Windows checkout on `v0.2-development`; origin fetch/push URL verified as `https://github.com/payola469/Maplegotchi.git`. R-01 merged/repository-level CLOSED; docs still recorded deployment/gate clearance/authorization as pending. Full exact-baseline release-gate evidence missing: earlier Git Bash startup failed with `NtCreateDirectoryObject` / `0xC0000022`, before any check stage; uv unavailable on PATH.
- **Changes made:** recorded owner decisions (2026-10-10): Pre-R1 clearance APPROVED / CLEAR; R1a preparation and implementation AUTHORIZED; R-01 deployed to paolo-core and HTTP Health PASS; R1A-01 authorized to start. Created development branch from the approved commit without moving `v0.2-development`. Added baseline evidence/focused task plan; updated current status pointers while preserving historical records and security/restore limitations.
- **Files changed:** `CLAUDE.md`; `docs/implementation/maple-room-r1a-{plan,checklist,worklog}.md`; new `docs/implementation/maple-room-r1a-01-baseline.md`; `docs/deployment.md`; `docs/security-model.md`; `docs/journal.md`; `docs/architecture/maple-future-architecture.md`.
- **Tests run:** documentation/static checks only: baseline/branch and docs-only scope; checklist counters and unchanged R1A-02–R1A-20 rows/details; worklog append-only; local document links and `git diff --check`. No implementation tests or full release gate rerun for this documentation-only kickoff.
- **Evidence / results:** exact local HEAD, target and origin-tracking ref equal the approved commit; initial tree clean; no fresh fetch/server-sync claim. Historical R-01 evidence: 389 runtime/API/security tests, Ruff, Linux mypy 179 files, seven import contracts and seven protected persistence sites (not newly run or full baseline evidence). Pinned simulation expectation and spec T6 walk matrix located, not recomputed/validated. Owner production confirmation is recorded as supplied, not agent verification.
- **Problems found:** complete exact-baseline release-gate/CI evidence and full test counts remain unavailable. Exact deployed SHA, deployment time and detailed acceptance transcript were not supplied; no inference from the development baseline. Harness/oracle/purity-contract/fixture outputs remain unimplemented.
- **Decisions made:** apply explicit owner authorization; start only R1A-01 preparation. Gate clearance does not waive baseline or CI completion criteria. No property-testing dependency choice yet.
- **ADR / spec impact:** none; precedence and stop rule preserved. No accepted geometry, route table or locked value changed.
- **Checklist status changes:** Pre-R1 clearance and R1a authorization RESOLVED; R1A-01 TODO → IN PROGRESS (baseline preparation only); counters 20 total / 19 TODO / 1 IN PROGRESS / 0 other statuses.
- **Remaining risks:** incomplete baseline check environment/evidence; historical digest is an expected value only. Existing R-01 worker/shutdown/eventual-wording and OD-01/restore evidence limitations remain.
- **Next step:** establish local baseline verification tooling and collect exact-start-commit checks/CI/test counts and computed simulation evidence, then implement the existing R1A-01 test-harness scope in a later step. Stop here before oracle/world/engine work.
- **Deployment status:** owner reports R-01 production deployment completed and HTTP Health PASS. No production commands, deployment/restart, database/schema/config/default-view changes or backup operations performed in this kickoff; retained paolo-core build environment untouched.

### 2026-10-10 (+07) — R1A-01 — Baseline evidence reconciliation

- **Branch / baseline:** `codex/r1a-01-baseline`; starting commit `5c6db41c0139e1da6a2178b36d838e4da57074b1`; kickoff documentation committed as `2a1c85a011b183e2b9185853538a01fa22e3394e`.
- **Before:** kickoff recorded only the failed Windows gate startup and historical R-01 subset; full baseline evidence was then unavailable. This entry supplements, rather than rewrites, that history.
- **Change / evidence source:** reconciled the previously verified full `scripts/check.sh` result supplied by owner for exact base `5c6db41`: **PASS, exit code 0**, in isolated Docker on paolo-core. Backend **1,510 passed / 1 skipped**; Discord **22 passed**; Brain **28 passed**; frontend **204 passed**. Ruff, mypy, import contracts, ShellCheck and frontend build passed. No gate rerun, production access or independent raw-log verification in this reconciliation. The earlier 389-test R-01 result is overlapping subset evidence, not additive.
- **CI evidence:** fresh read-only GitHub combined-status lookup returned `statuses: []`; commit workflow lookup returned `workflow_runs: []`. The latter is limited to PR-triggered runs / first page. These responses do not prove absence of all CI runs. `.github/workflows/ci.yml` defines backend Ubuntu/Windows and frontend Ubuntu jobs; no successful run output is available here. Docker PASS is not Windows CI proof.
- **Digest / routes / fixtures:** expected 30-day digest `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917` is pinned in `backend/tests/core/test_simulation.py::test_thirty_day_digest_is_pinned`; not newly computed or separately captured. Approved matrix is Final Design Spec §T6, walk-length table (lines 644–656), with T4 points and T7 legacy mapping. Existing synthetic core simulation/state and frontend DTO fixtures are identified in the baseline document; no private identity fields or seed values recorded, and no oracle implemented.
- **Remaining gaps:** complete exact-base CI/platform results, separately captured computed digest output, raw gate transcript/container versions/skip rationale, usable oracle/harness, enforced contracts and fixture/property conventions. Windows local check readiness remains unverified. Missing raw details do not erase the owner-supplied gate PASS.
- **Files / validation:** baseline document and current plan/checklist evidence pointers updated; worklog appended only. Documentation consistency checks and `git diff --check` passed. No implementation tests, simulation execution or full release gate run; documentation/evidence-only scope.
- **Status / safeguards:** R1A-01 remains IN PROGRESS; R1A-02–R1A-20 TODO. Pre-R1 owner clearance and R1a authorization unchanged. No application, dependency, test, schema, database, production or retained build-environment change; no commit, push or merge. Stop before Test Oracle implementation.

### 2026-10-10 (+07) — R1A-01 — Spec Oracle and test harness prepared

- **Before / branch:** `codex/r1a-01-baseline`, HEAD `2a1c85a011b183e2b9185853538a01fa22e3394e`, approved starting base `5c6db41`. Four existing uncommitted evidence-reconciliation docs preserved. R1A-01 IN PROGRESS; no oracle/harness yet.
- **Change:** immutable test-only Oracle parses approved T1–T7 plus walk matrix and compares all cells with a reviewed test snapshot. Docstring-only `core/world` and `world_catalog` markers allow enforceable package contracts without world behavior. Added three import-linter contracts, AST checks, exclusive scratch SQLite fixtures and allowlisted evidence capture. Layout/conventions documented; no geometry, catalog content, renderer or pathfinding implementation.
- **Decision / boundaries:** reproducible property approach is exhaustive mutations in stdlib `Random(101)` ordering, under Python 3.12; no dependency added. ADR-0036 runtime loads catalog and passes frozen values to core; core never loads catalog files. Oracle is outside wheel package inputs and runtime test imports/literal spec references are rejected. Static AST/import checks prevent accidental coupling, not deliberate obfuscation. Existing CI discovery enforces new checks; CI has not been executed here.
- **Environment / invocation:** Windows, Python 3.12.14; existing `var/probe-venv/Scripts/python.exe`, `PYTHONPATH=C:/GitHub/Maplegotchi/var/r01-deps;C:/GitHub/Maplegotchi/backend/src;C:/GitHub/Maplegotchi/backend`. Commands below run from `backend` using `../var/probe-venv/Scripts/python.exe` as `python`; this is cached-tool execution, not a new locked sync. pytest 9.1.1, Ruff 0.17.0, mypy 2.3.1, import-linter 2.15, grimp 3.17.
- **Initial attempts preserved:** snapshot parser initially rejected intentional repeated T7 activity; corrected to `(activity, new_points)` key before tests. First `python -m pytest tests/world -q --basetemp=../var/r1a01-harness-a`: **43 passed / 5 failed** (relative-import fixture and import-linter raw-option/graph setup errors). Corrected only harness setup. Initial Ruff invocation from repo root misapplied relative test ignores; subsequent checks ran from backend. Initial targeted mypy found malformed ignore comments, a list annotation and incorrect graph-copy API; corrected.
- **Final focused tests:** `python -m pytest tests/world/test_contracts.py -q --basetemp=../var/r1a01-contracts-b`: **24 passed**. After seeded corpus integration, `python -m pytest tests/world/test_oracle.py -q --basetemp=../var/r1a01-oracle-d`: **19 passed**. After strengthening the pre-open config decoy, `python -m pytest tests/world/test_harness.py -q --basetemp=../var/r1a01-fixtures-e`: **5 passed**. **48 distinct new tests passed**, not summed with initial/rerun counts. No unnecessary rerun of unchanged passing tests.
- **Existing source guards:** `python -m pytest tests/security/test_forbidden_apis.py::test_source_tree_has_no_forbidden_apis tests/security/test_forbidden_apis.py::test_core_imports_only_allowlisted_modules -q --basetemp=../var/r1a01-security-c`: **2 passed**.
- **Static commands / results:** `python -m ruff check tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog`; `python -m ruff format --check tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog`; `python -m mypy --platform linux --follow-imports=silent tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog`: **PASS**, mypy 10 files. After final fixture-only changes, the same Ruff lint/format and mypy commands limited to `tests/world/conftest.py tests/world/test_harness.py`: **PASS**, mypy 2 files. `python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports(config_filename='pyproject.toml', no_cache=True, no_logo=True))"`: **10 kept / 0 broken**, including existing seven. Linux-platform typing is not Linux test execution.
- **Oracle / negative evidence:** independent CSV transcription comparison against `git show 5c6db41:docs/architecture/maple-room-final-design-spec.md` passed; rows 8/7/28/17/12/7/10. All 635 CSV data cells and 49 walk lengths mutated/rejected; malformed/duplicate/missing tables, changed routes and duplicate keys rejected. Actual configured import-linter rules tested with clean and planted direct/indirect edges; AST tests include relative imports, clock/random/I/O, third-party geometry, test data and catalog Python behavior. Scratch DB v10/integrity/empty life table, distinct roots, RNG isolation and no evidence overwrite verified.
- **Documentation / status checks:** `git diff --check`, append-only history, documentation consistency, approved spec/pinned simulation/migrations unchanged and R1A-02–R1A-20 unchanged checks passed. Updated baseline, checklist, plan status pointer, CLAUDE layout/boundaries and architecture notes. No acceptance criteria changed.
- **Remaining / status:** R1A-01 remains IN PROGRESS pending exact-base CI/platform evidence, separately captured computed digest output and harness review/acceptance. Raw baseline gate details remain unavailable; prior owner-supplied isolated Docker PASS retained. R1A-02–R1A-20 TODO; do not begin R1A-02. No full gate or simulation rerun, runtime behavior/schema/production/default-view/dependency change, production access, commit, push or merge. Work remains uncommitted for review.

### 2026-10-10 (+07) — R1A-01 — STEP 69 acceptance evidence update

- **Before:** current pointers still described CI/computed simulation evidence as missing; earlier entries accurately describe their original preparation stages and remain unchanged.
- **Evidence supplied and verified by owner:** approved base `5c6db41c0139e1da6a2178b36d838e4da57074b1`; previously verified isolated Docker baseline release gate **PASS**. 30-day simulation: **8,640 ticks**, computed digest `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`, matching the unchanged pin. Oracle/Harness: **48 new focused tests passed**, **635 cells + 49 walk-matrix values**; import contracts **10 kept / 0 broken**.
- **PR evidence:** [PR #1](https://github.com/payola469/Maplegotchi/pull/1), HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`, [GitHub Actions run 38062574000](https://github.com/payola469/Maplegotchi/actions/runs/38062574000): **Backend Ubuntu PASS, Backend Windows PASS, Frontend PASS, ShellCheck PASS**. The passing PR run is **not** a separate CI execution of original base `5c6db41c0139e1da6a2178b36d838e4da57074b1`. Historical Windows startup failure, failed PR attempts and earlier empty CI lookups retain their original context; later PASS supersedes current missing-evidence statements without erasing history.
- **Change / validation:** reconciled baseline, checklist, plan and current project status pointers; documentation inspection only. Reused supplied evidence; no tests, simulation, release gate or production access. Existing focused CI-fix evidence remains applicable; no runtime/test/Oracle/Harness/schema/dependency changes in this step.
- **Master Plan criteria / remaining:** baseline recorded; harness usability supported by 48 focused tests and documented conventions; contracts enforced by passing backend CI; no world runtime behavior or schema change. API schema initialization now occurs before requests, with preserved API contracts; probe and installer security behavior is retained. Owner review/acceptance and review/merge under existing policy remain pending. Separate start-commit GitHub CI is unverified: owner acknowledgement of this provenance limitation or separate evidence is required before closure. Raw Docker transcript/container versions/skip rationale remain unavailable supporting detail, without invalidating the previously verified Docker PASS.
- **Status / next step:** **R1A-01 IN PROGRESS / PENDING OWNER ACCEPTANCE**, ready for owner acceptance review with the base-CI limitation explicit. **R1A-02–R1A-20 TODO**; counters remain 20 total / 19 TODO / 1 IN PROGRESS / 0 DONE. Await owner decision; no commit, push, merge, deployment, paolo-core access or R1A-02 work. Historical records are preserved.

### 2026-10-10 (+07) — R1A-01 — STEP 71 Owner Acceptance

- **Before:** STEP 69 documentation-only evidence changes pending on `codex/r1a-01-baseline`, HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`; freshly fetched origin aligned (0 ahead / 0 behind). Only the nine expected Markdown files changed; no staged/unrelated changes. Active tree: `/Users/paolo_cu/GitHub Desktop/Maplegotchi`.
- **Owner decision:** owner explicitly **APPROVES R1A-01 acceptance on 2026-10-10**. Owner acknowledges successful GitHub CI run `38062574000` validates PR HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`, not a separate CI execution of original baseline `5c6db41c0139e1da6a2178b36d838e4da57074b1`; baseline Docker Release Gate PASS is recorded, but complete raw baseline gate details are unavailable. Both limitations are explicitly accepted; no new execution or provenance claim.
- **Change / evidence:** current checklist, baseline, Master Plan and current-status pointers record **OWNER ACCEPTED / MERGE PENDING**. Existing evidence from STEP 69 retained: 8,640 ticks and computed pinned digest; 48 Oracle/Harness tests, 635 cells, 49 walk values, 10 import contracts kept / 0 broken, four passing PR CI jobs. Prior worklog entries preserved verbatim.
- **Validation / boundaries:** documentation consistency checks and `git diff --check` only. No runtime code, tests, Oracle, Harness, schema, dependencies, deployment configuration or Production default-view changes. No tests/full gate rerun, paolo-core access, deployment/restart, merge or force-push.
- **Completion state:** **R1A-01 OWNER ACCEPTED / MERGE PENDING** (checklist REVIEW substate), not DONE; repository integration remains incomplete until PR #1 is successfully merged. Counters: 20 total / 19 TODO / 0 IN PROGRESS / 1 REVIEW / 0 DONE. **R1A-02–R1A-20 TODO / NOT STARTED**. This step is authorized to commit/push documentation normally; merge is a separate action and is not performed here.

### 2026-10-10 (+07) — R1A-01 — Completion reconciliation (STEP 78)

- **Confirmed state:** PR #1 merged into `v0.2-development` at `a754efc9cd35f66e15efb8707dc9b4066d5ab54d`. Merge was verified in STEP 76 via GitHub; STEP 77 created a separate clean worktree from that remote baseline, and STEP 78 verified its branch/HEAD/cleanliness before editing. No merge is performed by this update.
- **Status:** **R1A-01 DONE / OWNER ACCEPTED / MERGED**. Owner acceptance dated 2026-10-10 remains unchanged. Both acknowledged limitations remain: CI run `38062574000` validates PR HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`, not a separate CI run on original base `5c6db41c0139e1da6a2178b36d838e4da57074b1`; complete raw baseline Docker Release Gate details are unavailable despite recorded PASS. Historical evidence and prior worklog entries preserved.
- **Changes:** reconciled checklist, baseline, Master Plan and current-status pointers. Counters: **20 total / 19 TODO / 1 DONE**, all other status counts zero. No implementation, production action or new test/gate evidence.

### 2026-10-10 (+07) — R1A-02 — Detailed implementation plan prepared (STEP 78)

- **Before:** clean `/Users/paolo_cu/GitHub Desktop/Maplegotchi-r1a-02-world-model`, branch `feat/r1a-02-world-model`, HEAD `a754efc9cd35f66e15efb8707dc9b4066d5ab54d`. Original checkout and divergent local `v0.2-development` left untouched.
- **Source review / plan:** read CLAUDE, Master Plan (R1A-02, §§4/7/8), Final Design Spec, ADR-0035/0036/0041 and existing Oracle/Harness/contracts. Added `maple-room-r1a-02-world-model.md`: pure values/boundaries, T1/T2 geometry, L8 structure, passages/topology, vocabulary/feet, lighting partition, S1–S4/S7 band-side/S12 tests, incremental checkpoints and acceptance targets. Proposed internal modules/data placement are explicitly proposals; no geometry is invented or accepted source changed.
- **Conflict reported:** ADR-0036 §3 and spec S15 require disjoint desk capabilities, but T3/T4 give both desks `seat` (T6 also requires it for writing). Record owner clarification before later catalog/capability validation; no silent reinterpretation, Oracle change or later workstream started. No unresolved R1A-02 geometry conflict found; implementation authorization remains required.
- **Checks / safeguards:** documentation consistency, internal file links, counters and `git diff --check` only; no tests or Full Release Gate. Markdown changes only; runtime/source/tests/Oracle/Harness/snapshot/schema/API/renderer/deployment configuration unchanged. Worklog appended only. No production access, commit/push/merge or branch switch.
- **Status / next:** **R1A-02 TODO / PLAN PREPARED**, ready for owner review and separate implementation authorization. **R1A-03–R1A-20 TODO**. Counters remain 20 total / 19 TODO / 1 DONE. Stop after planning.

### 2026-10-10 (+07) — R1A-02 — Checkpoint 1 implemented (STEP 81)

- **Authorization / baseline:** owner explicitly authorizes Checkpoint 1 only. Worktree `/Users/paolo_cu/GitHub Desktop/Maplegotchi-r1a-02-world-model`, branch `feat/r1a-02-world-model`, HEAD `a754efc9cd35f66e15efb8707dc9b4066d5ab54d`; prepared STEP 78 documentation retained. No branch switch or original-checkout change.
- **Implementation:** adopted proposed coordinates/model/directions module boundaries for immutable, slotted Tile/Rect/Region, RegionKind/RegionStatus, CharacterDirection/ObjectOrientation and explicit bidirectional legacy Facing conversion. Strict integer/grid/extent validation; half-open rectangles; T=16, grid 44×26; one shared `FEET_IN_TILE = (T // 2, (13 * T) // 16) = (8, 13)` and pure tile-to-feet mapping. No production wiring; Door/House and all structural/layout behavior remain deferred.
- **Focused tests:** from this worktree's `backend/`, using the existing original-checkout `backend/.venv/bin/python` and `PYTHONPATH=src:.`: `python -m pytest tests/world/test_primitives.py tests/world/test_contracts.py tests/security/test_forbidden_apis.py::test_source_tree_has_no_forbidden_apis tests/security/test_forbidden_apis.py::test_core_modules_are_scanned_with_core_rules tests/security/test_forbidden_apis.py::test_core_imports_only_allowlisted_modules -q -o cache_dir=/private/tmp/r1a02-cp1-pytest-cache` — **92 passed** (65 new primitive cases, 24 existing contract cases, 3 security cases). Includes invalid input, immutability, legacy round trips and deterministic mapping across all 1,144 coordinates; this is not lighting/house acceptance evidence.
- **Static checks:** existing environment's `ruff check --no-cache src/maplegotchi/core/world tests/world/test_primitives.py` PASS; `ruff format --check src/maplegotchi/core/world tests/world/test_primitives.py` PASS (5 files); `PYTHONPATH=src:. mypy --cache-dir /private/tmp/r1a02-cp1-mypy src/maplegotchi/core/world tests/world/test_primitives.py` PASS (5 files); `PYTHONPATH=src:. lint-imports --no-cache` **10 kept / 0 broken**. Python 3.12.15 on Mac; no dependency changes. Initial pytest/Ruff cache writes were blocked by the worktree filesystem boundary; rerun with temporary/no caches passed, without warning suppression.
- **Status / safeguards:** Checkpoint 1 criteria met, review pending. R1A-02 **IN PROGRESS**; counters **20 total / 18 TODO / 1 IN PROGRESS / 1 DONE**. Checkpoints 2–6 not started or authorized; R1A-03–R1A-20 TODO. Existing historical worklog entries preserved. No wall/door/passage/lighting/initial-house geometry, catalog, pathfinder, persistence/schema, API/renderer, Oracle/Harness/snapshot, simulation pin, production/default-view or deployment change. Full gate and unrelated tests not run. No production access, commit, push or merge.
- **Ambiguities:** no new Checkpoint 1 blocker. Previously recorded ADR-0036/S15 versus T3/T4 shared `seat` conflict remains deferred to the catalog/capability owner decision gate before R1A-03/06.

### 2026-10-10 (+07) — R1A-02 — Wall-structure Checkpoint 2 (STEP 84)

- **Authorization / baseline:** owner authorizes Checkpoint 2 wall structure only. Verified clean `/Users/paolo_cu/GitHub Desktop/Maplegotchi-r1a-02-world-model`, branch `feat/r1a-02-world-model`, HEAD and live origin ref both `3d389d1fd68838a708cf0c0d6471a82a6426bd5c`. Checkpoint 1 review PASS (STEP 82) and commit/push (STEP 83) retained.
- **Implementation:** new pure `core/world/geometry.py` and `validation.py`: fixed-grid S1 region validation and deterministic L8 floor/band/side/cutaway derivation, immutable row-major cells, deduplicated shared structure and geometric ownership. Bands span x−1…x+w and y−3…y−1; one-column sides span floor rows; one-row cutaway only beneath the lowest tier at the exterior south edge. Reject overlapping floors, duplicate IDs, out-of-grid structures, floor/wall conflicts, incompatible shared structure, interior cutaway and coverage gaps. No authored wall map, door carving, topology, walkability or lighting zones.
- **Focused tests:** using the existing original-checkout `backend/.venv/bin/` tools, from this worktree's `backend/`: `PYTHONPATH=src:. python -m pytest tests/world/test_geometry.py tests/world/test_primitives.py tests/world/test_contracts.py tests/security/test_forbidden_apis.py::test_source_tree_has_no_forbidden_apis tests/security/test_forbidden_apis.py::test_core_modules_are_scanned_with_core_rules tests/security/test_forbidden_apis.py::test_core_imports_only_allowlisted_modules -q -o cache_dir=/private/tmp/r1a02-cp2-pytest-cache` — **130 passed** (38 new structural, 65 Checkpoint 1, 24 contracts, 3 security). Independent synthetic layouts cover exact extents, half-open boundaries, shared corners/columns and southern band ownership, closed-floor geometry, all 1,144 mixed-tier cells, immutability, order independence and invalid arrangements. Initial run: 127 passed / 1 failed because a negative fixture expected a later collision instead of the first uncovered cell; corrected that diagnostic expectation and added two coverage cases. No invalid geometry was accepted.
- **Static checks:** `ruff check --no-cache src/maplegotchi/core/world tests/world/test_geometry.py` PASS; `ruff format --check src/maplegotchi/core/world tests/world/test_geometry.py` PASS (7 files); `PYTHONPATH=src:. mypy --cache-dir /private/tmp/r1a02-cp2-mypy src/maplegotchi/core/world tests/world/test_geometry.py` strict PASS (7 files); `PYTHONPATH=src:. lint-imports --no-cache`: **10 kept / 0 broken**. Existing Python 3.12.15 Mac environment, no dependency changes.
- **Status / scope:** Checkpoint 2 implemented, ready for review; R1A-02 IN PROGRESS. Counters unchanged: 20 total / 18 TODO / 1 IN PROGRESS / 1 DONE. Plan/checklist evidence updated; historical worklog preserved. Checkpoints 3–6 not started or authorized; no initial T1/T2 data, Oracle/Harness/snapshot, Checkpoint 1 source, pinned simulation, schema, API, renderer, persistence, production/default-view or deployment changes. No full gate, production access, commit, push or merge.
- **Remaining:** exact initial-house equality remains Checkpoint 5; door/topology/lighting validations remain their approved checkpoints. No new architecture conflict; the desk-capability conflict stays deferred to R1A-03/06.

### 2026-10-10 (+07) — R1A-02 — Doors and room topology Checkpoint 3 (STEP 87)

- **Authorization / baseline:** owner authorizes Checkpoint 3 only. Verified clean worktree `/Users/paolo_cu/GitHub Desktop/Maplegotchi-r1a-02-world-model`, branch `feat/r1a-02-world-model`, HEAD/live origin `312c81dae03f503368e2379600407acfe454dd1c`. Checkpoint 2 review PASS and owner acceptance/commit/push (STEP 85/86) retained.
- **Implementation:** appended immutable Door/DoorState values to `model.py`; added pure `topology.py` with immutable Passage/RoomNode/Topology. Each 2×3 passage is validated against rederived S1/S2 structure, exactly the named north/south floors, southern band ownership and non-overlap in either state. Reject malformed door values, self-links, duplicate IDs, missing rooms, wrong orientation/band/adjacency and overlapping passages. Open doors alone add deduplicated undirected graph edges; canonical ID order makes passages/nodes/neighbors input-order independent. S4 checks connectivity across open rooms; closed nodes are retained but cannot bridge the open component, consistent with spec S5 / ADR-0035 §2 inaccessibility. No tile walkability implementation.
- **Focused tests:** from this worktree's `backend/`, existing original-checkout `backend/.venv/bin/` tools, `PYTHONPATH=src:.`: `python -m pytest tests/world/test_topology.py tests/world/test_geometry.py tests/world/test_primitives.py tests/world/test_contracts.py tests/security/test_forbidden_apis.py::test_source_tree_has_no_forbidden_apis tests/security/test_forbidden_apis.py::test_core_modules_are_scanned_with_core_rules tests/security/test_forbidden_apis.py::test_core_imports_only_allowlisted_modules -q -o cache_dir=/private/tmp/r1a02-cp3-pytest-cache` — **179 passed**. Added three topology cases for transitive/closed-edge connectivity and deterministic diagnostics, fixed three test regex raw-string lint findings, then ran `python -m pytest tests/world/test_topology.py -q -o cache_dir=/private/tmp/r1a02-cp3-pytest-cache` — **52 passed**. **182 distinct cases passed / 0 failed**, counting the final 52 topology cases plus 130 unaffected cases, without summing repeated cases. Synthetic layouts only; no T1/T2 data or final-house Oracle comparison.
- **Static evidence:** `ruff check --no-cache src/maplegotchi/core/world tests/world/test_topology.py` final PASS; `ruff format --check src/maplegotchi/core/world tests/world/test_topology.py` PASS (8 files); `PYTHONPATH=src:. mypy --cache-dir /private/tmp/r1a02-cp3-mypy src/maplegotchi/core/world tests/world/test_topology.py` strict PASS (8 files); `PYTHONPATH=src:. lint-imports --no-cache` **10 kept / 0 broken**. Existing Python 3.12.15 Mac environment, no dependency changes.
- **Status / safeguards:** Checkpoint 3 implemented, ready for acceptance review; R1A-02 IN PROGRESS, counters 20 total / 18 TODO / 1 IN PROGRESS / 1 DONE. Only new topology/tests, appended Door values and plan/checklist/worklog records change. Prior primitive definitions, wall algorithms, legacy Facing, Oracle/Harness/snapshot, simulation pin, API, schema, persistence, renderer and production paths unchanged. Checkpoints 4–6 not started; no lighting/mount rules, complete initial data, object catalog, pathfinder or production wiring. No Full Release Gate, production access, commit, push, merge or deployment.
- **Remaining:** no new accepted-rule conflict. Exact seven-door initial topology/data equality remains Checkpoint 5; lighting/mount rules remain Checkpoint 4. Existing desk-capability conflict remains deferred to R1A-03/06.
