#!/usr/bin/env bash
# Daily Postgres backup with retention.
# Schedule via cron:
#   0 3 * * * /opt/mooviogo/scripts/backup_db.sh >> /var/log/mooviogo-backup.log 2>&1

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/mooviogo}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/mooviogo-$STAMP.sql.gz"

echo "[backup] $(date -u) starting → $OUT"
pg_dump --no-owner --no-privileges --clean --if-exists \
        --format=plain "$DATABASE_URL" \
    | gzip -9 > "$OUT"

# Rotation
find "$BACKUP_DIR" -name "mooviogo-*.sql.gz" -mtime "+$RETENTION_DAYS" -delete

echo "[backup] $(date -u) done: $(du -h "$OUT" | cut -f1)"

# Optional offsite upload (uncomment + configure):
# aws s3 cp "$OUT" "s3://${BACKUP_BUCKET}/db/$(basename "$OUT")" --storage-class STANDARD_IA
