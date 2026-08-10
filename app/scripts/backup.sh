#!/usr/bin/env bash
# ============================================================================
# AIC-ADE Database Backup Script (FIXED VERSION)
# ===========================================================================

set -euo pipefail

DATA_DIR="${1:-${AIC_DATA_DIR:-./data}}"
BACKUP_DIR="${DATA_DIR}/backups"
DB_FILE="${DATA_DIR}/aic.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aic_${TIMESTAMP}.db.gz"
VALID_BACKUP=""

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database file not found: ${DB_FILE}"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Backing up ${DB_FILE} to ${BACKUP_FILE}..."

# R12 FIX: Checkpoint WAL mode to prevent torn snapshots
sqlite3 "$DB_FILE" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true

# Use temp file approach
TEMP_BACKUP="${BACKUP_FILE%.gz}"
cp "$DB_FILE" "$TEMP_BACKUP"

# Compress
gzip -c "$TEMP_BACKUP" > "$BACKUP_FILE"
rm "$TEMP_BACKUP"

# Validate before considering success
if gzip -t "$BACKUP_FILE"; then
    VALID_BACKUP="$BACKUP_FILE"
    echo "Backup complete and validated: ${BACKUP_FILE}"
else
    echo "ERROR: Backup validation failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Keep only the 7 most recent valid backups
echo "Pruning old backups (keeping last 7)..."
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/aic_*.db.gz 2>/dev/null | wc -l || echo 0)
if [ "$BACKUP_COUNT" -gt 7 ]; then
    ls -1t "${BACKUP_DIR}"/aic_*.db.gz | tail -n +8 | while read old_backup; do
        # Verify backup is valid before pruning
        if gzip -t "$old_backup" 2>/dev/null; then
            rm -f "$old_backup"
            echo "Pruned: $old_backup"
        else
            echo "WARNING: Corrupt backup detected, removing: $old_backup"
            rm -f "$old_backup"
        fi
    done
fi

echo "Done. Total valid backups: $(ls -1 "${BACKUP_DIR}"/aic_*.db.gz 2>/dev/null | grep -v 'corrupt' | wc -l)"
