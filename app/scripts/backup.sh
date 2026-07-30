#!/usr/bin/env bash
# ============================================================================
# AIC-ADE Database Backup Script
# Copies the SQLite database with a timestamp, compresses with gzip,
# and prunes backups older than the most recent 7.
#
# Usage: ./scripts/backup.sh [DATA_DIR]
#
# To restore a backup:
#   1. Stop the backend:    docker compose stop aic-ade  (or kill the process)
#   2. Decompress:          gunzip backup_file.db.gz
#   3. Copy over database:  cp backup_file.db <DATA_DIR>/aic.db
#   4. Restart backend:     docker compose start aic-ade (or re-run uvicorn)
#
# Or use: ./scripts/restore.sh backup_file.db.gz
# ============================================================================

set -euo pipefail

DATA_DIR="${1:-${AIC_DATA_DIR:-./data}}"
BACKUP_DIR="${DATA_DIR}/backups"
DB_FILE="${DATA_DIR}/aic.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aic_${TIMESTAMP}.db.gz"

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database file not found: ${DB_FILE}"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Backing up ${DB_FILE} to ${BACKUP_FILE}..."
cp "$DB_FILE" - | gzip > "$BACKUP_FILE"

echo "Backup complete: ${BACKUP_FILE}"

# Keep only the 7 most recent backups
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/aic_*.db.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 7 ]; then
    echo "Pruning old backups (keeping last 7)..."
    ls -1t "${BACKUP_DIR}"/aic_*.db.gz | tail -n +8 | xargs rm -f
    echo "Pruned."
fi

echo "Done. Total backups: $(ls -1 "${BACKUP_DIR}"/aic_*.db.gz 2>/dev/null | wc -l)"
