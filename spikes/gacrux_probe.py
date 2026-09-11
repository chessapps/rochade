"""Run the vendored Gacrux engine on the golden TRF fixtures and print what it says.

The Phase 0 spike for the native pairing program. It does what
`rochade.gacrux.engine` does, only by hand and with the whole JSON shown, so
that a refresh of the vendored engine can be compared against
`docs/gacrux.md` line by line.

    uv run python spikes/gacrux_probe.py [--engine DIR]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_ENGINE = ROOT / "src" / "rochade" / "gacrux" / "vendor" / "tiebreakserver"

PROBES: list[tuple[str, str, str, list[str]]] = [
    (
        "pair round 1 of the seed, white on top",
        "round1_pairings.trf",
        "pairingchecker.py",
        ["-n", "1", "-p", "-m", "dutch", "-t", "w"],
    ),
    (
        "pair round 1 of the seed, black on top",
        "round1_pairings.trf",
        "pairingchecker.py",
        ["-n", "1", "-p", "-m", "dutch", "-t", "b"],
    ),
    (
        "pair round 3 of the messy seed (9 is absent: Z)",
        "round3_messy.trf",
        "pairingchecker.py",
        ["-n", "3", "-p", "-m", "dutch"],
    ),
    (
        "pair round 3 without player 8: a bye appears",
        "round3_messy.trf",
        "pairingchecker.py",
        ["-n", "3", "-p", "-m", "dutch", "-u", "8"],
    ),
    ("pair beyond XXR", "round3_messy.trf", "pairingchecker.py", ["-n", "6", "-p", "-m", "dutch"]),
    (
        "standings after round 2",
        "round3_messy.trf",
        "tiebreakchecker.py",
        ["-s", "-n", "2", "-t", "PTS", "BH/C1", "BH", "SB"],
    ),
    (
        "standings, every offered tie-break",
        "round3_messy.trf",
        "tiebreakchecker.py",
        [
            "-s",
            "-n",
            "2",
            "-t",
            "PTS",
            "BH/C1",
            "BH",
            "BH/M1",
            "SB",
            "SB/C1",
            "DE",
            "WIN",
            "WON",
            "BPG",
            "BWG",
            "PS",
            "KS",
            "AOB",
            "ARO",
            "ARO/C1",
            "TPR",
        ],
    ),
]


def run(engine: pathlib.Path, fixture: str, tool: str, args: list[str]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as scratch:
        out = pathlib.Path(scratch) / "out.json"
        command = [
            sys.executable,
            str(engine / tool),
            "-i",
            str(FIXTURES / fixture),
            "-o",
            str(out),
            "-f",
            "TRF",
            "-b",
            "utf-8",
            *args,
        ]
        completed = subprocess.run(command, cwd=engine, capture_output=True, text=True)
        if completed.stderr:
            print("  stderr:", completed.stderr.strip())
        print("  exit code:", completed.returncode)
        return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=pathlib.Path, default=DEFAULT_ENGINE)
    options = parser.parse_args()

    print("engine:", options.engine)
    for title, fixture, tool, args in PROBES:
        print(f"\n== {title}\n   {tool} {' '.join(args)}  <  {fixture}")
        result = run(options.engine, fixture, tool, args)
        print("  status:", result.get("status"))
        for key in ("pairingResult", "tiebreakResult"):
            if key in result:
                payload = dict(result[key])  # type: ignore[call-overload]
                payload.pop("tiebreaks", None)
                print(f"  {key}:", json.dumps(payload, indent=None))


if __name__ == "__main__":
    main()
