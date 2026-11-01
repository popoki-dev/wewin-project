#!/bin/sh
# Restore a dump into the running stack. REPLACES the current database contents.
#   cd deployment && ./backup/restore.sh backups/wewin-20260101T020000Z.dump
set -eu

dump="${1:?usage: $0 path/to/wewin-<timestamp>.dump}"
[ -f "$dump" ] || { echo "No such file: $dump" >&2; exit 1; }

printf 'This replaces the WeWin database with %s. Type "restore" to continue: ' "$dump"
read -r answer
[ "$answer" = "restore" ] || { echo "Aborted."; exit 1; }

docker compose stop server
docker compose exec -T db pg_restore --clean --if-exists --no-owner -U wewin -d wewin < "$dump"
docker compose start server
echo "Restored $dump"
