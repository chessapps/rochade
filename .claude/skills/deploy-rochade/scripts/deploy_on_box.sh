#!/usr/bin/env bash
# Build and start (or update) the stack on the box from ~/stacks/rochade/src.
#   ssh USER@IP 'bash -s' < deploy_on_box.sh [git-ref]
# Pulls the ref (default: main), builds the images on the box, brings the
# stack up with the production overlay, and prints the service table.
set -euo pipefail
REF="${1:-main}"
DIR="$HOME/stacks/rochade"
SRC="$DIR/src"
ENV="$DIR/rochade.prod.env"

[ -f "$ENV" ] || { echo "deploy_on_box: $ENV missing; run make_env.sh first" >&2; exit 1; }
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch -q origin
  git -C "$SRC" checkout -q "$REF"
  git -C "$SRC" pull -q --ff-only origin "$REF" 2>/dev/null || true
else
  git clone -q --branch "$REF" https://github.com/chessapps/rochade.git "$SRC"
fi
echo "deploy_on_box: source at $(git -C "$SRC" rev-parse --short HEAD) ($REF)"

cd "$SRC"
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -p rochade --env-file "$ENV" \
  up -d --build --remove-orphans

echo "deploy_on_box: waiting for the API"
for _ in $(seq 1 30); do
  if docker compose -p rochade ps --format '{{.Service}} {{.Health}}' 2>/dev/null | grep -q '^web healthy'; then
    break
  fi
  sleep 10
done
docker compose -p rochade ps
docker image prune -f >/dev/null
echo "deploy_on_box: done"
