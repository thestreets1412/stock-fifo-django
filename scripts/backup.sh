#!/usr/bin/env bash
# Nightly backup for Stock FIFO Tracker.
# Takes a crash-safe SQLite snapshot, verifies it, archives media,
# rotates old copies, then mirrors everything to the USB drive if mounted.
set -euo pipefail

APP_DIR="/home/minotaur/stock-fifo-django"
BACKUP_DIR="/home/minotaur/backups"
USB_MOUNT="/mnt/backup"
USB_DIR="$USB_MOUNT/stock-fifo"
KEEP_DAYS_LOCAL=14
KEEP_DAYS_USB=60

STAMP=$(date +%Y-%m-%d_%H%M%S)
SNAP="$BACKUP_DIR/db_${STAMP}.sqlite3"
MEDIA_ARCHIVE="$BACKUP_DIR/media_${STAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

# --- 1. Crash-safe snapshot. Never use cp on a live SQLite file. ---
sqlite3 "$APP_DIR/db.sqlite3" ".backup '$SNAP'"

# --- 2. Verify the snapshot opens and is structurally sound. ---
INTEGRITY=$(sqlite3 "$SNAP" "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    echo "FAIL: integrity_check on $SNAP returned: $INTEGRITY" >&2
    rm -f "$SNAP"
    exit 1
fi

# --- 3. Verify the snapshot actually holds ledger rows. ---
LOTS=$(sqlite3 "$SNAP" "SELECT COUNT(*) FROM portfolio_stocklot;")
echo "snapshot ok: $SNAP (stock lots: $LOTS)"

# --- 4. Archive uploaded evidence images. ---
if [ -d "$APP_DIR/media" ]; then
    tar -czf "$MEDIA_ARCHIVE" -C "$APP_DIR" media
    echo "media archived: $MEDIA_ARCHIVE"
else
    echo "WARN: $APP_DIR/media does not exist, skipped media archive" >&2
fi

# --- 5. Rotate local copies. ---
find "$BACKUP_DIR" -maxdepth 1 -name 'db_*.sqlite3' -mtime "+$KEEP_DAYS_LOCAL" -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'media_*.tar.gz' -mtime "+$KEEP_DAYS_LOCAL" -delete

# --- 6. Mirror to USB drive, but only if it is actually mounted. ---
# Without this guard an unplugged drive would leave /mnt/backup as a plain
# directory on the SD card, and the mirror would fill the very disk these
# backups exist to survive.
if mountpoint -q "$USB_MOUNT"; then
    mkdir -p "$USB_DIR"
    rsync -a "$BACKUP_DIR/" "$USB_DIR/"
    find "$USB_DIR" -maxdepth 1 -name 'db_*.sqlite3' -mtime "+$KEEP_DAYS_USB" -delete
    find "$USB_DIR" -maxdepth 1 -name 'media_*.tar.gz' -mtime "+$KEEP_DAYS_USB" -delete
    sync
    echo "mirrored to USB: $USB_DIR"
else
    echo "WARN: $USB_MOUNT is not mounted, USB mirror skipped" >&2
fi

echo "backup complete: $STAMP"
