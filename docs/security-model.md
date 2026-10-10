# Security model

`CLAUDE.md` §4 is the source of truth. This file will record the concrete
evidence behind it as phases land (test names, systemd unit review, the
Phase 3 paolo-core survey, and `check_boundaries.py` output).

## Enforced today (Phases 0–7 Stage B, plus v0.2 on `v0.2-development`)

| Control | Where |
|---|---|
| No subprocess / shell / exec / eval / process-kill APIs in `backend/src` | `backend/tests/security/test_forbidden_apis.py` (AST scanner, self-tested) |
| `core` has no I/O, clock, randomness, or concurrency imports | same scanner, core rules |
| `core` imports only allowlisted stdlib modules (`__future__`, `collections`, `dataclasses`, `datetime`, `enum`, `hashlib`, `math`, `types`, `typing`) and `maplegotchi.core.*` | `test_core_imports_only_allowlisted_modules` (Phase 1) |
| Heartbeat cannot invoke a Brain (no Brain parameter) | `tests/core/test_heartbeat.py::test_heartbeat_takes_no_brain` (Phase 1) |
| Only Greet/Pet exist; D14 limits fixed and restart-safe | `tests/core/test_interactions.py`, `tests/core/test_state.py` (Phase 1) |
| Only `maplegotchi.storage` writes files or imports `sqlite3`/`shutil`/`tempfile` | scanner "write-outside-storage" rules (Phase 2) |
| Every Maple-owned write resolves inside `MAPLE_DATA_DIR` (`..`, absolute, drive, UNC, device names, symlink/junction escapes rejected) | `storage/datadir.py`, `tests/storage/test_datadir.py` (Phase 2) |
| Identity and life seed immutable; timeline append-only; one birth; revisions advance by one; RNG counters never decrease | SQLite triggers + unique index (migration 1), `tests/storage/test_database.py` (Phase 2) |
| Corrupt / foreign / empty / too-new databases fail loudly, never replaced | `storage/db.py`, `tests/storage/` (Phase 2) |
| SQLite hardening: `trusted_schema=OFF`, defensive mode | `storage/db.py` (Phase 2) |
| Birth is published only from a self-contained rollback-journal file (no WAL/sidecar dependency) | `storage/db.py`, `tests/storage/test_birth_publication.py` (Phase 2) |
| `sqlite3` only inside storage; external monitoring DB read via read-only `storage.external` datasource, never from sensors (D18) | scanner (`external` mode: may read SQLite, may not write), import-linter (sensors → only `storage.external.interface`; external ↔ Maple storage separated), `tests/security/test_phase3_boundaries.py` |
| External DB opened `mode=ro` + `query_only`; write SQL refused by SQLite; no write/execute/schema method in the API; no write-SQL text in `storage/external` | `tests/storage/test_external_metrics.py`, `tests/security/test_phase3_boundaries.py` |
| Sensors import no `sqlite3`/`subprocess`/`shutil`/`tempfile`/`socket`/writable storage | `test_sensors_never_import_sqlite3_subprocess_or_writable_storage` |
| D-Bus client and dbus-fast transport can send only `GetUnit` and `Get(Unit.ActiveState)` for allowlisted units; only the transport imports dbus_fast | `tests/sensors/test_systemd_dbus.py`, `tests/security/test_phase3_boundaries.py` |
| Production settings refuse fake senses, non-https origins, non-loopback binds | `tests/api/test_api_security.py` |
| systemd unit: `User=maple-svc`, no capabilities, `ProtectSystem=strict`, `/data` hidden except `/data/maple` (rw) and `/data/monitor` (ro), loopback-only IP, syscall filter | `tests/deploy/test_unit_file.py`; on the host `deploy/verify/sandbox_probe.sh`, `check_boundaries.py` |
| Backup staging never writes Maple's DB and publishes only an integrity-checked copy | `tests/deploy/test_maple_db_snapshot.py` |
| Survey script linted (ruff) and type-checked (mypy strict) in normal CI, plus security tests | `.github/workflows/ci.yml`, `backend/pyproject.toml` (mypy files), `tests/security/test_phase3_boundaries.py` |
| No `systemctl` in any executable string in `backend/src` or the survey | `test_no_systemctl_anywhere_in_executable_text`, `test_survey_script_uses_no_forbidden_or_writing_apis` |
| Only the built-in RuleBrain may claim `kind=rule` (exact class); impostor Brains are refused before storage opens. Since v0.2 (ADR-0025) an explicitly configured external Brain (`BrainKind.EXTERNAL`, `MAPLE_BRAIN=antigravity`) is accepted. *(Earlier text named `require_rule_brain`; that function no longer exists.)* | `runtime/life.py: require_supported_brain`, `runtime/brain_factory.py`, `tests/runtime/test_journal_runtime.py`, `tests/runtime/test_external_brain.py` |
| `brain` package is pure like core (no I/O, clock, randomness, network; import allowlist) | AST scanner, `test_core_imports_only_allowlisted_modules` |
| Journal grounded: references come from core triggers; no unreferenced service names; RuleBrain output digit-free (template policy); entries append-only; Brain failure never marks a trigger as journaled | `core/journal.py: accept_drafts`, migration 3 CHECKs/triggers, `tests/core/test_journal.py` |
| API surface is exactly the approved routes. The only mutations are Greet/Pet (trusted Origin) and, since v0.2, `POST /api/conversation/messages` (gateway token, ADR-0032). | `tests/api/test_api_security.py::test_route_table_is_exactly_the_approved_surface` |
| Conversation gateway route: 404 without a configured token, 403 with any `Origin`, 401 without a matching bearer (`hmac.compare_digest`), ≤ 8 KB body, idempotent by message id | `api/security.py: gateway_guard`, `tests/api/test_conversation_api.py` |
| External Director/Replier (v0.2): loopback-only `MAPLE_BRAIN_URL`, no redirects, 16 KB response cap, exact response keys, called **outside** the writer lock with a deadline and never stacked; every answer re-validated by core, else rule fallback; no prompt or raw model output stored | `runtime/external_director.py`, `runtime/external_replier.py`, `runtime/service.py`, `core/proposal.py`, `tests/runtime/test_director_runtime.py`, `tests/api/test_conversation_api.py` |
| Companion units (v0.2): `maple-brain.service` (`maple-brain-svc`, loopback 127.0.0.1:8471, `/data` and Maple/Discord config inaccessible, MDWE unset by owner decision, outbound allowed) and `maple-discord.service` (`maple-discord-svc`, tokens via `LoadCredential`, MDWE on, no listener) | `deploy/brain/`, `deploy/discord/`, `tests/deploy/test_brain_unit.py`, `tests/deploy/test_discord_unit.py` |
| Brain companion refuses auto-approve / permission-bypass provider flags, runs the provider with argv (no shell), a scratch cwd, minimal env, timeout, and output cap | `companion/brain/src/maple_brain/config.py`, `provider.py`, `companion/brain/tests/test_brain.py` |
| Loopback-only bind; exact allowed origins (no wildcards); production requires origins and hides docs | `config.py`, `tests/api/test_api_security.py` |
| No CORS; Greet/Pet require a trusted Origin (403 otherwise, no side effects); bodies ≤ 1 KiB; security headers; no Server header | `api/security.py`, `tests/api/test_api_interactions.py`, `tests/api/test_api_security.py` |
| Snapshots read from one committed DB view (single read transaction); SSE publishes only committed transitions, after commit, outside the lock | `storage/repositories.py: read_view`, `runtime/service.py`, `tests/api/test_consistency.py` |
| SSE is read-only, bounded, and never blocks the writer | `runtime/events.py`, `api/stream.py`, `tests/api/test_sse.py` |
| Static frontend never shadows `/api`; traversal refused | `api/static.py`, `tests/api/test_api_security.py` |
| Observations append-only; stored atomically with their heartbeat | migration 2 triggers, `tests/runtime/test_observations_runtime.py` |
| Banned APIs flagged while editing | ruff `TID251` + `S` rules (`backend/pyproject.toml`) |
| Layer dependency rules (CLAUDE.md §3.3) | import-linter contracts (`backend/pyproject.toml`) |
| No `eval` / `new Function` / raw HTML sinks in the UI | `frontend/eslint.config.js` |
| All of the above in CI on every push/PR | `.github/workflows/ci.yml` |

## Production boundary (Phase 7)

The deployment design and its verification are in `docs/deployment.md`
(ADR-0020 … ADR-0024). Maple runs as `maple-svc` (no shell, no home, no groups,
no capabilities, no_new_privs, seccomp) inside a mount namespace where the OS is
read-only, `/home` and `/root` are hidden, `/data` is an empty read-only tmpfs
except `/data/maple` (read-write) and `/data/monitor` (read-only), and container
runtime sockets are inaccessible. It binds 127.0.0.1:8470 only, egress/ingress is
limited to localhost, and Tailscale Serve (Funnel off) is the only way in. polkit
denies every action to `maple-svc`. Evidence on the host comes from
`deploy/verify/check_boundaries.py` and `deploy/verify/sandbox_probe.sh`
(Stage C); their parsers and verdicts are unit-tested in `tests/deploy/`.

**Verified current runtime (2026-10-08, owner-supplied evidence):**
- `maplegotchi`, `maple-brain` and `maple-discord` are active on paolo-core at release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`.
- The production database is schema v10.
- The only listeners are `127.0.0.1:8470` and `127.0.0.1:8471`, both loopback. Port 8471 belongs to `maple_brain`, which runs as `maple-brain-svc`.
- **systemd hardening is verified as loaded** on the live `maplegotchi.service`:
  - `User=maple-svc`, `Group=maple-svc`
  - `ProtectSystem=strict`, `ProtectHome=yes`, `NoNewPrivileges=yes`, `PrivateTmp=yes`, `PrivateDevices=yes`, `ProtectProc=invisible`, `RestrictNamespaces=yes`, `RestrictAddressFamilies=AF_INET AF_UNIX`
  - `IPAddressDeny=::/0 0.0.0.0/0`, `IPAddressAllow=127.0.0.0/8 ::1/128`
  - `MemoryHigh=402653184`, `MemoryMax=536870912`, `TasksMax=64`

  `systemd-analyze security` reports "Overall exposure level for maplegotchi.service: **1.1 OK**".
- **Tailscale:** Serve is tailnet-only (`/` → `http://127.0.0.1:8470`), and Funnel status reports tailnet-only.
- **Backup creation is verified:** the 2026-10-08 nightly run succeeded, the Maple DB snapshot was staged, and restic snapshot `8b7bea38` was saved.
- **External Brain in production:** `MAPLE_BRAIN`, `MAPLE_DIRECTOR` and `MAPLE_REPLIER` are all `antigravity`. Known limitation 1 below therefore applies to the live service.

**Boundary verification update (2026-10-10):**
- **Inside-service runtime boundary behaviour:** **PASS / CLOSED (recorded 2026-10-10, owner-supplied production evidence)** for release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`. See `docs/implementation/maple-room-r1a-worklog.md` (OD-01 boundary probe PASS). No active polkit-denial, cgroup network-filter enforcement or live POST Origin-denial claim.
- **Isolated Restore Test: PASS / CLOSED (2026-10-10)** from owner-supplied evidence; see `docs/implementation/maple-room-r1a-worklog.md`. No production replacement or restart/recovery claim from that exercise; archived identity equality does not authenticate original provenance or prove uninterrupted continuity. Owner now confirms R-01 deployed/HTTP Health PASS, Pre-R1 clearance APPROVED / CLEAR and R1a AUTHORIZED; only R1A-01 baseline preparation starts.

See `docs/architecture.md` → Deployment state.

## Services and trust relationships (current code, v0.2)

| Service | Account | Listens | Talks to | Holds secrets |
|---|---|---|---|---|
| `maplegotchi` | `maple-svc` | 127.0.0.1:8470 | `maple-brain` on 127.0.0.1:8471 (only when `MAPLE_BRAIN`/`MAPLE_DIRECTOR`/`MAPLE_REPLIER` = `antigravity`); systemd over D-Bus (read-only); `metrics.db` (read-only) | the gateway token (`MAPLE_GATEWAY_TOKEN`), if configured |
| `maple-brain` | `maple-brain-svc` | 127.0.0.1:8471 | the provider CLI (subprocess, argv, no shell) and its outbound network | the provider login, in its `StateDirectory` only |
| `maple-discord` | `maple-discord-svc` | nothing | Discord (outbound); Maple on 127.0.0.1:8470 (read GETs; `POST /api/conversation/messages` with the gateway token) | the bot token and gateway token, via `LoadCredential` |

Boundaries between the services:
- Maple never calls Discord.
- The Brain companion never calls Maple.
- Neither companion can read `/data` or Maple's configuration.
- No service in the repository has write access to another service's data.

## Known limitations and open items (documented, not fixed)

1. **R-01: PASS / CLOSED; owner confirms production deployment and HTTP Health PASS (2026-10-10).**
   - Historical finding on the old release: journal `/generate` held the writer lock, with a 30 s default and no explicit response cap/redirect refusal. Owner now confirms remediation deployed; exact deployed SHA and detailed acceptance transcript not supplied. HTTP Health alone does not prove concurrency, timeout or sandbox enforcement. No agent production access. Pre-R1 clearance APPROVED / CLEAR; R1a AUTHORIZED, R1A-01 baseline preparation only; full baseline checks/CI remain unverified.
   - Repository patch: prepare under lock → one daemon composes unlocked → revision/lifecycle revalidation → atomic commit. Stale candidates are recomputed without wording; busy/timeout/failure also yields no wording. Core validation and existing retry opportunities remain authoritative.
   - Monotonic caller deadline: 30 s including startup, request preparation and parsing; connect at most 2 s. Streamed HTTP body limited to 64 KiB before JSON parsing; redirects/environment proxies refused; no automatic retries. Only identity content coding is accepted, preventing decompression expansion before the cap.
   - Timed-out workers retain their slot through transport cleanup: at most one outstanding request per runtime, no replacement worker or durable queue. Workers have no storage or commit capability.
   - Shutdown closes admission, invalidates preparations, wakes waiters and drains callers through their final reads before storage closes. Every persistence path obtains an irrevocable commit permit under the same gate lock as shutdown admission closure: shutdown first aborts the preparation without persistence; permit first allows that transaction to finish atomically. The gate lock is released before SQLite work and never held while acquiring the writer lock.
   - Limits: bounded external-journal caller waiting, subject to scheduling/other operations, does not force blocked daemons to terminate or guarantee bounded whole-process shutdown. A stuck request keeps wording busy until cleanup or restart. No eventual-wording guarantee. RuleBrain remains synchronous; Director/Replier behavior is not redesigned.
   - Evidence: R1a worklog. No schema, service/configuration, backup-tooling or production changes.
2. **Future owner mutations need owner authentication.**
   - Today the tailnet plus an exact `Origin` is the only check on browser mutations (Greet/Pet).
   - Any future owner-only mutation must first get an owner-authentication decision and an ADR. Examples are the proposed Room Editor and project approvals.
   - Tracked as OD-03 in `docs/architecture/maple-future-architecture.md` (PROPOSED).
3. **The future code-execution sandbox (`maple-exec`) is unvalidated.**
   - The proposed systemd socket-activated, per-job design has not been checked against paolo-core's systemd version and AppArmor user-namespace policy.
   - It is a proposal only (OD-06). No execution capability exists today, and §4.1 #2 (no subprocess or shell in the backend) is unchanged.

Future boundaries such as the workspace mount, `maple-exec` and `maple-observer` are
**DRAFT / PROPOSED / FOR HUMAN REVIEW** in `docs/architecture/`. They do not exist in
the code or the units.
