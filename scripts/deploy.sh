#!/usr/bin/env sh
# Deploy the stack to the box through a docker context over SSH.
# Usage: scripts/deploy.sh [context] [env-file]     (defaults: box, rochade.prod.env)
# One-time setup on both ends is in deploy/README.md.
set -eu
cd "$(dirname "$0")/.."
context="${1:-workbench}"
envfile="${2:-rochade.prod.env}"

if [ ! -f "$envfile" ]; then
  echo "$envfile not found. Copy .env.example to $envfile and set POSTGRES_PASSWORD." >&2
  exit 1
fi

docker --context "$context" compose \
  -f docker-compose.yml -f docker-compose.prod.yml \
  -p rochade --env-file "$envfile" \
  up -d --build --remove-orphans

docker --context "$context" compose -p rochade ps
