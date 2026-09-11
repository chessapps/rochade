# Rochade

Digital result entry for chess tournaments that someone else is running.
Live at <https://rochade.app>.

An existing manager — Vega, Swiss-Manager — stays the tournament manager: it
owns setup, the player list, the pairings, the tiebreaks and the public view.
Rochade does the one thing it cannot — put a phone in every player's hand — and
hands the results back each round.

```
  manager                       Rochade                       manager
  ───────                       ───────                       ───────
  pair round N
  export      ──────────────▶  import, open round N
                                players enter results (hall PWA)
                                arbiter reviews + confirms
                               export      ─────────────────▶  import results
                                                               pair round N+1 ──▶ (loop)
```

Which manager is an adapter choice, not an architecture — see
`src/rochade/interchange/` (the code keeps its working name, `rochade`). Every adapter declares what it *cannot* do, and
ships `UNVERIFIED` until someone has watched it work.

| Manager | Status | Read more |
|---|---|---|
| **Swiss-Manager** | **verified** against 15.0.0.3 — its two text exports out, its pairing file back in, merges into the open tournament | [arbiter guide](docs/arbiter-guide-swiss-manager.md) · [what was observed](docs/m0-swiss-manager.md) |
| **Vega** | unverified — TRF16 both ways is what the manual says | [how to run the spike](spikes/README.md) |
| **Rochade (Gacrux engine)** | native — no files: players are entered here, rounds are paired and the table computed by the vendored [TieBreakServer](https://github.com/OttoMilvang/TieBreakServer) | [arbiter guide](docs/arbiter-guide-gacrux.md) · [what the engine does](docs/gacrux.md) |

See [PLAN.md](PLAN.md) for the design and the reasoning behind it.

## Running it

```sh
docker compose up --build
```

- landing page — <http://localhost:8092>: what this is, the way in for players
  (the QR, or the join code where that is switched on) and the link to the
  arbiter area. A phone that scanned a QR never sees it; it lands on its
  tournament's board list, which is the hall app behind the same URL
- arbiter app — <http://localhost:8092/admin/>
- API docs — <http://localhost:8092/api> (OpenAPI at `/openapi.json` on the API)
- Zitadel, the arbiters' sign-in — <http://localhost:8093> (console at `/ui/console`)

The first start takes a minute longer: Zitadel initialises itself in the
stack's Postgres and creates the first arbiter account, `admin@rochade.localhost`
with password `Password1!` (both from `.env.example`). Then a small setup
container registers the arbiter app with Zitadel and hands its client id to
the API, so the arbiter app's **Sign in** button just works. More arbiters are
added in Zitadel's console; passkeys are offered there and at sign-in.

If 8092 or 8093 is taken on your machine, set `ROCHADE_WEB_PORT` or the
`AUTH_*` variables in a `.env` (see `.env.example`); the ports move, and
everything is served same-origin, so nothing else changes.

Compose also runs with `ROCHADE_DEV_AUTH_ENABLED=true`: beside Zitadel, a
bearer that is not a JWT is taken as the staff subject with no verification,
which is how the smoke and browser scripts sign in. That is a development
affordance and it is **off by default**. The host ports and both dev flags live
in `docker-compose.override.yml`, which compose merges in on its own;
`docker-compose.yml` alone is production-safe.

It also runs with `ROCHADE_DEVICE_JOIN_ENABLED=true`, which lets a phone admit
itself by typing a tournament's six-character join code on the landing page
instead of scanning the QR. The arbiter opens and closes it under **Devices**,
and it grants exactly what the QR grants — so it is off by default too, and the
landing page then shows no code field at all.

Smoke-test a running stack, including one full round trip:

```sh
uv run python scripts/smoke.py http://localhost:8092
```

Putting the stack on a Linux box behind a shared Caddy, with TLS and room for
other stacks on the same machine, is one command once the box is prepared:
see [deploy/README.md](deploy/README.md).
Every commit on `main` that passes CI deploys itself from GitHub Actions; the
same file explains the secrets and who may merge to `main`.

The same round through the arbiter app in a real browser — screens, dialogs,
polling, the download, phone widths — using the Edge or Chrome already on the
machine (`ROCHADE_BROWSER=chrome` for Chrome):

```sh
node scripts/admin_flow.mjs http://localhost:8092
```

And the sign-in itself, from no credential through Zitadel's login page and
back, then out again:

```sh
node scripts/login_flow.mjs http://localhost:8092
```

And an arbiter who never gets a password: invited, a passkey registered from
the link, signed in with that alone. Needs the setup machine user's token:

```sh
ZITADEL_PAT=$(docker compose exec zitadel cat /zitadel/bootstrap/setup.pat) node scripts/passkey_flow.mjs http://localhost:8092
```

## The arbiter's day

Sign in at `/admin/` with a staff token, create the tournament, and issue a QR
code under **Devices** — print it as a poster or show it on screen. Then each
round is the same five minutes, and the section card on the tournament home
always names the next step:

1. Pair the round in Swiss-Manager or Vega and export it — Swiss-Manager
   writes the players and the pairings as two text files; **Import round N**
   shows what they change before anything is written.
2. Players enter results on their phones — scanning the QR, or typing the join
   code when a camera will not do. The round board updates every few
   seconds and opens on **Attention**: the boards with no result, and the ones
   two phones disagree about, with which phone said what. Forfeits are one tap
   further away; `1` `=` `0` on the keyboard work too.
3. **Release**, then **Export for Swiss-Manager**. The file downloads, the round
   freezes, and the card at the top says which menu to use — with the file a
   click away should the download have gone astray.

`docs/arbiter-guide-swiss-manager.md` has the Swiss-Manager menus for each step.

A tournament on **Rochade (Gacrux engine)** skips the files: enter the players
under **Players**, **Pair round N** from the section card (the preview shows
the boards first), release, and pair the next one. The standings are computed
at every release. `docs/arbiter-guide-gacrux.md` walks through it.

## Developing

```sh
uv venv && uv pip install -e ".[dev]"
pnpm install

uv run pytest                 # needs docker, or set ROCHADE_TEST_DATABASE_URL
uv run ruff check src tests
uv run mypy

pnpm -r run test
pnpm -r run typecheck
```

The API server and the two frontends, each against a locally running Postgres.
The API applies the migrations itself when it starts, so the database only has
to exist (`ROCHADE_MIGRATE_ON_START=false` turns that off for a deployment that
migrates as its own step). Settings are read from the environment or from a
`.env` in the repo root, `ROCHADE_DATABASE_URL` among them:

```sh
docker compose up -d postgres            # or any Postgres with a database named rochade
ROCHADE_DEV_AUTH_ENABLED=true uv run uvicorn rochade.app:app --reload
pnpm run dev:hall     # :5173
pnpm run dev:admin    # :5174/admin/
```

Uvicorn defaults to :8000. If that one is taken too, pass `--port` and point the
Vite dev proxy at it with `ROCHADE_API_URL`:

```sh
ROCHADE_DEV_AUTH_ENABLED=true uv run uvicorn rochade.app:app --reload --port 8001
ROCHADE_API_URL=http://localhost:8001 pnpm run dev:hall
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
src/rochade/
  shared/          anemic models and enums -- the whole schema in one file
  interchange/     the manager port and its adapters -- vega.py today
  features/
    managers/      /api/managers                        adapters and what they cost
    tournaments/   /api/tournaments
    imports/       /api/tournaments/{id}/imports        preview + commit
    boards/        /api/tournaments/{id}/boards         the hall board list
    queue/         /api/tournaments/{id}/queue          what the arbiter owes
    devices/       /api/tournaments/{id}/devices        QR issue, list, revoke, remove
    rounds/        /api/rounds/{id}                     release, export
    games/         /api/games/{id}                      claim, override, resolve
    audit.py locking.py scoping.py    shared mechanics, named for what they do
  platform/        mediator + pipeline, db, auth, migrations
  registry.py      every route module, in REST order
  trf/             the TRF library -- pure, no database, no framework
  gacrux/          the pairing engine: a wrapper over the vendored TieBreakServer
spikes/            M0: throwaway tooling for the manager round-trip spike
apps/hall          the player PWA: board list -> result (one tap sends) -> done, offline-first
apps/admin         the arbiter app: tournament home, round board, import wizard, phones
packages/api-client        generated from the OpenAPI schema
```

Commands and queries are still separate things -- `Command` opens a transaction
and dedupes on an idempotency key, `Query` does neither -- but that is carried
by the base class, not by which folder a file lives in.

## Credits

Pairings and tie-breaks in tournaments that Rochade runs itself are computed
by [TieBreakServer](https://github.com/OttoMilvang/TieBreakServer), the
**Gacrux pairing** and **Gacrux tiebreak** reference implementations by IA
Otto Milvang, © 2024 FIDE, MIT licence. See <https://www.gacrux.no>. A
verbatim copy lives under `src/rochade/gacrux/vendor/tiebreakserver/`; the
licence text is in `NOTICE`.

Rochade is not endorsed by FIDE.
