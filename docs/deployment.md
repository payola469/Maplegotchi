# Deployment on paolo-core (Phase 7)

How Maplegotchi runs in production. Facts about the host come from the Stage A
survey (`deploy/survey/findings.md`); decisions are ADR-0020 … ADR-0024. The
owner-run procedure is `deploy/install.md`.

This file describes the designed and contract-tested production boundary.

**Latest owner update (2026-10-10):** R-01 implementation is merged and deployed to paolo-core; HTTP Health PASS. Exact deployed SHA, activation time and detailed post-deployment evidence were not supplied with this update; do not infer them from the approved development baseline `5c6db41…`. Pre-R1 clearance APPROVED / CLEAR; R1a AUTHORIZED, R1A-01 baseline preparation IN PROGRESS. No deployment/restart is performed or authorized by this kickoff. Retain the paolo-core build environment. Prior release-gate attempt did not start; complete exact-baseline checks/CI evidence remain missing. See `docs/implementation/maple-room-r1a-01-baseline.md`.

**Historical verified runtime (2026-10-08; release details superseded by the owner update above):**
- `maplegotchi`, `maple-brain` and `maple-discord` are active on paolo-core.
- Each `current` points to release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`.
- The database is at schema v10.
- The listeners are `127.0.0.1:8470` and `127.0.0.1:8471` (`maple_brain`, running as `maple-brain-svc`) only.
- The unit hardening listed below is **loaded** on the live `maplegotchi.service`, and `systemd-analyze security` reports "1.1 OK". Full property list: `docs/architecture.md` → Deployment state.
- Tailscale Serve is tailnet-only (`/` → `http://127.0.0.1:8470`), and Funnel status reports tailnet-only.
- The nightly backup works. The latest observed run, on 2026-10-08, finished 0/SUCCESS, staged the Maple DB snapshot and saved restic snapshot `8b7bea38`.

**Boundary verification update (2026-10-10):**
- **Inside-service runtime probe:** **PASS / CLOSED (recorded 2026-10-10, owner-supplied production evidence)** for release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`. See `docs/implementation/maple-room-r1a-worklog.md` (OD-01 boundary probe PASS). No active polkit-denial, cgroup network-filter enforcement or live POST Origin-denial claim.
- **Isolated Restore Test: PASS / CLOSED (2026-10-10).** Owner-restored schema v10 database opens and passes integrity verification; historical/current archived identity equality and exact-path cleanup passed. Evidence and limitations: `docs/implementation/maple-room-r1a-worklog.md`. Production replacement and restart/recovery were not tested by that restore exercise. R-01 deployment and R1a authorization status are updated above.

See `docs/architecture.md` → Deployment state. The v0.2 companions have their own
units and runbooks: `maple-brain` (`deploy/brain/`, ADR-0033) and `maple-discord`
(`deploy/discord/`, ADR-0032). The order for upgrading from v0.1 is in
`docs/v0.2-review.md` §6.

```
 tailnet browser ──HTTPS──► tailscaled (Serve, :443, Funnel OFF)
                                 │ http
                                 ▼
 maplegotchi.service ── User=maple-svc ── 127.0.0.1:8470 (FastAPI: /api/* + built frontend)
   │  mount namespace: / read-only, /home /root hidden, private /tmp,
   │  /data = empty read-only tmpfs + two binds:
   ├── /data/maple    (bind, read-write)  maple.db — Maple's only writable place
   ├── /data/monitor  (bind, read-only)   metrics.db — collector freshness only
   ├── /run/dbus/system_bus_socket        GetUnit + Get(ActiveState), 5 allowlisted units
   └── /proc, /sys (read-only)            psutil host metrics, coretemp "Package id 0"
```

## Service account `maple-svc` (ADR-0020)
System account (`useradd --system`), primary group `maple-svc`, shell
`/usr/sbin/nologin`, home `/nonexistent` (never created), no password, no sudo,
**no supplementary groups** (not `docker`, `adm`, `sudo`, `systemd-journal`, …).
`deploy/install/setup_host.sh` creates and checks it; `check_boundaries.py` and
`sandbox_probe.sh` re-check it in production.

## Filesystem layout
| Path | Owner / mode | maple-svc | Contents |
|---|---|---|---|
| `/opt/maplegotchi/` | root:root 0755 | read | releases and runtime |
| `/opt/maplegotchi/releases/<commit-sha>/` | root:root, files 0644 (0755 exec) | read | one immutable release: `backend/`, `venv/`, `frontend/dist/`, `deploy/`, `RELEASE`, `SHA256SUMS`, `.complete` |
| `/opt/maplegotchi/current` | root symlink → `releases/<sha>` | read | what systemd runs |
| `/opt/maplegotchi/previous` | root symlink → `releases/<sha>` | read | the release before `current` (rollback) |
| `/opt/maplegotchi/python/` | root:root 0755 | read | uv-managed CPython 3.12.x (pinned patch) |
| `/etc/maplegotchi/` | root:maple-svc 0750 | read | settings |
| `/etc/maplegotchi/maplegotchi.env` | root:maple-svc 0640 | read | `MAPLE_*` environment |
| `/etc/systemd/system/maplegotchi.service` | root:root 0644 | none | the sandbox |
| `/etc/polkit-1/rules.d/50-maplegotchi-deny.rules` | root:root 0644 | none | deny every polkit action to maple-svc |
| `/data/maple/` | maple-svc:maple-svc 0750 | read/write | `maple.db` (+ WAL sidecars) |
| `/data/monitor/metrics.db` | paolo:paolo 0644 (existing) | read (bind ro) | collector database, never written |
| `/usr/local/sbin/maple-db-snapshot` | root:root 0755 | none | backup staging helper (root's backup job) |

`umask 0027` in the unit makes Maple's files 0640. The service map, unit names and
security rules are **code in the release** (root-owned) or root-owned config;
Maple cannot write any of them (§4.1 #5).

## Python runtime (ADR-0023)
D1 stands: **CPython 3.12**, not the host's 3.14. `uv python install` puts a
pinned, hash-verified python-build-standalone CPython (3.12.14) under
`/opt/maplegotchi/python`; each release gets its own venv built with
`uv sync --locked --no-dev --no-editable --compile-bytecode` from the release's
`uv.lock`, using that exact interpreter path (not uv's minor-version link, so a
later patch install cannot silently change an existing release). psutil,
dbus-fast, FastAPI, uvicorn, pydantic live only in that venv. The unit runs
`venv/bin/python -I -m maplegotchi.cli run` (isolated mode).

## Release model (ADR-0023)
1. **Build** (trusted build machine): `scripts/build_release.sh <commit>` →
   `git archive <sha>`, `pnpm install --frozen-lockfile && pnpm build`, bundle
   with `RELEASE` (commit id) and `SHA256SUMS`; prints the bundle's SHA-256.
   The frontend is built here, not on paolo-core: no node/pnpm toolchain or npm
   registry access is needed on the server, the output is plain static files
   covered by the bundle checksums, and CI builds the same lockfile.
2. **Install** (owner, root): `install_release.sh <bundle> <sha256> <uv>` →
   verifies the bundle hash and every file, creates
   `releases/<sha>` (refuses to modify an existing complete release), builds the
   venv in place, `chown -R root:root`, `go-w`, writes `.complete`.
3. **Activate** (owner, root): `activate_release.sh <sha>` → schema check
   (below), `previous` ← old `current`, atomic `current` swap, install the
   release's unit if it changed + `daemon-reload`, `systemd-analyze verify`.
4. **Restart** (owner): `systemctl restart maplegotchi`.

Releases are never edited after `.complete`; a fix is a new commit and a new
release. `check_boundaries.py` re-verifies `SHA256SUMS` and that nothing under
`/opt/maplegotchi` is writable by non-root. Old releases can be removed by the
owner once they are neither `current` nor `previous`.

## Rollback and schema compatibility
Code and data are separate: rollback swaps `current` back and restarts; it never
copies, replaces, or downgrades `/data/maple/maple.db`.

- Maple's schema version is `PRAGMA user_version` (currently **10**); migrations
  only move forward and run automatically at startup inside a transaction.
- A release can open a database whose version is **≤** its own latest migration.
  A database **newer** than the code fails loudly (`SchemaTooNewError`) and is
  never "repaired".
- `activate_release.sh` refuses a release older than the database's schema, and
  requires `--allow-migration` (after a verified `maple-db-snapshot stage` copy)
  before activating a release that would migrate the database forward.
- Rollback across a migration therefore means: activate the older release **and**
  restore the pre-migration copy, accepting the loss of life lived since — an
  explicit owner decision, never automatic.
- Schema v10 (ADR-0034) only adds the nullable `conversation_message.latency_ms`;
  it is forward-only like every migration, so returning to a v9 (v0.2) release means
  restoring the automatic `pre-migration/maple.v9.*.db` copy (or the owner's
  `maple-db-snapshot` copy) and losing life since. `activate_release.sh` needs
  `--allow-migration` for the v9 → v10 step.
- Schema v4 (ADR-0028) is forward-only. Before it migrates, Maple itself also
  writes a verified copy to `/data/maple/pre-migration/` and refuses to migrate if
  that copy fails. Returning to a pre-v4 release is the owner-run restore R6 in
  `deploy/install.md` → Rollback; `MAPLE_DIRECTOR=rule` and forward-fixes need no
  restore.
- Rollback within the same schema (the normal case, e.g. every Phase 7 fix) is
  just `activate_release.sh <previous-sha>` + restart; Maple's identity, state,
  RNG counters, and cooldowns continue from the database.

## systemd sandbox
`deploy/systemd/maplegotchi.service`, checked by `tests/deploy/test_unit_file.py`:
`User=maple-svc`, `NoNewPrivileges`, empty capability bounding/ambient sets,
`ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp`, `PrivateDevices`,
kernel/cgroup/clock/hostname protection, `ProtectProc=invisible`,
`RestrictNamespaces`, `RestrictSUIDSGID`, `LockPersonality`,
`MemoryDenyWriteExecute`, `SystemCallFilter=@system-service` minus privileged
groups (EPERM), `RestrictAddressFamilies=AF_UNIX AF_INET`,
`IPAddressDeny=any` + `IPAddressAllow=localhost`, memory/task limits, and:

```
TemporaryFileSystem=/data:ro      # hide every /data sibling (several are world-readable)
BindPaths=/data/maple             # Maple's only writable place
BindReadOnlyPaths=/data/monitor   # whole dir: SQLite must see a hot -journal to refuse it
InaccessiblePaths=-/run/docker.sock -/var/run/docker.sock -/run/containerd -/var/lib/docker
```
This is the documented systemd pattern (systemd.exec(5), `TemporaryFileSystem=`:
"combine with `BindPaths=`/`BindReadOnlyPaths=`"); `BindPaths=` creates writable
binds and `ProtectSystem=strict` keeps everything else read-only. It could not be
executed on the Windows build machine, so Stage C verifies it on the host
**before** relying on it: `systemd-analyze verify`, `systemd-analyze security`,
and `sandbox_probe.sh` run inside the live service's mount namespace as
maple-svc (writes only to `/data/maple`; `/data` lists only `maple monitor`;
siblings, homes, Docker socket, other processes invisible).

Not set, deliberately: `ProcSubset=pid` (psutil needs `/proc/stat`, `/proc/meminfo`,
`/proc/loadavg`), `PrivateNetwork` (Tailscale Serve connects over loopback),
`PrivateUsers` (D-Bus peer credentials must stay the real uid).

## Senses in production
- Host metrics: psutil (CPU busy share since the last heartbeat, memory, `/` disk,
  load, CPU count, coretemp `Package id 0`).
- Service map (`runtime/senses.py`, `PAOLO_CORE_SERVICES`): see
  `deploy/survey/findings.md` and `docs/sensors.md`. D-Bus allowlist is exactly
  `maplegotchi.service`, `personal-ai-monitor.{service,timer}`,
  `paolo-core-backup.{service,timer}`.

## Exposure (D5, D13)
uvicorn binds `127.0.0.1:8470` (non-loopback is a settings error). Tailscale
Serve (`deploy/tailscale/serve.md`) publishes HTTPS to the tailnet. Funnel off.
Production settings refuse fake senses and non-https origins.

## Backup (ADR-0024)
`deploy/backup/README.md`: the root backup job stages `maple.db` via the SQLite
backup API into `$RUN_DIR/maple.db`, `integrity_check` must be `ok`, then restic.

## Verification
`deploy/verify/check_boundaries.py` (owner, no sudo) and
`deploy/verify/sandbox_probe.sh` (owner via `nsenter`); the full checklist is
`deploy/install.md` §Verify. The unprivileged verifier distinguishes "does not
exist" (FAIL) from "permission denied" (OWNER_CHECK): metadata of files inside
the protected `/etc/maplegotchi`, `/data/maple` and polkit `rules.d` directories
is confirmed by the owner with `sudo stat -c '%U:%G %a %n' …`, which the script
prints with the exact expected output. Permissions are never loosened for it.
