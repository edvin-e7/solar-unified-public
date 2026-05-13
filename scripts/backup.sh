#!/usr/bin/env bash
# Solar-unified backup — prospects.db + satellite images + learned-data.
#
# Idempotent rsync + retention-rotation. Designed for daily cron:
#   0 4 * * * /home/user/solar-unified/scripts/backup.sh >> /tmp/solar-backup.log 2>&1
#
# Backup-target prio (first writable wins):
#   1. $SOLAR_BACKUP_DIR (env override)
#   2. ~/backups/solar-unified (default for self-host on Mac Mini)
#   3. /Volumes/Backup/solar-unified (external disk pattern)
#
# Retention: keep daily for 7 days, weekly for 4 weeks, monthly forever.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DAY="$(date -u +%Y-%m-%d)"

# Pick backup target
if [[ -n "${SOLAR_BACKUP_DIR:-}" ]]; then
  TARGET="$SOLAR_BACKUP_DIR"
elif [[ -d "${HOME}/backups" ]]; then
  TARGET="${HOME}/backups/solar-unified"
elif [[ -d "/Volumes/Backup" ]]; then
  TARGET="/Volumes/Backup/solar-unified"
else
  echo "[backup] no target dir. Set SOLAR_BACKUP_DIR or mkdir ~/backups" >&2
  exit 1
fi

mkdir -p "$TARGET/daily" "$TARGET/weekly" "$TARGET/monthly"

# --- 1. Snapshot prospects.db (atomic copy via .backup attach) ---

DB="$REPO/backend/data/prospects.db"
if [[ -f "$DB" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    # Use SQLite's .backup command for safe hot-copy
    sqlite3 "$DB" ".backup $TARGET/daily/prospects-${TS}.db"
  else
    # Fallback: cp (may catch a mid-write transaction in rare cases)
    cp "$DB" "$TARGET/daily/prospects-${TS}.db"
  fi
  echo "[backup] prospects.db → $TARGET/daily/prospects-${TS}.db"
fi

# --- 2. Mirror satellite images (incremental if rsync, else cp -r) ---

IMG_DIR="$REPO/backend/data/images"
if [[ -d "$IMG_DIR" ]]; then
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$IMG_DIR/" "$TARGET/images/"
    echo "[backup] images/ rsynced → $TARGET/images/"
  else
    # Fallback: cp -r (not incremental, slower on large image-sets)
    mkdir -p "$TARGET/images"
    cp -a "$IMG_DIR/." "$TARGET/images/"
    echo "[backup] images/ cp-mirrored → $TARGET/images/ (rsync not installed)"
  fi
fi

# --- 3. Snapshot learned-data (journal + summary + prompts_log) ---

LEARNED="$REPO/backend/prompts/learned"
if [[ -d "$LEARNED" ]]; then
  mkdir -p "$TARGET/daily/learned-${TS}"
  cp -a "$LEARNED/." "$TARGET/daily/learned-${TS}/"
  echo "[backup] learned/ → $TARGET/daily/learned-${TS}/"
fi

# --- 4. Retention rotation ---

# Daily: keep 7 most recent
find "$TARGET/daily" -maxdepth 1 -name "prospects-*.db" -type f -printf "%T@ %p\n" \
  | sort -nr | tail -n +8 | awk '{print $2}' | xargs -r rm -f
find "$TARGET/daily" -maxdepth 1 -name "learned-*" -type d -printf "%T@ %p\n" \
  | sort -nr | tail -n +8 | awk '{print $2}' | xargs -r rm -rf

# Weekly: every Sunday, promote latest daily → weekly. Keep 4 weeks.
if [[ "$(date -u +%u)" == "7" ]]; then
  LATEST_DB="$(ls -t "$TARGET/daily"/prospects-*.db 2>/dev/null | head -n 1)"
  if [[ -n "$LATEST_DB" ]]; then
    cp "$LATEST_DB" "$TARGET/weekly/prospects-week-${DAY}.db"
    echo "[backup] weekly snapshot → $TARGET/weekly/prospects-week-${DAY}.db"
  fi
  find "$TARGET/weekly" -maxdepth 1 -name "prospects-week-*.db" -printf "%T@ %p\n" \
    | sort -nr | tail -n +5 | awk '{print $2}' | xargs -r rm -f
fi

# Monthly: on the 1st, promote → monthly. Keep all (cheap, db is small).
if [[ "$(date -u +%d)" == "01" ]]; then
  LATEST_DB="$(ls -t "$TARGET/daily"/prospects-*.db 2>/dev/null | head -n 1)"
  if [[ -n "$LATEST_DB" ]]; then
    cp "$LATEST_DB" "$TARGET/monthly/prospects-month-${DAY}.db"
    echo "[backup] monthly snapshot → $TARGET/monthly/prospects-month-${DAY}.db"
  fi
fi

# --- 5. Size + freshness summary ---

DB_COUNT=$(find "$TARGET/daily" -name "prospects-*.db" | wc -l | tr -d ' ')
IMG_SIZE=$(du -sh "$TARGET/images" 2>/dev/null | awk '{print $1}' || echo "n/a")
echo "[backup] done. daily-dbs=${DB_COUNT}, images=${IMG_SIZE}"
