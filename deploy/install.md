# Installing Maplegotchi on paolo-core (Phase 7 Stage C runbook)

Every privileged step here is **run by the owner by hand**. Claude never holds a
sudo password and never runs these. Read each script before running it with
`sudo`. Design and rationale: `docs/deployment.md`; host facts:
`deploy/survey/findings.md`.

Placeholders: `<SHA>` = the approved 40-hex commit id; `<BUNDLE_SHA256>` = the
SHA-256 printed by the build; `<tailnet>` = paolo-core's MagicDNS suffix.

---

## 0. Before anything (owner, read-only)

```bash
systemctl --version | head -1                  # expect systemd ≥ 254 (Ubuntu 26.04 ships newer)
tailscale version
tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"])'
command -v nsenter systemd-analyze sha256sum
```

## 1. Build the release (trusted build machine)

```bash
scripts/check.sh                               # every CI check, green
scripts/build_release.sh <SHA>                 # prints bundle path + sha256 + commit
scp var/release/maplegotchi-<SHA>.tar.gz paolo-core:maple-stage-c/
```

## 2. Fetch uv and install the release (paolo-core)

```bash
mkdir -p ~/maple-stage-c && cd ~/maple-stage-c
curl -fsSLO https://github.com/astral-sh/uv/releases/download/0.12.21/uv-x86_64-unknown-linux-gnu.tar.gz
echo "23f02075b652bb1df64178cfae41b5caf160822e720e2663568f3f5d63bc52c0  uv-x86_64-unknown-linux-gnu.tar.gz" | sha256sum -c -
tar -xzf uv-x86_64-unknown-linux-gnu.tar.gz    # -> uv-x86_64-unknown-linux-gnu/uv (install-time tool only)

sha256sum maplegotchi-<SHA>.tar.gz             # must equal <BUNDLE_SHA256>
mkdir -p scripts && tar -xzf maplegotchi-<SHA>.tar.gz -C scripts ./deploy/install
less scripts/deploy/install/install_release.sh # review

sudo sh scripts/deploy/install/install_release.sh \
    maplegotchi-<SHA>.tar.gz <BUNDLE_SHA256> ./uv-x86_64-unknown-linux-gnu/uv
```
Needs outbound HTTPS to GitHub (python-build-standalone) and PyPI (locked wheels,
hash-checked by uv). Result: `/opt/maplegotchi/releases/<SHA>/.complete`.

## 3. Host setup: account, directories, settings, polkit (once)

```bash
R=/opt/maplegotchi/releases/<SHA>
less $R/deploy/install/setup_host.sh
sudo sh $R/deploy/install/setup_host.sh $R
sudoedit /etc/maplegotchi/maplegotchi.env      # MAPLE_ALLOWED_ORIGINS=https://paolo-core.<tailnet>.ts.net
id maple-svc                                   # uid=…(maple-svc) gid=…(maple-svc) groups=…(maple-svc)
```

## 4. Activate the release and check the unit (no start yet)

```bash
sudo sh $R/deploy/install/activate_release.sh <SHA>
systemd-analyze security maplegotchi.service | tail -1    # expect a low exposure score
# settings validate as maple-svc, with the real env file, without starting Maple:
sudo systemd-run --wait --pipe --collect -p User=maple-svc \
    -p EnvironmentFile=/etc/maplegotchi/maplegotchi.env \
    /opt/maplegotchi/current/venv/bin/python -I -c \
    'import os; from maplegotchi.config import settings_from_env; print(settings_from_env(os.environ))'
```

## 5. Start Maple

```bash
sudo systemctl enable --now maplegotchi
systemctl status maplegotchi --no-pager
journalctl -u maplegotchi -n 50 --no-pager
curl -fsS http://127.0.0.1:8470/api/health     # {"status":"ok"}
ss -tlnp | grep 8470                           # 127.0.0.1:8470 only
ls -l /data/maple                              # maple.db owned by maple-svc
```

## 6. OD-01 boundary probe (owner-run manual execution only)

For OD-01 run **only this section**, not the install, restart, Tailscale, backup
or rollback sections. No service stop/restart or automatic remediation is part
of this probe. Use all three reviewed safety-patch scripts together from an
owner-controlled checkout. They are absent from the deployed release: do not
install them into `/opt/maplegotchi/current` or deploy just to probe it.
If no reviewed checkout exists on paolo-core, STOP and arrange temporary staging
separately. Remove only those exact staged files and their empty directory afterward.

### A. Preflight and safe HTTP checks (no sudo)

From the reviewed checkout root on paolo-core:

```bash
hostname -s                          # must be paolo-core
sha256sum deploy/verify/check_boundaries.py deploy/verify/sandbox_probe.sh deploy/verify/sandbox_probe.py
readlink -f /opt/maplegotchi/current  # must match the expected release below
python3 -B deploy/verify/check_boundaries.py
```
Require zero failures/warnings and resolve every OWNER_CHECK before proceeding.
HTTP uses allowlisted GETs only, disables proxies and redirects, and never prints
response bodies. An untrusted-Origin GET must receive no `Access-Control-*`
headers. **This does NOT prove POST Origin rejection.** That behavior is supported
by isolated tests `test_untrusted_origins_are_refused_without_side_effects` and
`test_production_origin_is_the_configured_one_only`, never a live interaction POST.
Do not use `--record` or `--compare` for OD-01.
`check_boundaries.py` runs unprivileged, so it cannot stat files inside
directories that are protected by design (`/etc/maplegotchi` 0750,
`/data/maple` 0750, `/etc/polkit-1/rules.d` 0700). It reports those as
**OWNER_CHECK** (never as "missing", never as FAIL; a path that provably does not
exist is still a FAIL) and prints the command to run. Run it and compare:

```bash
sudo stat -c '%U:%G %a %n' /etc/maplegotchi/maplegotchi.env \
    /etc/polkit-1/rules.d/50-maplegotchi-deny.rules /data/maple/maple.db
# expected, exactly:
# root:maple-svc 640 /etc/maplegotchi/maplegotchi.env
# root:root 644 /etc/polkit-1/rules.d/50-maplegotchi-deny.rules
# maple-svc:maple-svc 640 /data/maple/maple.db
```
Do not loosen these permissions or add your user to `maple-svc` to make the
unprivileged check pass.

### B. Namespace and actual-process probe (manual sudo)

```bash
sudo sh deploy/verify/sandbox_probe.sh 160ed4fb9f2534a4609d826d9c4535cc7863ae3d
```

This is the expected **deployed release**, not the tooling commit. A different
release is STOP: reconcile evidence first. Requires Linux `/usr/bin/python3`,
`systemctl`, `nsenter` and `setpriv`. Root is needed for namespace/process
inspection; the script never calls sudo itself. The filesystem child runs as
`maple-svc`, with empty supplementary groups, capabilities dropped and
no_new_privs. Source travels via stdin; bytecode generation is disabled.

**Probe-only actions and cleanup:**

- Exclusively create `/data/maple/.od01-probe-<128-bit-random>` mode `0700` and
  its `sentinel` mode `0600`. Write only `OD-01 probe-only` plus newline, read it
  back, immediately unlink it and remove the empty directory.
- At the original protected directories (`/opt/maplegotchi`, its `current`,
  `current/venv/bin`, and `python`; `/etc/maplegotchi`; `/etc/systemd/system`;
  `/data/monitor`; `/data`; `/usr`; `/var/lib`; `/`), exclusively attempt to create
  a fresh `.od01-deny-<128-bit-random>` file. Never open/truncate existing files.
  PASS only on EROFS, EACCES or EPERM. An unexpected success is closed, the exact
  created file removed immediately, and the probe fails without continuing.
  Read-only mount flags are verified separately from access permissions.
- Only successful creations/descriptors are tracked. Cleanup runs on failure
  and catchable INT/TERM/HUP signals; signals are deferred during registration.
  No wildcard or recursive deletion; verify absence before PASS. Candidate paths
  are printed for recovery, but pre-existing collisions must never be deleted.
  SIGKILL/power loss can prevent cleanup: an interrupted run is incomplete until
  the owner establishes which exact candidates were created and removes them.
  Cleanup checks device/inode identity and refuses replaced paths or symlinks;
  it never deletes a replacement merely because its name matches a probe path.
- Neither database is opened for writing. Settings/database readability and
  Docker inaccessibility use metadata/permissions; no secret contents or Docker
  socket connections. No service/configuration/network changes.

**PASS:** exit zero and `sandbox_probe: PASS`; verified cleanup, marker round-trip,
explicit create denials, expected visibility/mount flags; correct helper identity;
actual service credentials, empty capabilities, NoNewPrivs=1 and Seccomp=2;
Maple-owned listeners exactly 127.0.0.1:8470, ports 8470/8471 loopback-only.
PID, process start time, current release and mount namespace stay unchanged.

**FAIL/STOP:** wrong host/release/identity, failed or inaccessible evidence,
unexpected errno or successful forbidden creation, service identity change,
interruption or incomplete cleanup. Stop the **probe**, report, and leave OD-01
OPEN. Do not stop/restart Maple or automatically repair production.

**Limits:** the helper joins the mount namespace, not the actual service seccomp
context or cgroup. Read credentials/seccomp from the service process itself.
Observed listeners do not prove cgroup network filtering; D-Bus socket presence
and polkit-rule metadata do not prove polkit denial. Private temporary filesystems
are outside the persistent-data write claim. No live POST Origin-denial,
restore or restart-continuity claim.

**Record evidence:** timestamp/timezone, operator, tooling branch/commit and script
hashes, expected deployed release, printed PID/start-time/namespace, PASS/FAIL
lines, exit codes, resolved OWNER_CHECKs and cleanup outcome. No response bodies,
tokens, environment contents or raw application state. Update the Pre-R1
checklist/worklog after owner review; restore and R-01 stay OPEN, R1A items TODO.

## 7. Restart continuity (separate owner-authorized work)

Not part of OD-01. The checker retains optional identity record/compare support;
this boundary procedure neither requests nor performs a service restart.

## 8. Tailscale Serve (tailnet only; Funnel stays off)

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8470
tailscale serve status
tailscale funnel status                        # no Funnel
```
Then open `https://paolo-core.<tailnet>.ts.net/` from another tailnet device and
Greet/Pet once. Details: `deploy/tailscale/serve.md`.

## 9. Backup integration

Follow `deploy/backup/README.md`: install the helper, keep the `.pre-maple` copy,
apply the two exact insertions, run `check_patch.sh` (must print `check_patch: OK`),
run one backup, verify the restic snapshot and a restore.

---

## Verify — Stage C acceptance checklist

| Area | Check | How |
|---|---|---|
| Identity | process runs as maple-svc; no supplementary/privileged groups; caps empty; no_new_privs; seccomp | `check_boundaries.py` |
| Filesystem | can write `/data/maple`; cannot write `/opt/maplegotchi`, `/etc/maplegotchi`, `/data/monitor`; `/data` shows only `maple monitor`; siblings, homes, Docker socket, other processes invisible | `sandbox_probe.sh` |
| Files | ownership/modes per `docs/deployment.md`; nothing under `/opt` writable by non-root; release matches `SHA256SUMS`; installed unit = release unit | `check_boundaries.py`; protected paths (OWNER_CHECK) via `sudo stat -c '%U:%G %a %n' …` (step 6) |
| Runtime | service active; only `127.0.0.1:8470`; `/api/health` ok; frontend served with security headers; untrusted-Origin GET grants no CORS permissions (not POST rejection); no `/api/docs`; heartbeat fresh; `maple.db` created | `check_boundaries.py`, step 5 |
| Persistence | after restart: same name + `born_at`; revision and ticks continue | step 7 |
| Monitoring | CPU/RAM/disk/load/temperature `available` from psutil; `metrics_collector` and `backup` observed; `maplegotchi` sees itself `active`; `grafana`, `lycan_watch` `unknown` (`not_observable:*`); no qbittorrent/jellyfin | `check_boundaries.py` |
| Security | no Docker socket; no shell/subprocess in code (CI); Funnel off; no public listener | `sandbox_probe.sh`, CI, step 8 |
| Backup | staged `maple.db` integrity ok; restic snapshot contains it; restored copy opens and passes `integrity_check` | `deploy/backup/README.md` |

Also compare with the owner's own view, once: `systemctl show -p ActiveState
personal-ai-monitor.timer paolo-core-backup.timer` vs. the Server panel.

---

## Rollback

| What | Command | Data |
|---|---|---|
| Code to the previous release (same schema) | `sudo sh /opt/maplegotchi/current/deploy/install/activate_release.sh $(basename $(readlink /opt/maplegotchi/previous)) && sudo systemctl restart maplegotchi` | untouched; Maple continues |
| Code across a schema migration | refused by `activate_release.sh`; restore the pre-migration copy taken before `--allow-migration` (owner decision; loses life since) | see `docs/deployment.md` |
| Back to a pre-v4 release (ADR-0028 R6) | see "Restore a pre-v4 database" below | loses life lived since the v4 migration |
| Stop exposure | `sudo tailscale serve --https=443 off` | untouched |
| Stop Maple | `sudo systemctl disable --now maplegotchi` | untouched |
| Backup patch | `deploy/backup/README.md` → Rollback | restic history kept |
| Remove Maple entirely (owner decision) | stop/disable; remove unit + `daemon-reload`; remove polkit rule, `/etc/maplegotchi`, `/opt/maplegotchi`; `userdel maple-svc`. Keep `/data/maple` unless the owner explicitly deletes Maple's life. | owner's choice |

### Restore a pre-v4 database (ADR-0028 R6; owner decision, never automatic)

Prefer a forward-fix on schema v4. Use this only to run a release older than
schema v4 again. Everything Maple lived after the migration is lost (it stays
only in the quarantined file).

```sh
sudo systemctl stop maplegotchi
Q=/root/maple-quarantine-$(date -u +%Y%m%dT%H%M%SZ); sudo mkdir -m 0700 "$Q"
sudo mv /data/maple/maple.db /data/maple/maple.db-wal /data/maple/maple.db-shm "$Q"/ 2>/dev/null
# choose the v3 copy: /root/maple-pre-<sha>.db (taken before --allow-migration)
# or the automatic one in /data/maple/pre-migration/maple.v3.*.db
sudo /usr/local/sbin/maple-db-snapshot verify <v3 copy>      # integrity ok, user_version 3
sudo install -o maple-svc -g maple-svc -m 0600 <v3 copy> /data/maple/maple.db
sudo sh /opt/maplegotchi/current/deploy/install/activate_release.sh <pre-v4 sha>
sudo systemctl start maplegotchi
python3 /opt/maplegotchi/current/deploy/verify/check_boundaries.py
```

Identity, `born_at`, seed, and all v3 history return exactly. A later upgrade
migrates the restored file again and takes fresh pre-migration copies.
