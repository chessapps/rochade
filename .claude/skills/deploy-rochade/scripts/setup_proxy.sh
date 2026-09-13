#!/usr/bin/env bash
# The box's shared Caddy: TLS from Let's Encrypt, one site block per hostname.
#   ssh USER@IP 'bash -s' < setup_proxy.sh rochade.example.com auth.example.com you@example.com
# Expects the repository at ~/stacks/rochade/src (deploy/proxy comes from it).
set -euo pipefail
APP_HOST="${1:?app hostname, e.g. rochade.example.com}"
AUTH_HOST="${2:?auth hostname, e.g. auth.example.com}"
ACME_EMAIL="${3:?email for Let's Encrypt}"
SRC="$HOME/stacks/rochade/src"
DEST="$HOME/stacks/proxy"

[ -d "$SRC/deploy/proxy" ] || { echo "setup_proxy: $SRC/deploy/proxy not found; clone the repository first" >&2; exit 1; }

if ss -ltn 2>/dev/null | grep -qE ':(80|443) ' && ! docker ps --format '{{.Names}}' | grep -q '^proxy-caddy-1$'; then
  echo "setup_proxy: something else already listens on port 80 or 443 on this box." >&2
  echo "setup_proxy: that proxy has to be the shared one; see 'When the box already has a proxy' in deploy/README.md." >&2
  exit 1
fi

mkdir -p "$DEST"
cp "$SRC/deploy/proxy/docker-compose.yml" "$DEST/docker-compose.yml"
cat > "$DEST/Caddyfile" <<EOF
# Written by deploy-rochade. One site block per stack; after editing:
#   docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
{
	email {\$ACME_EMAIL}
}

# The app: hall, arbiter app, public results and the API on one origin.
$APP_HOST {
	encode gzip
	reverse_proxy rochade-web:8080
}

# Zitadel, the arbiters' sign-in.
$AUTH_HOST {
	reverse_proxy rochade-web:8081
}
EOF
echo "ACME_EMAIL=$ACME_EMAIL" > "$DEST/.env"
chmod 600 "$DEST/.env"

cd "$DEST"
docker compose up -d
echo "setup_proxy: caddy up for $APP_HOST and $AUTH_HOST; certificates follow once the app stack runs"
