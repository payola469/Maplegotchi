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
cat /usr/local/sbin/paolo-core-backup          # share it: the backup patch is finalized against it
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

## 6. Verify the boundary (see "Verify" below for the full checklist)

```bash
python3 /opt/maplegotchi/current/deploy/verify/check_boundaries.py
PID=$(systemctl show -P MainPID maplegotchi)
sudo nsenter --target "$PID" --mount --setuid "$(id -u maple-svc)" --setgid "$(id -g maple-svc)" \
     -- /bin/sh /opt/maplegotchi/current/deploy/verify/sandbox_probe.sh
```
If `sandbox_probe.sh` reports any FAIL, stop Maple (`sudo systemctl stop maplegotchi`)
and report it before continuing.

## 7. Restart continuity (after ≥ 1 heartbeat, i.e. 5+ minutes)

```bash
python3 /opt/maplegotchi/current/deploy/verify/check_boundaries.py --record /tmp/maple-before.json
sudo systemctl restart maplegotchi
sleep 5
python3 /opt/maplegotchi/current/deploy/verify/check_boundaries.py --compare /tmp/maple-before.json
```

## 8. Tailscale Serve (tailnet only; Funnel stays off)

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8470
tailscale serve status
tailscale funnel status                        # no Funnel
```
Then open `https://paolo-core.<tailnet>.ts.net/` from another tailnet device and
Greet/Pet once. Details: `deploy/tailscale/serve.md`.

## 9. Backup integration

Follow `deploy/backup/README.md` (install helper, apply the exact diff prepared
from step 0, run one backup, verify the restic snapshot and a restore).

---

## Verify — Stage C acceptance checklist

| Area | Check | How |
|---|---|---|
| Identity | process runs as maple-svc; no supplementary/privileged groups; caps empty; no_new_privs; seccomp | `check_boundaries.py` |
| Filesystem | can write `/data/maple`; cannot write `/opt/maplegotchi`, `/etc/maplegotchi`, `/data/monitor`; `/data` shows only `maple monitor`; siblings, homes, Docker socket, other processes invisible | `sandbox_probe.sh` |
| Files | ownership/modes per `docs/deployment.md`; nothing under `/opt` writable by non-root; release matches `SHA256SUMS`; installed unit = release unit | `check_boundaries.py` |
| Runtime | service active; only `127.0.0.1:8470`; `/api/health` ok; frontend served by the backend with security headers; untrusted Origin → 403; no `/api/docs`; heartbeat fresh; `maple.db` created | `check_boundaries.py`, step 5 |
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
| Stop exposure | `sudo tailscale serve --https=443 off` | untouched |
| Stop Maple | `sudo systemctl disable --now maplegotchi` | untouched |
| Backup patch | `deploy/backup/README.md` → Rollback | restic history kept |
| Remove Maple entirely (owner decision) | stop/disable; remove unit + `daemon-reload`; remove polkit rule, `/etc/maplegotchi`, `/opt/maplegotchi`; `userdel maple-svc`. Keep `/data/maple` unless the owner explicitly deletes Maple's life. | owner's choice |
