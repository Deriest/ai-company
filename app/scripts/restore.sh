#!/usr/bin/env bash
# ============================================================================
# AIC-ADE Database Restore Script
# Restores a gzip-compressed SQLite backup over the live database.
#
# Usage: ./scripts/restore.sh <backup_file.db.gz> [DATA_DIR]
# ============================================================================

set -euo pipefail

BACKUP_FILE="${1:-}"
DATA_DIR="${2:-${AIC_DATA_DIR:-./data}}"
DB_FILE="${DATA_DIR}/aic.db"

if [ -z "$BACKUP_FILE" ]; then
    echo "ERROR: No backup file specified."
    echo "Usage: $0 <backup_file.db.gz> [DATA_DIR]"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "Stopping backend..."
if command -v docker &>/dev/null && [ -f docker-compose.yml ]; then
    docker compose stop aic-ade 2>/dev/null || true
else
    # Try to find and kill any running uvicorn process
    pkill -f "uvicorn backend.main:app" 2>/dev/null || true
fi
sleep 2

echo "Restoring ${BACKUP_FILE} to ${DB_FILE}..."
# Back up current database before overwriting
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "${DB_FILE}.pre-restore"
    echo "Current database backed up to ${DB_FILE}.pre-restore"
fi

gunzip -c "$BACKUP_FILE" > "$DB_FILE"
echo "Restore complete."

echo "Starting backend..."
if command -v docker &>/dev/null && [ -f docker-compose.yml ]; then
    docker compose start aic-ade 2>/dev/null || true
else
    echo "Please restart the backend manually (uvicorn backend.main:app)"
fi

echo "Done."
