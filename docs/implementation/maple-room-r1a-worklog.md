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
