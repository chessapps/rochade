"""Generates the golden TRF fixtures. Run manually; the outputs are checked in."""

import pathlib


def player(rank, sex, title, name, rating, fed, fide, birth, points, srank, rounds):
    line = list(" " * 89)
    line[0:3] = "001"
    line[4:8] = f"{rank:4d}"
    line[9:10] = sex.ljust(1)
    line[10:13] = title.ljust(3)
    line[14:47] = name.ljust(33)[:33]
    line[48:52] = f"{rating:4d}" if rating else "    "
    line[53:56] = fed.ljust(3)
    line[57:68] = fide.rjust(11)
    line[69:79] = birth.ljust(10)
    line[80:84] = f"{points:4.1f}"
    line[85:89] = f"{srank:4d}"
    s = "".join(line)
    for opp, col, res in rounds:
        s += "  " + (f"{opp:4d}" if opp else "0000") + " " + col + " " + res
    return s


def build(header, players):
    return "\r\n".join(header + players) + "\r\n"


HERE = pathlib.Path(__file__).parent

r1_header = [
    "012 Seebach Open 2026",
    "022 Seebach",
    "032 SUI",
    "042 2026/03/14",
    "052 2026/03/15",
    "062 8",
    "072 8",
    "092 Individual: Swiss-System",
    "102 Muster, Anna",
    "122 90 min + 30 sec increment",
    "XXR 5",
    "XXC white1",
]
r1_players = [
    player(
        1,
        "m",
        "FM",
        "Baumann, Lukas",
        2201,
        "SUI",
        "1300001",
        "1990/04/02",
        0.0,
        1,
        [(5, "w", " ")],
    ),
    player(2, "m", "", "Chen, Wei", 2150, "SUI", "1300002", "1995/11/23", 0.0, 2, [(6, "b", " ")]),
    player(
        3,
        "w",
        "WFM",
        "Dubois, Elise",
        2098,
        "FRA",
        "1300003",
        "2001/07/09",
        0.0,
        3,
        [(7, "w", " ")],
    ),
    player(
        4, "m", "", "Egger, Tobias", 2044, "AUT", "1300004", "1988/01/30", 0.0, 4, [(8, "b", " ")]
    ),
    player(
        5, "m", "", "Fischer, Jonas", 1987, "GER", "1300005", "2003/05/17", 0.0, 5, [(1, "b", " ")]
    ),
    player(
        6, "w", "", "Gruber, Sarah", 1922, "SUI", "1300006", "1999/09/12", 0.0, 6, [(2, "w", " ")]
    ),
    player(
        7, "m", "", "Huber, Marco", 1870, "SUI", "1300007", "1975/12/01", 0.0, 7, [(3, "b", " ")]
    ),
    player(
        8, "w", "", "Iten, Nadia", 1804, "SUI", "1300008", "2007/02/28", 0.0, 8, [(4, "w", " ")]
    ),
]
(HERE / "round1_pairings.trf").write_bytes(build(r1_header, r1_players).encode("utf-8"))

r3_header = [
    "012 Seebach Open 2026",
    "022 Seebach",
    "032 SUI",
    "042 2026/03/14",
    "052 2026/03/15",
    "062 9",
    "092 Individual: Swiss-System",
    "102 Muster, Anna",
    "XXR 5",
]
# 9 players: byes, forfeits, a withdrawal (player 9 has Z in round 3).
r3_players = [
    player(
        1,
        "m",
        "FM",
        "Baumann, Lukas",
        2201,
        "SUI",
        "1300001",
        "1990/04/02",
        2.0,
        1,
        [(5, "w", "1"), (2, "b", "1"), (3, "w", " ")],
    ),
    player(
        2,
        "m",
        "",
        "Chen, Wei",
        2150,
        "SUI",
        "1300002",
        "1995/11/23",
        1.0,
        4,
        [(6, "b", "1"), (1, "w", "0"), (4, "b", " ")],
    ),
    player(
        3,
        "w",
        "WFM",
        "Dubois, Elise",
        2098,
        "FRA",
        "1300003",
        "2001/07/09",
        1.5,
        2,
        [(7, "w", "="), (8, "b", "1"), (1, "b", " ")],
    ),
    player(
        4,
        "m",
        "",
        "Egger, Tobias",
        2044,
        "AUT",
        "1300004",
        "1988/01/30",
        1.5,
        3,
        [(0, "-", "H"), (9, "w", "1"), (2, "w", " ")],
    ),
    player(
        5,
        "m",
        "",
        "Fischer, Jonas",
        1987,
        "GER",
        "1300005",
        "2003/05/17",
        1.0,
        5,
        [(1, "b", "0"), (7, "w", "+"), (6, "w", " ")],
    ),
    player(
        6,
        "w",
        "",
        "Gruber, Sarah",
        1922,
        "SUI",
        "1300006",
        "1999/09/12",
        0.0,
        8,
        [(2, "w", "0"), (0, "-", "Z"), (5, "b", " ")],
    ),
    player(
        7,
        "m",
        "",
        "Huber, Marco",
        1870,
        "SUI",
        "1300007",
        "1975/12/01",
        0.5,
        6,
        [(3, "b", "="), (5, "b", "-"), (8, "w", " ")],
    ),
    player(
        8,
        "w",
        "",
        "Iten, Nadia",
        1804,
        "SUI",
        "1300008",
        "2007/02/28",
        0.5,
        7,
        [(0, "-", "U"), (3, "w", "0"), (7, "b", " ")],
    ),
    player(
        9,
        "m",
        "",
        "Jenni, Rafael",
        1755,
        "SUI",
        "1300009",
        "2010/06/05",
        0.0,
        9,
        [(0, "-", "Z"), (4, "b", "0"), (0, "-", "Z")],
    ),
]
(HERE / "round3_messy.trf").write_bytes(build(r3_header, r3_players).encode("utf-8"))
print("wrote fixtures")
