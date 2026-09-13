#!/usr/bin/env bash
# A nightly compressed dump of the database into ~/backups/rochade, kept 14 days.
#   ssh USER@IP 'bash -s' < install_backup.sh
# Also backs up the env file beside it once, since the master key in it is
# needed to read Zitadel's data. Idempotent.
set -euo pipefail
mkdir -p "$HOME/backups/rochade"
LINE='0 3 * * * mkdir -p ~/backups/rochade && docker exec rochade-postgres-1 pg_dump -U rochade -Fc rochade > ~/backups/rochade/$(date +\%F).dump && find ~/backups/rochade -name "*.dump" -mtime +14 -delete'
( crontab -l 2>/dev/null | grep -v 'backups/rochade' ; echo "$LINE" ) | crontab -
cp -n "$HOME/stacks/rochade/rochade.prod.env" "$HOME/backups/rochade/rochade.prod.env" 2>/dev/null || true
chmod 600 "$HOME/backups/rochade/rochade.prod.env" 2>/dev/null || true
# One dump right away, so the directory is not empty and the command is proven.
docker exec rochade-postgres-1 pg_dump -U rochade -Fc rochade > "$HOME/backups/rochade/$(date +%F).dump"
ls -la "$HOME/backups/rochade"
echo "install_backup: nightly at 03:00, 14 days kept, in ~/backups/rochade (same server: copy it elsewhere too)"
