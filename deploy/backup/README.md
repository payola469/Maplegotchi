# Backing up Maple's database (Phase 7, ADR-0024)

`/usr/local/sbin/paolo-core-backup` (root, daily 03:30 via `paolo-core-backup.timer`)
does not back up `/data/maple` yet. This adds it **without redesigning** the script:
one helper, one staging call, one extra restic input. n8n / Grafana / metrics /
monitor-v2 / log-growth / Atlas handling is untouched.

## Why a helper and not `cp`

`maple.db` is a live SQLite database in WAL mode; a byte copy can be torn or miss
committed pages still in `maple.db-wal`. The helper follows the script's existing
safe pattern:

```
/data/maple/maple.db  (live, WAL; opened mode=ro + query_only; never written)
   └─ SQLite online backup API ─► $RUN_DIR/maple.db.partial   (created 0600, root)
        └─ journal_mode=DELETE    (one self-contained file, no -wal/-shm)
        └─ PRAGMA integrity_check == "ok", application_id == Maplegotchi, schema migrated
        └─ fsync, atomic rename ─► $RUN_DIR/maple.db
restic backup … "$RUN_DIR/maple.db" …
```

`maple_db_snapshot.py` (stdlib only, runs under the system `/usr/bin/python3`) is
tested in `backend/tests/deploy/test_maple_db_snapshot.py` against a *live* Maple
database (open WAL connection, heartbeats continuing during and after the copy),
corrupted copies, foreign/unmigrated files, and existing destinations.

Exit codes: `0` staged and verified · `3` **not deployed** (`/data/maple` does not
exist: skip intentionally) · `1` anything else. Once `/data/maple` exists, Maple is
deployed and a missing/unreadable/corrupt database is a **failure** (exit 1) that
must go through the script's existing fail-safe path — no silent skip.

## Install the helper (owner, Stage C)

```bash
sudo install -o root -g root -m 0755 \
    /opt/maplegotchi/current/deploy/backup/maple_db_snapshot.py /usr/local/sbin/maple-db-snapshot
sudo cp -a /usr/local/sbin/paolo-core-backup /usr/local/sbin/paolo-core-backup.pre-maple   # rollback copy
```

## Patch (template — finalize against the real script first)

Stage A did not capture the backup script, so the exact diff (its variable for the
staging directory, its failure/alert function, how it builds the restic input list)
must be read first. **Stage C step 0:** the owner shares the output of

```bash
cat /usr/local/sbin/paolo-core-backup      # read-only; the script is root 0755
```

and the template below is turned into an exact unified diff against it. The
template assumes bash, `set -e`, a staging directory `$RUN_DIR`, a failure path
named `fail`, and an array `RESTIC_INPUTS` — each is replaced by the script's real
equivalent; the logic does not change.

Insert after the existing SQLite staging steps (the metrics.db / Grafana ones),
before `restic backup`:

```bash
# --- Maplegotchi database (Phase 7, ADR-0024) --------------------------------
# Live WAL DB -> SQLite backup API -> integrity_check -> $RUN_DIR/maple.db.
# rc 3 = Maple not deployed on this host (no /data/maple): skip on purpose.
maple_rc=0
/usr/local/sbin/maple-db-snapshot stage \
    --source /data/maple/maple.db --dest "$RUN_DIR/maple.db" || maple_rc=$?
case "$maple_rc" in
    0) RESTIC_INPUTS+=("$RUN_DIR/maple.db") ;;
    3) echo "paolo-core-backup: Maple not deployed; skipping maple.db" ;;
    *) fail "Maple database snapshot failed (rc=$maple_rc)" ;;
esac
# ----------------------------------------------------------------------------
```

If the script lists restic inputs inline instead of in an array, the staged file
is added to that list conditionally in the same way the other staged databases are.
The staged copy lives in `$RUN_DIR`, so the script's existing `$RUN_DIR` cleanup
removes it after the snapshot.

## Verify (owner, Stage C, after Maple has run for at least one heartbeat)

```bash
sudo bash -n /usr/local/sbin/paolo-core-backup                 # syntax
sudo systemctl start paolo-core-backup.service                 # one real run
systemctl show -p Result,ExecMainStatus paolo-core-backup.service   # Result=success, status 0
sudo journalctl -u paolo-core-backup.service -n 50 --no-pager | grep -i maple
#   expect: "maple-db-snapshot: staged ... integrity=ok ..."
# With the script's restic environment (repository/password as the script sets them):
sudo -E restic snapshots --latest 1
sudo -E restic ls latest | grep '/maple.db$'
sudo -E restic restore latest --target /root/maple-restore-test --include '/**/maple.db'
sudo /usr/local/sbin/maple-db-snapshot verify "$(sudo find /root/maple-restore-test -name maple.db | head -1)"
#   expect: "verified integrity=ok ... name=Maple born_at=... life_seed_sha256_16=..."
#   and the same born_at / fingerprint as:
sudo /usr/local/sbin/maple-db-snapshot stage --source /data/maple/maple.db --dest /root/maple-compare.db
sudo rm -rf /root/maple-restore-test /root/maple-compare.db
```

Failure path: the helper's failures (missing, corrupt, foreign database) are
covered by tests; on the host, confirm from the script's code (Stage C step 0)
that the call uses the same failure/alert path as the other database staging
steps. No production failure is provoked on purpose.

## Rollback

```bash
sudo cp -a /usr/local/sbin/paolo-core-backup.pre-maple /usr/local/sbin/paolo-core-backup
sudo rm -f /usr/local/sbin/maple-db-snapshot
sudo bash -n /usr/local/sbin/paolo-core-backup
```

Restic snapshots already taken keep their `maple.db`; nothing else changes.
