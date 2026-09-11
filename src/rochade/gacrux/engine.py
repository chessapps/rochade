"""Drive the vendored TieBreakServer command-line tools.

Why a subprocess and not an import: upstream is a set of flat scripts that
import each other by bare name (`from helpers import *`), written to be run
from their own directory. Running them that way, in a child process, is the
one mode upstream itself exercises; importing them into our package would
mean patching `sys.path` and living with their module-level state.

Why files and not stdout: the tools write JSON to a path given with `-o`,
and reading it back from a file sidesteps every console-encoding question a
Windows development box would otherwise raise.

What a failure looks like: the tools exit 0 whatever happened and put the
verdict in `status.code` with a list of messages beside it. Everything that
is not `code == 0` becomes an `EngineError` carrying those messages, so a
handler can show the arbiter what the engine actually said -- minus the
paths of our own scratch files, which go to the log instead.

The child gets a minimal environment and Python's `-E -s -B` flags, so
nothing on the server's `PYTHONPATH` or in a user site directory can shadow
the vendored modules or `networkx`, and no `.pyc` files land in the package.
At most a couple of engine processes run at once: each one is a fresh
interpreter, and a burst of previews must not crowd out the hall's claims.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rochade.platform.config import settings

log = logging.getLogger(__name__)

PACKAGED_ENGINE = pathlib.Path(__file__).resolve().parent / "vendor" / "tiebreakserver"

PAIRING_TOOL = "pairingchecker.py"
TIEBREAK_TOOL = "tiebreakchecker.py"

#: How many engine processes may run at once, server-wide.
_SLOTS = threading.BoundedSemaphore(2)

#: What the child process is allowed to see of the environment.
_ENV_KEYS = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR", "HOME", "LANG", "LC_ALL")


class EngineError(Exception):
    """The engine did not produce a result.

    `errors` is what the engine itself reported, in its words; `code` is its
    status code (5xx are its own failures, 0 never lands here). `code` is
    None when the failure was ours -- a timeout, a crash, a missing install --
    which a handler reports as the service being unavailable rather than as
    something wrong with the request.
    """

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        errors: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.errors = list(errors)

    @property
    def ours(self) -> bool:
        return self.code is None


@dataclass(frozen=True, slots=True)
class EnginePair:
    """One board as the engine pairs it, by TRF starting rank. `black` is None for the bye."""

    white: int
    black: int | None

    @property
    def is_bye(self) -> bool:
        return self.black is None


@dataclass(frozen=True, slots=True)
class EngineStanding:
    """One player's place: rank, then the tie-break values in the order asked for.

    The first value is always the points, because the spec handed to the
    engine always starts with `PTS`. Ties share a rank, as FIDE tables do.
    """

    start_rank: int
    rank: int
    #: None where the engine has no value: a rating-based tie-break for a
    #: player who has met nobody rated, for instance.
    scores: tuple[float | None, ...]

    @property
    def points(self) -> float:
        return self.scores[0] or 0.0 if self.scores else 0.0

    @property
    def tiebreaks(self) -> tuple[float | None, ...]:
        return self.scores[1:]


def engine_dir() -> pathlib.Path:
    """Where the engine lives: the packaged copy unless `ROCHADE_GACRUX_DIR` says otherwise."""
    configured = settings().gacrux_dir
    return pathlib.Path(configured) if configured else PACKAGED_ENGINE


def pair(
    trf_text: str,
    *,
    round_no: int,
    top_colour: str | None = None,
    unpaired: Sequence[int] = (),
    engine: pathlib.Path | None = None,
    timeout: float | None = None,
) -> list[EnginePair]:
    """Pair `round_no` of the tournament in `trf_text` with the FIDE Dutch system.

    `top_colour` ("white" | "black") only decides anything in round 1; from
    then on the engine reads it off the first round's boards. `unpaired` are
    starting ranks to leave out of this round entirely.
    """
    if round_no < 1:
        raise ValueError(f"round number must be >= 1, got {round_no}")
    if top_colour not in (None, "white", "black"):
        raise ValueError(f"top colour must be 'white' or 'black', got {top_colour!r}")

    args = ["-n", str(round_no), "-p", "-m", "dutch"]
    if top_colour is not None:
        args += ["-t", top_colour[0]]
    if unpaired:
        args += ["-u", *(str(int(rank)) for rank in unpaired)]

    result = _run(PAIRING_TOOL, trf_text, args, engine=engine, timeout=timeout)
    try:
        payload = result["pairingResult"]
        if payload["round"] != round_no:
            raise EngineError(
                f"the pairing engine paired round {payload['round']}, not round {round_no}"
            )
        return [
            EnginePair(white=int(entry[0]), black=int(entry[1]) if int(entry[1]) > 0 else None)
            for entry in payload["pairs"]
        ]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise EngineError("the pairing engine returned no pairing") from exc


def standings(
    trf_text: str,
    *,
    tiebreaks: Sequence[str],
    after_round: int | None = None,
    engine: pathlib.Path | None = None,
    timeout: float | None = None,
) -> list[EngineStanding]:
    """Rank the players in `trf_text` by `tiebreaks`, Swiss rules.

    `tiebreaks` is the engine's own spec syntax (`PTS`, `BH/C1`, ...), and it
    must start with `PTS`: see `rochade.gacrux.tiebreaks`. `after_round`
    limits the arithmetic to the rounds up to and including it.
    """
    if not tiebreaks or tiebreaks[0] != "PTS":
        raise ValueError("the tie-break spec must start with PTS")
    if any(not code or code.startswith("-") for code in tiebreaks):
        raise ValueError("a tie-break code cannot be empty or start with '-'")

    args = ["-s"]
    if after_round is not None:
        args += ["-n", str(int(after_round))]
    args += ["-t", *tiebreaks]

    result = _run(TIEBREAK_TOOL, trf_text, args, engine=engine, timeout=timeout)
    try:
        rows = [
            EngineStanding(
                start_rank=int(entry["cid"]),
                rank=int(entry["rank"]),
                scores=tuple(
                    None if value is None else float(value)
                    for value in entry.get("tiebreakScore", [])
                ),
            )
            for entry in result["tiebreakResult"]["competitors"]
        ]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise EngineError("the tie-break engine returned no standings") from exc
    return sorted(rows, key=lambda row: (row.rank, row.start_rank))


def _run(
    tool: str,
    trf_text: str,
    args: Sequence[str],
    *,
    engine: pathlib.Path | None,
    timeout: float | None,
) -> dict[str, Any]:
    home = engine or engine_dir()
    script = home / tool
    if not script.is_file():
        log.error("the pairing engine is not installed: %s does not exist", script)
        raise EngineError("the pairing engine is not installed on this server")
    limit = timeout if timeout is not None else settings().gacrux_timeout

    with tempfile.TemporaryDirectory(prefix="gacrux-", ignore_cleanup_errors=True) as scratch:
        inbox = pathlib.Path(scratch) / "in.trf"
        outbox = pathlib.Path(scratch) / "out.json"
        inbox.write_bytes(trf_text.encode("utf-8"))

        command = [
            sys.executable,
            "-E",
            "-s",
            "-B",
            "-X",
            "utf8",
            str(script),
            "-i",
            str(inbox),
            "-o",
            str(outbox),
            "-f",
            "TRF",
            "-b",
            "utf-8",
            *args,
        ]
        env = {key: os.environ[key] for key in _ENV_KEYS if key in os.environ}
        try:
            with _SLOTS:
                completed = subprocess.run(
                    command,
                    cwd=home,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=limit,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            log.error("%s did not finish within %.0fs", tool, limit)
            raise EngineError(
                f"the pairing engine did not finish within {limit:g} seconds"
            ) from exc

        if completed.returncode != 0:
            log.error("%s crashed (exit %s): %s", tool, completed.returncode, completed.stderr)
            raise EngineError(f"the pairing engine crashed (exit code {completed.returncode})")
        if not outbox.is_file():
            log.error("%s wrote no output: %s", tool, completed.stderr)
            raise EngineError("the pairing engine wrote no output")
        try:
            result = json.loads(outbox.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise EngineError("the pairing engine wrote something that is not JSON") from exc
        private = (str(inbox), str(outbox), str(home))

    if not isinstance(result, dict):
        raise EngineError("the pairing engine wrote something unexpected")
    status = result.get("status") or {}
    try:
        code = int(status.get("code", 0) or 0)
    except (TypeError, ValueError, AttributeError) as exc:
        raise EngineError("the pairing engine wrote something unexpected") from exc
    if code != 0:
        raw = [str(line) for line in status.get("error", [])]
        log.warning("%s refused (status %s): %s", tool, code, raw)
        errors = [_redact(line, private) for line in raw]
        summary = errors[0] if errors else f"status {code}"
        raise EngineError(f"the pairing engine refused: {summary}", code=code, errors=errors)
    return result


def _redact(line: str, private: Sequence[str]) -> str:
    """The engine's message without the paths of our scratch files."""
    for path in private:
        line = line.replace(path, "<file>")
    return line
