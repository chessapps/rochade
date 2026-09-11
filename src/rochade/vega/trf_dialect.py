"""The TRF Vega's importer actually reads, made from the TRF16 we write.

Two things Vega 12.1.8 does that the TRF16 specification does not say:

- **It counts bytes, not characters.** A UTF-8 name with an umlaut is one
  character longer in bytes, and Vega reads the rating from the shifted
  column -- then never returns from the import (the process sits at 100 %
  and grows past a gigabyte). Padding the name field to 33 *bytes* fixes it,
  and Vega then shows the umlaut correctly. Windows-1252 imports without a
  hang but shows mojibake, so the encoding stays UTF-8.
- **It ignores ``XXR``.** The round count comes from its own ``142 N`` line;
  without it the tournament has as many rounds as the file has, and the
  arbiter is told "The Tournament is finished" when they try to pair.

Everything else -- results, byes, forfeits, points -- it takes as written.
"""

from __future__ import annotations

from rochade.trf import columns

NAME_BYTES = columns.NAME.stop - columns.NAME.start


def to_vega(text: str, *, declared_rounds: int | None) -> str:
    """Byte-pad the name fields and carry the round count the way Vega reads it."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    out: list[str] = []
    rounds_written = False
    for line in lines:
        if line.startswith("142 "):
            if declared_rounds is not None:
                line = f"142 {declared_rounds}"
            rounds_written = True
        if line.startswith("001 ") and not rounds_written:
            if declared_rounds is not None:
                out.append(f"142 {declared_rounds}")
            rounds_written = True
        if line.startswith("001 "):
            line = _byte_pad(line)
        out.append(line)
    return newline.join(out)


def _byte_pad(line: str) -> str:
    name = line[columns.NAME]
    extra = len(name.encode("utf-8")) - len(name)
    if extra <= 0:
        return line
    stripped = name.rstrip()
    while len(stripped.encode("utf-8")) > NAME_BYTES:
        stripped = stripped[:-1]
    field = stripped + " " * (NAME_BYTES - len(stripped.encode("utf-8")))
    return line[: columns.NAME.start] + field + line[columns.NAME.stop :]
