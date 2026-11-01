#!/bin/sh
# Runs inside the `backup` service: dump the database now, then every
# BACKUP_INTERVAL_SECONDS, deleting dumps older than BACKUP_KEEP_DAYS.
set -eu

while true; do
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    target="/backups/wewin-$stamp.dump"
    if pg_dump --format=custom --no-owner --file="$target.partial"; then
        mv "$target.partial" "$target"
        echo "$(date -u) backup written: $target"
    else
        rm -f "$target.partial"
        echo "$(date -u) backup FAILED" >&2
    fi
    find /backups -name 'wewin-*.dump' -mtime "+${BACKUP_KEEP_DAYS:-14}" -delete
    sleep "${BACKUP_INTERVAL_SECONDS:-86400}"
done
