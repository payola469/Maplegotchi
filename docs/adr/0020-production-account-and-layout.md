# ADR-0020: Production service account `maple-svc`, filesystem layout, and namespace sandbox

- **Status:** Accepted — FIXED (CLAUDE.md D19)
- **Date:** 2026-09-30
- **Decided by:** owner (Phase 7 Stage B locked decisions 2–4)

## Context
CLAUDE.md §4.2/§4.3 proposed a user named `maple` and `ReadOnlyPaths=/data/monitor`.
Stage A showed several `/data` siblings are world-readable (0755), so plain file
permissions alone would let the service read unrelated data.

## Decision
- The canonical production account is **`maple-svc`**: system account, its own
  primary group, `/usr/sbin/nologin`, home `/nonexistent`, no password, no sudo,
  no supplementary groups (never `docker`).
- Layout: `/opt/maplegotchi/{releases/<commit-sha>, current, previous, python}`
  root-owned and not writable by `maple-svc`; `/etc/maplegotchi/maplegotchi.env`
  root:maple-svc 0640; `/data/maple` maple-svc 0750 is Maple's only writable path.
- The unit hides all of `/data` behind `TemporaryFileSystem=/data:ro` and binds back
  only `/data/maple` (read-write) and `/data/monitor` (read-only), plus the
  hardening in `deploy/systemd/maplegotchi.service`.

## Consequences
- References to the production account say `maple-svc`; "Maple" remains the being.
- The mount namespace, not file permissions, keeps unrelated `/data` content out of
  reach; it is verified on the host by `deploy/verify/sandbox_probe.sh` before
  acceptance.
- `metrics.db` is already world-readable; no group or ACL grant is made.
