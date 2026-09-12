# Live: the public view of a tournament

Design agreed 2026-09-11. Players, visitors and the public follow a
tournament: pairings, results as they come in, standings, and every game of
one player. No sign-in.

## Decisions

- **The arbiter publishes.** A tournament is invisible until its owner or
  arbiter switches it on; it then has a short public URL. Switching it off
  hides it at once. Test tournaments never leak.
- **The watch list lives in the browser**, keyed so a later visitor account
  could hold the same list. No accounts now.
- **Polling, not push.** 20 seconds while the tab is visible; responses are
  cacheable for 15 seconds, so many visitors cost one query per endpoint per
  cache window.
- **The front door lists every published tournament**, current ones first.
- **Nothing is computed.** Points, tie-breaks and ranks are the manager's
  numbers as imported; when there are none, the page shows games without a
  total.

## API

`Tournament` gains `published: bool` and `slug: str | None` (unique, from the
name, editable). One command, `PublishTournament(tournament_id, published,
slug)`, at arbiter access. `GetTournament` returns both fields.

Public reads under `/api/public/`, all `Access.PUBLIC`, all `Cache-Control:
public, max-age=15`:

| Route | Returns |
| --- | --- |
| `GET /public/tournaments` | published tournaments: slug, name, city, dates, sections with rounds held and the state of the newest |
| `GET /public/tournaments/{slug}` | the tournament: sections, each with its rounds (number, state), players held, standings round, tie-break names |
| `GET /public/tournaments/{slug}/sections/{section_id}/rounds/{n}` | boards: board, white and black (start rank, name, title, rating), result as shown (`1-0`, `½-½`, `0-1`, forfeits, bye), `state` |
| `GET /public/tournaments/{slug}/sections/{section_id}/standings` | the section's standings rows, as `GetStandings` gives them |
| `GET /public/tournaments/{slug}/sections/{section_id}/players/{start_rank}` | the player and every game: round, colour, opponent (start rank, name), result, `state` |

`state` on a game is one of `pending` (no result), `preliminary` (claimed or
disputed: the two claims are never exposed, only the standing white result),
`confirmed` (confirmed by the arbiter, or the round released). An unpublished
or unknown slug is a plain 404, the same for both.

## App: `apps/live`

Vite + React + TypeScript + Tailwind, `base: "/live/"`, the shared API
client, react-router. No PWA, no sign-in.

| Route | Screen |
| --- | --- |
| `/live/` | published tournaments, cards |
| `/live/:slug` | the tournament; section tabs when more than one; per section: Pairings (newest round, round picker), Standings, Players |
| `/live/:slug/s/:sectionId/p/:startRank` | the player: header, rank and points when standings exist, the game list, Watch toggle |

Watch list: `localStorage` key `rochade.live.watch`, a list of
`{slug, sectionId, startRank, name}`. Shown as a strip on the tournament page
with each watched player's latest result while a round is in play.

Polling: round and standings queries refetch every 20 s while
`document.visibilityState === "visible"`; none once every round of the
tournament is exported. Stale data stays on screen with a "last updated" line.

## Edge cases

- Unknown or unpublished slug: "no such tournament", nothing more.
- A section without rounds: player list and "not paired yet".
- A re-import can replace the player list; start ranks are the manager's and
  stable, so watch links survive. A vanished rank: "no longer in this
  section", link to the list.
- Standings behind the newest round: the table says which round it is after.

## Tests

- Handlers: each public query; unpublished is 404; a disputed board exposes
  one preliminary result and no claims; publish needs arbiter access.
- App: list, a round with preliminary and confirmed results, the player page
  with its games and the watch toggle, the watch list after a reload.
- The contract check in CI for the generated client.

## Order

1. Migration, `PublishTournament`, the switch on the tournament home.
2. The public queries and tests; regenerate the client.
3. `apps/live`: list and tournament page with pairings and standings.
4. Player page and watch list.
5. Polling, cache headers, README and guides.

One PR per step.
