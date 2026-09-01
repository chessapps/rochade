"""M0, check 1 and 2: what did the manager actually give us?

Throwaway. Point it at any file a tournament manager exported and it reports
everything the M0 checklist asks for, in one pass.

    python spikes/inspect_export.py path/to/export.trf

The headline it exists to answer is the cheap one that gates all the others:
does this file contain a round that has been PAIRED BUT NOT PLAYED? A FIDE
rating export describes completed games. If that is all we get, there is no
open board for anyone to enter and the loop cannot start, whatever the import
side turns out to support.
"""

from __future__ import annotations

import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from seebach.trf import Dialect, TrfParseError, parse, serialize  # noqa: E402
from seebach.trf.results import RESULT_CODES  # noqa: E402

RECOGNISED = {"001", "012", "022", "032", "042", "052", "102", "XXR"}


def main(path: pathlib.Path) -> int:
    raw = path.read_bytes()
    print(f"file            {path.name}  ({len(raw)} bytes)")
    print(f"encoding        {_encoding(raw)}")

    text = _decode(raw)
    print(f"line endings    {'CRLF' if chr(13) + chr(10) in text else 'LF'}")
    print(f"lines           {len(text.splitlines())}")
    print()

    try:
        trf = parse(text)
    except TrfParseError as exc:
        print(f"PARSE FAILED    {exc}")
        print(f"  offending line: {exc.line!r}")
        return 1

    _records(text)
    _tournament(trf)
    _rounds(trf)
    _roundtrip(text, trf)
    _sample_line(trf)
    return 0


def _encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8 with BOM  <-- note: we strip nothing, check this survives"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not utf-8 (cp1252 or latin-1)"
    return "utf-8"


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _records(text: str) -> None:
    counts = Counter(line[:3] for line in text.splitlines() if line.strip())
    print("record types")
    for code, count in sorted(counts.items()):
        mark = "read " if code in RECOGNISED else "kept "
        note = "" if code in RECOGNISED else "  (retained verbatim, not modelled)"
        print(f"  {mark} {code!r:8} x{count}{note}")
    print()


def _tournament(trf: TrfFile) -> None:  # type: ignore[name-defined]
    print("tournament")
    print(f"  name          {trf.name!r}")
    print(f"  city / fed    {trf.city!r} / {trf.federation!r}")
    print(f"  dates         {trf.start_date!r} .. {trf.end_date!r}")
    print(f"  arbiter       {trf.chief_arbiter!r}")
    print(f"  XXR rounds    {trf.declared_rounds}")
    print(f"  players       {len(trf.players)}")
    if trf.unknown_result_codes:
        print(f"  UNKNOWN CODES {trf.unknown_result_codes}  <-- we do not model these")
    print()


def _rounds(trf: TrfFile) -> None:  # type: ignore[name-defined]
    print("rounds")
    open_rounds = []
    for round_no in range(1, trf.rounds_present + 1):
        pairings = trf.pairings(round_no)
        games = [p for p in pairings if not p.is_bye]
        byes = [p for p in pairings if p.is_bye]
        codes = Counter(p.white_result for p in games)
        blank = codes.get(" ", 0)
        bye_codes = sorted({p.white_result for p in byes})
        if blank == len(games) and games:
            open_rounds.append(round_no)
        print(
            f"  round {round_no}: {len(games)} games, {len(byes)} byes"
            f"  results={dict(codes)}  bye codes={bye_codes}"
        )
    print()

    print("CHECK 1 -- is there a paired-but-unplayed round?")
    if open_rounds:
        print(f"  YES: round(s) {open_rounds} have pairings and no results.")
        print("  This is the round players would enter. The loop can start.")
    else:
        print("  NO. Every round in this file already has results.")
        print("  We would import them all as CONFIRMED and there would be nothing")
        print("  to enter. Try exporting with the upcoming round selected, or fall")
        print("  back to the blank-PGN-headers path for the outbound leg.")
    print()


def _roundtrip(text: str, trf: TrfFile) -> None:  # type: ignore[name-defined]
    print("CHECK 4 -- lossless round trip on the untouched file")
    out = serialize(trf, Dialect.TRF16)
    if out == text:
        print("  PASS: parse -> serialize is byte-identical.")
        return
    print("  FAIL: the file changed. First differing lines:")
    shown = 0
    for i, (a, b) in enumerate(zip(text.splitlines(), out.splitlines(), strict=False), 1):
        if a != b and shown < 3:
            print(f"    line {i}")
            print(f"      in : {a!r}")
            print(f"      out: {b!r}")
            shown += 1
    if len(text) != len(out):
        print(f"    lengths differ: {len(text)} in, {len(out)} out")
    print()


def _sample_line(trf: TrfFile) -> None:  # type: ignore[name-defined]
    """Print one player row against a column ruler.

    TRF16 and TRF26 are both fixed-column formats. If a newer version has moved
    a field, this is where it shows up -- eyeball that rating, federation and
    the round blocks line up with the ruler.
    """
    if not trf.players:
        return
    player = trf.players[min(trf.players)]
    print("column check -- a player row against the TRF16 ruler")
    ruler_tens = "".join(str((i // 10) % 10) for i in range(1, len(player.raw) + 1))
    ruler_ones = "".join(str(i % 10) for i in range(1, len(player.raw) + 1))
    print(f"  {ruler_tens}")
    print(f"  {ruler_ones}")
    print(f"  {player.raw}")
    print()
    print("  expect: 5-8 rank | 10 sex | 11-13 title | 15-47 name | 49-52 rating")
    print("          54-56 fed | 58-68 FIDE id | 70-79 born | 81-84 pts | 86-89 rank")
    print("          then 10-wide round blocks from 92: opponent 92-95, colour 97, result 99")
    print()
    print(f"  we read: rank={player.start_rank} name={player.name!r} rating={player.rating}")
    print(f"           fed={player.federation!r} id={player.fide_id!r} pts={player.points}")
    print()
    print(f"  known result codes: {' '.join(sorted(c for c in RESULT_CODES if c.strip()))}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1])))
