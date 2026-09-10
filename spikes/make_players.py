"""Generate a Swiss-Manager player list ("Spielerdaten (Text-File)") of any size.

Swiss-Manager imports its own text exports through `Extras -> Daten
Import/Export...`, import side, `Spielerdaten (Text-File)`. This writes that
file: the same semicolon columns the fixture `players_round1.txt` has, one
invented player per row, ratings descending so the start numbers are the
rating order Swiss-Manager would give them anyway.

    uv run python spikes/make_players.py --players 40

writes `spikes/out/players-40.txt`. Import it into a fresh Swiss-Manager
tournament, pair round 1, and export Spielerdaten and Spielerauslosung from
there for Rochade.

The standings columns (`Pkt`, `Wtg1..6`, `Rang`) are left empty: this is an
entry list before the first round, and Swiss-Manager fills them itself.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from rochade.swiss_manager.player_file import parse_player_file

CRLF = chr(13) + chr(10)

HEADER = (
    "Nr;Name;Titel;Identnr;EloNat;EloInt;Geburt;Fed;Sex;Typ;Gr;KlubNr;Klub;FideIdent;"
    "Quelle;Pkt;Wtg1;Wtg2;Wtg3;Wtg4;Wtg5;Wtg6;Rang;Nachname;Vorname;Atitel"
)

SURNAMES = [
    "Baumann",
    "Chen",
    "Dubois",
    "Müller",
    "Fischer",
    "Gruber",
    "Huber",
    "Iten",
    "Jenni",
    "Keller",
    "Lehmann",
    "Meier",
    "Novak",
    "Odermatt",
    "Peter",
    "Quaranta",
    "Rossi",
    "Schmid",
    "Tanner",
    "Ulrich",
    "Vogel",
    "Weber",
    "Zimmermann",
    "Ammann",
    "Bianchi",
    "Caduff",
    "Egli",
    "Frei",
    "Gerber",
    "Hess",
    "Imhof",
    "Jäger",
    "Koch",
    "Lüthi",
    "Marti",
    "Nussbaumer",
    "Oberholzer",
    "Pfister",
    "Roth",
    "Steiner",
    "Thommen",
    "Urech",
    "Vetter",
    "Wyss",
    "Zanetti",
]
GIVEN_M = [
    "Lukas",
    "Wei",
    "Tobias",
    "Jonas",
    "Marco",
    "Rafael",
    "Nico",
    "Samuel",
    "Elias",
    "David",
    "Leon",
    "Matteo",
    "Noah",
    "Jan",
    "Simon",
    "Fabio",
    "Luca",
    "Timo",
]
GIVEN_W = [
    "Anna",
    "Elise",
    "Sarah",
    "Nadia",
    "Lea",
    "Mia",
    "Livia",
    "Sophie",
    "Nina",
    "Laura",
    "Julia",
    "Emma",
    "Chiara",
    "Alina",
    "Elena",
]
FEDERATIONS = ["SUI"] * 6 + ["GER", "AUT", "FRA", "ITA"]


def player(number: int, rating: int, rng: random.Random) -> list[str]:
    woman = rng.random() < 0.3
    surname = SURNAMES[(number - 1) % len(SURNAMES)]
    if number > len(SURNAMES):
        surname = f"{surname}-{(number - 1) // len(SURNAMES) + 1}"
    given = rng.choice(GIVEN_W if woman else GIVEN_M)
    title = ""
    if rating >= 2400:
        title = "WGM" if woman else "IM"
    elif rating >= 2300:
        title = "WIM" if woman else "FM"
    elif rating >= 2200:
        title = "WFM" if woman else "CM"
    born = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1958, 2012)}"
    federation = rng.choice(FEDERATIONS)
    cells = dict.fromkeys(HEADER.split(";"), "")
    cells.update(
        {
            "Nr": str(number),
            "Name": f"{surname} {given}",
            "Titel": title,
            "EloNat": "0",
            "EloInt": str(rating),
            "Geburt": born,
            "Fed": federation,
            "Sex": "W" if woman else "",
            "KlubNr": "0",
            # No FIDE id on purpose: invented players must not match a real list.
            "FideIdent": "0",
            "Nachname": surname,
            "Vorname": given,
        }
    )
    return [cells[name] for name in HEADER.split(";")]


def build(count: int, seed: int) -> str:
    rng = random.Random(seed)
    top = 2450
    ratings = sorted((top - rng.randint(0, 900) for _ in range(count)), reverse=True)
    rows = [HEADER]
    rows += [";".join(player(n, rating, rng)) for n, rating in enumerate(ratings, start=1)]
    return CRLF.join(rows) + CRLF


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--players", type=int, default=40, help="how many players (default 40)")
    parser.add_argument("--seed", type=int, default=1, help="random seed; same seed, same file")
    parser.add_argument(
        "--out", type=pathlib.Path, help="where to write (default spikes/out/players-N.txt)"
    )
    args = parser.parse_args()
    if args.players < 2:
        parser.error("a tournament needs at least two players")

    text = build(args.players, args.seed)
    parsed = parse_player_file(text)
    assert [p.start_number for p in parsed] == list(range(1, args.players + 1))
    assert all(p.rating for p in parsed) and all(p.points is None for p in parsed)

    out = args.out or pathlib.Path(__file__).parent / "out" / f"players-{args.players}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8, CRLF, no BOM: what Swiss-Manager 15 wrote in the fixture.
    out.write_bytes(text.encode("utf-8"))
    print(f"wrote {out.resolve()}  ({args.players} players, {out.stat().st_size} bytes)")
    first, last = parsed[0], parsed[-1]
    print(f"  top: {first.name} {first.rating}, bottom: {last.name} {last.rating}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
