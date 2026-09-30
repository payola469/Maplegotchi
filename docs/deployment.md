# Deployment on paolo-core (Phase 7)

How Maplegotchi runs in production. Facts about the host come from the Stage A
survey (`deploy/survey/findings.md`); decisions are ADR-0020 … ADR-0024. The
owner-run procedure is `deploy/install.md`.

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

- Maple's schema version is `PRAGMA user_version` (currently **3**); migrations
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
`deploy/install.md` §Verify.
