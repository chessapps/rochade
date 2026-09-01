# Seebach

Digital result entry for chess tournaments that someone else is running.

An existing manager — Vega, Swiss-Manager — stays the tournament manager: it
owns setup, the player list, the pairings, the tiebreaks and the public view.
Seebach does the one thing it cannot — put a phone in every player's hand — and
hands the results back each round.

```
  manager                       Seebach                       manager
  ───────                       ───────                       ───────
  pair round N
  export      ──────────────▶  import, open round N
                                players enter results (hall PWA)
                                arbiter reviews + confirms
                               export      ─────────────────▶  import results
                                                               pair round N+1 ──▶ (loop)
```

Which manager is an adapter choice, not an architecture — see
`src/seebach/interchange/`. Every adapter declares what it *cannot* do, and
ships `UNVERIFIED` until someone has watched it work; `spikes/README.md` is the
round-trip spike that turns those flags into facts.

See [PLAN.md](PLAN.md) for the design and the reasoning behind it.

## Running it

```sh
docker compose up --build
```

- hall app — <http://localhost:8080>
- arbiter app — <http://localhost:8080/admin/>
- API docs — <http://localhost:8080/api> (OpenAPI at `/openapi.json` on the API)

If 8080 is already taken on your machine, set `SEEBACH_WEB_PORT` — it moves the
host port only, and everything is served same-origin, so nothing else changes:

```sh
SEEBACH_WEB_PORT=8081 docker compose up --build
```

Compose runs with `SEEBACH_DEV_AUTH_ENABLED=true`, which takes the bearer token
as the staff subject with no verification. That is a development affordance and
it is **off by default** — a real deployment sets `SEEBACH_OIDC_ISSUER` instead.

Smoke-test a running stack, including one full round trip:

```sh
uv run python scripts/smoke.py http://localhost:8080
```

## Developing

```sh
uv venv && uv pip install -e ".[dev]"
pnpm install

uv run pytest                 # needs docker, or set SEEBACH_TEST_DATABASE_URL
uv run ruff check src tests
uv run mypy

pnpm -r run test
pnpm -r run typecheck
```

The API server and the two frontends, each against a locally running Postgres:

```sh
docker compose up -d postgres
SEEBACH_DEV_AUTH_ENABLED=true uv run uvicorn seebach.app:app --reload
pnpm run dev:hall     # :5173
pnpm run dev:admin    # :5174
```

Uvicorn defaults to :8000. If that one is taken too, pass `--port` and point the
Vite dev proxy at it with `SEEBACH_API_URL`:

```sh
SEEBACH_DEV_AUTH_ENABLED=true uv run uvicorn seebach.app:app --reload --port 8001
SEEBACH_API_URL=http://localhost:8001 pnpm run dev:hall
```

The TypeScript client is generated from the API and checked in, so a change to
a route shows up as a diff rather than as a runtime surprise:

```sh
uv run python scripts/dump_openapi.py && pnpm run api:types
```

## Layout

One folder per REST resource, so a route and the file that serves it are found
the same way. Each file holds one use case whole: request model, handler, route.

```
src/seebach/
  shared/          anemic models and enums -- the whole schema in one file
  interchange/     the manager port and its adapters -- vega.py today
  features/
    managers/      /api/managers                        adapters and what they cost
    tournaments/   /api/tournaments
    imports/       /api/tournaments/{id}/imports        preview + commit
    boards/        /api/tournaments/{id}/boards         the hall board list
    queue/         /api/tournaments/{id}/queue          what the arbiter owes
    devices/       /api/tournaments/{id}/devices        QR issue, list, revoke
    rounds/        /api/rounds/{id}                     release, export
    games/         /api/games/{id}                      claim, override, resolve
    audit.py locking.py scoping.py    shared mechanics, named for what they do
  platform/        mediator + pipeline, db, auth, migrations
  registry.py      every route module, in REST order
  trf/             the TRF library -- pure, no database, no framework
spikes/            M0: throwaway tooling for the manager round-trip spike
apps/hall          the player PWA: board list -> result -> confirm, offline-first
apps/admin         the arbiter app: import diff, queue, release, export
packages/api-client        generated from the OpenAPI schema
```

Commands and queries are still separate things -- `Command` opens a transaction
and dedupes on an idempotency key, `Query` does neither -- but that is carried
by the base class, not by which folder a file lives in.
