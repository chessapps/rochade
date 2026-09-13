#!/usr/bin/env bash
# Write ~/stacks/rochade/rochade.prod.env with generated secrets.
#   ssh USER@IP 'bash -s' < make_env.sh rochade.example.com auth.example.com arbiter@club.ch [smtp_host:port smtp_user smtp_password smtp_from]
# Prints the first arbiter's password once and nothing else that is secret.
# Refuses to overwrite an existing file: the secrets in it are baked into the
# data directories on first start and cannot be regenerated.
set -euo pipefail
APP_HOST="${1:?app hostname}"
AUTH_HOST="${2:?auth hostname}"
ARBITER_EMAIL="${3:?first arbiter email}"
SMTP_HOST="${4:-}"
SMTP_USER="${5:-}"
SMTP_PASSWORD="${6:-}"
SMTP_FROM="${7:-}"
case "$SMTP_HOST" in *:587) SMTP_TLS=false ;; *) SMTP_TLS=true ;; esac

DIR="$HOME/stacks/rochade"
FILE="$DIR/rochade.prod.env"
mkdir -p "$DIR/data/postgres" "$DIR/data/zitadel" "$DIR/data/auth"

if [ -f "$FILE" ]; then
  echo "make_env: $FILE exists; leaving it alone. Edit it by hand for SMTP or other settings." >&2
  exit 0
fi

rand() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
POSTGRES_PASSWORD="$(rand 32)"
MASTERKEY="$(rand 32)"           # Zitadel wants exactly 32 characters
ARBITER_PASSWORD="$(rand 10)!"   # Zitadel's default policy asks for a symbol

umask 077
cat > "$FILE" <<EOF
# Written by deploy-rochade on $(date -I). Secrets; back it up, never share it.
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

ROCHADE_PUBLIC_URL=https://$APP_HOST

# Four views of one URL; Zitadel needs each and refuses when they disagree.
AUTH_URL=https://$AUTH_HOST
AUTH_DOMAIN=$AUTH_HOST
AUTH_PORT=443
AUTH_SCHEME=https
AUTH_SECURE=true

# Exactly 32 characters. Losing it loses Zitadel's stored secrets.
ZITADEL_MASTERKEY=$MASTERKEY

# The first arbiter, created on Zitadel's first start only.
ZITADEL_ADMIN_EMAIL=$ARBITER_EMAIL
ZITADEL_ADMIN_PASSWORD=$ARBITER_PASSWORD

ROCHADE_DEV_AUTH_ENABLED=false
ROCHADE_DEVICE_JOIN_ENABLED=false

ROCHADE_DATA_DIR=$DIR/data
PROXY_NETWORK=proxy

# Outgoing mail: arbiter invitations, passkey links, password resets.
# Empty means nothing is sent; add it later and redeploy.
SMTP_HOST=$SMTP_HOST
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM=$SMTP_FROM
SMTP_FROM_NAME=Rochade
# true for implicit TLS (port 465), false for STARTTLS (port 587).
SMTP_TLS=$SMTP_TLS
EOF

echo "make_env: wrote $FILE"
echo "make_env: first arbiter $ARBITER_EMAIL, password: $ARBITER_PASSWORD"
