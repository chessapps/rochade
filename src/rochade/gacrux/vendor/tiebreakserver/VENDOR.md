# TieBreakServer, vendored

Upstream: https://github.com/OttoMilvang/TieBreakServer
Licence: MIT, Copyright (c) 2024 FIDE. Source code developed by IA Otto Milvang.
Snapshot: commit `14a34a2c2f36509b110e4f25d6247f31fc4bf2f5` (version 1.9.57, 2026-07-21),
taken on 2026-09-10.

This directory is a verbatim copy of every file upstream tracks, minus its
IDE settings and `.gitignore`. Nothing in here is edited: Rochade drives the
two command-line tools (`pairingchecker.py`, `tiebreakchecker.py`) as
subprocesses from `rochade.gacrux.engine`, and the FIDE TRF16 files it hands
them are the interchange. Its one dependency, `networkx`, is declared in the
project's `pyproject.toml`.

Lint and type checks skip this directory on purpose; it is upstream's code and
is kept diffable against upstream.

## Refreshing

```
git clone https://github.com/OttoMilvang/TieBreakServer /tmp/tbs
cd /tmp/tbs && git rev-parse HEAD
git ls-files | grep -v '^\.spyproject/\|^\.gitignore$' \
  | while read f; do cp "$f" <repo>/src/rochade/gacrux/vendor/tiebreakserver/"$f"; done
```

Then update the commit, version and date above, run `uv run pytest tests/gacrux`
(the golden files under `tests/fixtures/gacrux/` say whether the pairing or the
tiebreak arithmetic moved), and note anything that changed in `docs/gacrux.md`.

`VENDOR.sha256` holds the SHA-256 of every `.py` file in the snapshot
(`sha256sum *.py > VENDOR.sha256`, run inside this directory); a test compares
the files against it on every run.
