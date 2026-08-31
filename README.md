# Seebach

Digital result entry for chess tournaments that Vega runs.

Vega stays the tournament manager: it owns setup, the player list, the
pairings, the tiebreaks and the public view. Seebach does the one thing Vega
cannot — put a phone in every player's hand — and hands the results back as a
TRF file each round.

```
  Vega                          Seebach                        Vega
  ─────                         ───────                        ─────
  pair round N
  export TRF  ──────────────▶  import, open round N
                                players enter results (hall PWA)
                                arbiter reviews + confirms
                               export TRF  ─────────────────▶  import results
                                                               pair round N+1 ──▶ (loop)
```

The file round-trip *is* the integration, so nothing here is Vega-specific:
any TRF-speaking manager works the same way.

See [PLAN.md](PLAN.md) for the design and the reasoning behind it.

## Running it

```sh
docker compose up --build
```

- hall app — <http://localhost:8080>
- arbiter app — <http://localhost:8080/admin/>
- API docs — <http://localhost:8080/api> (OpenAPI at `/openapi.json` on the API)

Compose runs with `SEEBACH_DEV_AUTH_ENABLED=true`, which takes the bearer token
as the staff subject with no verification. That is a development affordance and
it is **off by default** — a real deployment sets `SEEBACH_OIDC_ISSUER` instead.

Smoke-test a running stack, including one full round trip:

```sh
python scripts/smoke.py http://localhost:8080
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

The TypeScript client is generated from the API and checked in, so a change to
a route shows up as a diff rather than as a runtime surprise:

```sh
uv run python scripts/dump_openapi.py && pnpm run api:types
```

## Layout

```
src/seebach/
  shared/      anemic models and enums -- the whole schema in one file
  commands/    one file per state change; each owns its own preconditions
  queries/     one file per read shape
  platform/    mediator + pipeline, db, auth, migrations
  trf/         the TRF library -- pure, no database, no framework
apps/hall      the player PWA: board list -> result -> confirm, offline-first
apps/admin     the arbiter app: import diff, queue, release, export
packages/api-client   generated from the OpenAPI schema
```
