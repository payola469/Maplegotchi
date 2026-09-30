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
