# paolo-core read-only survey (Phase 3, D15)

Before the real service-health provider is configured, record facts about
paolo-core instead of guessing them. **Nothing in this procedure changes the
server.**

## Rules

- Read-only: no writes, no config changes, no `chmod`/`chown`, no package installs.
- No restarts, reloads, starts, or stops of anything.
- Run as your ordinary user (not root). If a file is unreadable, record that; that is a finding too.
- Review output before committing it; `--samples 0` omits database sample rows.

## Step 1 — automated survey (stdlib Python, reads files only)

```bash
# copy deploy/survey/survey_paolo_core.py to paolo-core, then:
python3 survey_paolo_core.py --metrics-db /data/monitor/metrics.db --samples 3 > survey.json
```

It reports:

| Section | Contents |
|---|---|
| `host` | OS release, kernel, architecture, Python and SQLite versions, CPU count, load, uptime, memory total, timezone (`/etc/timezone`, `/etc/localtime`), whether psutil is installed |
| `filesystems` | owner/mode/size of `/data`, `/data/maple`, `/data/monitor`, `metrics.db`; mount point and filesystem type (WAL needs a local filesystem); free space |
| `temperatures` | every `/sys/class/hwmon` chip name and `temp*_input`/label, every `/sys/class/thermal` zone |
| `systemd_units` | unit files matching the D12 keywords in the standard unit directories, symlinks, which `*.wants` enable them, whether a cgroup exists (running), timer stamp times |
| `metrics_db` | read-only open (`mode=ro`, `query_only` verified), journal mode, user_version, application_id, all schema objects and their SQL, per-table columns, row counts, min/max of time-like columns, last N rows |

The script never runs commands. Its read-only behaviour is checked in CI by
`backend/tests/security/test_phase3_boundaries.py`.

## Step 2 — optional owner-run read-only commands

These are for **you** to run by hand if the file-based view is ambiguous. They
only display information. Maple itself never runs them (D4).

```bash
systemctl list-units --all --no-pager --type=service,timer | grep -Ei 'grafana|jellyfin|qbittorrent|lycan|backup|integrity|metric|monitor'
systemctl list-timers --all --no-pager
systemctl show -p Id,ActiveState,SubState,LoadState <unit-name>
busctl introspect org.freedesktop.systemd1 /org/freedesktop/systemd1   # confirms D-Bus is reachable
id; groups                                                             # what the future maple-svc account will need
```

## Step 3 — record findings

Copy the answers into `deploy/survey/findings.md` (template below; the Stage A
results of 2026-09-30 are recorded there) and commit
that, not the raw JSON unless you have reviewed it.

```markdown
# paolo-core survey findings — YYYY-MM-DD

## Monitoring database (/data/monitor/metrics.db)
- Journal mode / filesystem:
- Owner, group, mode; how `maple-svc` could get read-only access (group or ACL):
- Collector cadence (from timestamps):
- Tables and meaning of relevant columns:
- Which host metrics it records (cpu / memory / disk / load / temperature):
- Which service states it records, and for which units:

## Service allowlist (D12) — verified unit names
| service_id | unit name | source that can report it (monitor_db / systemd_dbus / none) |
|---|---|---|
| maplegotchi | (after deploy) | |
| metrics_collector | | |
| grafana | | |
| lycan_watch | | |
| qbittorrent | | |
| jellyfin | | |
| backup | | |

## Temperatures
- Chip/zone to use for "cpu" temperature:

## Host facts
- OS / kernel / Python / SQLite:
- Timezone (expected Asia/Bangkok):
- /data/maple filesystem type (WAL requires local):

## Decisions for the owner
- Is a D-Bus provider needed (services monitoring cannot report)?
```

These findings then drive: the `SchemaExpectation` and read queries for the
monitoring datasource, the deployment service map (`ServiceTarget` unit names),
and whether the D-Bus transport is added.
