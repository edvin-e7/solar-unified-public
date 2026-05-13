#!/usr/bin/env bash
# Solar-unified restore — pick a snapshot, restore over current data.
#
# Usage:
#   scripts/restore.sh                    # list available snapshots, prompt
#   scripts/restore.sh latest             # restore most-recent daily
#   scripts/restore.sh <db-snapshot-path> # explicit path
#
# Refuses to overwrite if backend is currently running (uvicorn process detected).

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${SOLAR_BACKUP_DIR:-${HOME}/backups/solar-unified}"

if [[ ! -d "$TARGET/daily" ]]; then
  echo "[restore] no backup-dir at $TARGET" >&2
  exit 1
fi

# Refuse if backend is running
if pgrep -f "uvicorn main:app" >/dev/null; then
  echo "[restore] backend is running. Stop uvicorn first (Ctrl-C or pkill -f 'uvicorn main:app')." >&2
  exit 1
fi

# Choose snapshot
SNAPSHOT="${1:-}"
if [[ -z "$SNAPSHOT" ]]; then
  echo "Available daily snapshots:"
  ls -t "$TARGET/daily"/prospects-*.db 2>/dev/null | head -10 | nl
  echo ""
  echo "Run: $0 latest    # most recent"
  echo "Run: $0 <path>    # explicit"
  exit 0
fi

if [[ "$SNAPSHOT" == "latest" ]]; then
  SRC="$(ls -t "$TARGET/daily"/prospects-*.db 2>/dev/null | head -n 1)"
elif [[ -f "$SNAPSHOT" ]]; then
  SRC="$SNAPSHOT"
else
  echo "[restore] snapshot not found: $SNAPSHOT" >&2
  exit 1
fi

if [[ -z "$SRC" ]]; then
  echo "[restore] no snapshots in $TARGET/daily" >&2
  exit 1
fi

DEST="$REPO/backend/data/prospects.db"
echo "[restore] restoring $SRC → $DEST"
echo "[restore] CURRENT prospects.db will be backed-up to ${DEST}.before-restore"

if [[ -f "$DEST" ]]; then
  cp "$DEST" "${DEST}.before-restore"
fi
cp "$SRC" "$DEST"
echo "[restore] done. Verify with: sqlite3 $DEST 'SELECT COUNT(*) FROM prospects'"
