# Backing up Maple's database (Phase 7, ADR-0024)

`/usr/local/sbin/paolo-core-backup` (root, daily 03:30 via `paolo-core-backup.timer`)
does not back up `/data/maple` yet. This patch adds it **without redesigning** the
script: two insertions, nothing removed or changed. n8n, Grafana, metrics.db,
monitor-v2, weekly-log-growth and Atlas handling are untouched.

## The real script's structure (reviewed 2026-09-30)

- bash with `set -Eeuo pipefail` (errors abort the job through its existing
  ERR/exit handling; there is no generic `fail()` function)
- `REPO="/data/backups/paolo-core-restic"`,
  `PASSWORD_FILE="/etc/paolo-core/backup/restic-password"`,
  `STAGING_BASE="/data/backups/paolo-core-staging"`, `RUN_DIR` from `mktemp`
- SQLite backup API staging already exists for `n8n.sqlite`, `grafana.db`, `metrics.db`
- optional monitor-v2, weekly-log-growth and Atlas integrations
- the final `restic … backup` command lists explicit path arguments (no input array)

## How Maple's database is staged

```
/data/maple/maple.db  (live, WAL; opened mode=ro + query_only; never written)
   └─ SQLite online backup API ─► $RUN_DIR/maple.db.partial  (created 0600)
        └─ journal_mode=DELETE    (one self-contained file, no -wal/-shm)
        └─ PRAGMA integrity_check must return exactly "ok";
           Maplegotchi application_id; migrated schema
        └─ chmod 0600, fsync, atomic rename ─► $RUN_DIR/maple.db
restic … backup … "$RUN_DIR/metrics.db" … "$RUN_DIR/maple.db" …   (only if staged)
```

The staging is done by `maple_db_snapshot.py`, installed as
`/usr/local/sbin/maple-db-snapshot` (stdlib only; system `/usr/bin/python3`).

| Situation | Behavior |
|---|---|
| `/data/maple/maple.db` does not exist (Maple not deployed) | the block prints a notice and skips; `MAPLE_DB_STAGED` stays empty; restic gets no Maple argument; the job continues exactly as before |
| database exists and stages cleanly | `$RUN_DIR/maple.db` (0600, integrity `ok`) is added to the restic command |
| database exists but cannot be opened, copied, or fails `integrity_check` / identity checks (or the source is not a file) | the helper exits non-zero, nothing is left at `$RUN_DIR/maple.db`; under `set -Eeuo pipefail` the job **fails** through its existing ERR/exit handling; restic does not run |

## The exact patch

The Maple text is two insertions. Both are checked by `check_patch.sh` and
exercised in `backend/tests/deploy/test_backup_integration.py`, which runs them
inside a replica of the script's structure (live database, missing database,
corrupt/non-database/non-file sources, tampered patches).

**Insertion 1** — immediately after the existing `metrics.db` SQLite staging step
(after `RUN_DIR` exists, before the optional monitor-v2 / weekly-log-growth /
Atlas sections and before `restic`), insert the contents of
[`maple-block.bash`](maple-block.bash) verbatim:

```bash
# --- Maplegotchi database (Phase 7, ADR-0024) -------------------------------
# Live WAL database -> SQLite online backup API -> $RUN_DIR/maple.db (0600),
# PRAGMA integrity_check must be exactly "ok" (maple-db-snapshot enforces it).
# Not deployed yet (no /data/maple/maple.db): skip on purpose.
# Deployed but not stageable: the helper exits non-zero, and set -Eeuo pipefail
# fails the whole job through the script's existing ERR/exit handling.
MAPLE_DB_SOURCE="/data/maple/maple.db"
MAPLE_DB_STAGED=""
if [[ -e "$MAPLE_DB_SOURCE" || -L "$MAPLE_DB_SOURCE" ]]; then
    /usr/local/sbin/maple-db-snapshot stage \
        --source "$MAPLE_DB_SOURCE" --dest "$RUN_DIR/maple.db"
    MAPLE_DB_STAGED="$RUN_DIR/maple.db"
else
    echo "Maplegotchi: $MAPLE_DB_SOURCE not present; Maple not deployed, skipping its database"
fi
# ----------------------------------------------------------------------------
```

**Insertion 2** — in the final `restic … backup \` command, directly after the
explicit `"$RUN_DIR/metrics.db" \` argument line, add one line (indented like its
neighbours):

```bash
    ${MAPLE_DB_STAGED:+"$MAPLE_DB_STAGED"} \
```

It expands to the staged path only when staging succeeded, and to nothing
otherwise (safe under `set -u`: the variable is always defined by the block).
If `"$RUN_DIR/metrics.db"` happens to be the command's last argument (no trailing
backslash), insert the Maple line directly *before* it instead: no existing line
may change, and `check_patch.sh` enforces that.

Why the helper is called as a plain command (not `if helper; then`): a failing
command inside an `if` condition does not trigger `errexit` or the ERR trap. As
a plain command in the `then` branch it fails the job exactly like the existing
n8n/Grafana/metrics staging steps do.

## Stage C procedure (owner)

```bash
# 1. helper + rollback copy
sudo install -o root -g root -m 0755 \
    /opt/maplegotchi/current/deploy/backup/maple_db_snapshot.py /usr/local/sbin/maple-db-snapshot
sudo cp -a /usr/local/sbin/paolo-core-backup /usr/local/sbin/paolo-core-backup.pre-maple

# 2. apply the two insertions (sudoedit), then prove the diff is exactly them
sudoedit /usr/local/sbin/paolo-core-backup
sh /opt/maplegotchi/current/deploy/backup/check_patch.sh      # expect: check_patch: OK
diff -u /usr/local/sbin/paolo-core-backup.pre-maple /usr/local/sbin/paolo-core-backup
```

## Verify

```bash
# helper on its own (Maple has run ≥ 1 heartbeat)
sudo /usr/local/sbin/maple-db-snapshot stage --source /data/maple/maple.db --dest /root/maple-check.db
#   maple-db-snapshot: staged integrity=ok user_version=3 journal_mode=delete name=Maple ...
sudo ls -l /root/maple-check.db          # -rw------- root root
sudo rm -f /root/maple-check.db

# one real backup run
sudo systemctl start paolo-core-backup.service
systemctl show -p Result,ExecMainStatus paolo-core-backup.service     # Result=success ExecMainStatus=0
sudo journalctl -u paolo-core-backup.service -n 80 --no-pager | grep -E 'maple-db-snapshot|Maplegotchi'

# the snapshot contains Maple's database, and a restore opens independently
R="/data/backups/paolo-core-restic"; P="/etc/paolo-core/backup/restic-password"
sudo restic -r "$R" --password-file "$P" snapshots --latest 1
sudo restic -r "$R" --password-file "$P" ls latest | grep '/maple.db$'
sudo restic -r "$R" --password-file "$P" restore latest --target /root/maple-restore-test --include '/**/maple.db'
sudo /usr/local/sbin/maple-db-snapshot verify "$(sudo find /root/maple-restore-test -name maple.db | head -1)"
#   verified integrity=ok ... name=Maple born_at=<same as the API> life_seed_sha256_16=<fingerprint>
sudo rm -rf /root/maple-restore-test
```

Also confirm the other inputs are still present in the same snapshot
(`ls latest` shows `n8n.sqlite`, `grafana.db`, `metrics.db` and the optional
integrations exactly as in the previous night's snapshot).

## Rollback

```bash
sudo cp -a /usr/local/sbin/paolo-core-backup.pre-maple /usr/local/sbin/paolo-core-backup
sudo bash -n /usr/local/sbin/paolo-core-backup
sudo rm -f /usr/local/sbin/maple-db-snapshot
systemctl cat paolo-core-backup.service >/dev/null   # unit unchanged; next 03:30 run uses the old script
```

Restic snapshots already taken keep their `maple.db`; nothing else changes.
