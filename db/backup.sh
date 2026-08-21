#!/bin/sh
# Периодический pg_dump с ротацией: хранит только BACKUP_KEEP последних файлов.
set -eu

mkdir -p /backups

while true; do
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "/backups/${POSTGRES_DB}_${ts}.dump"
  ls -1t "/backups/${POSTGRES_DB}"_*.dump | tail -n "+$((BACKUP_KEEP + 1))" | xargs -r rm -f --
  sleep "$BACKUP_EVERY"
done
