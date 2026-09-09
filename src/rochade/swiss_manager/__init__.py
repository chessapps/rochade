"""Swiss-Manager's own file formats -- pure, no database, no framework.

Named for the program the way `trf/` is named for the format, because these
files are not a standard: they are whatever Swiss-Manager writes and reads under
`Extras -> Daten Import/Export`. Everything in here was learnt by exporting real
files and importing them back (see `docs/m0-swiss-manager.md`), not from
documentation.
"""

from rochade.swiss_manager.pairing_file import (
    PairingFileError,
    PairingLine,
    parse_pairing_file,
    render_pairing_file,
)
from rochade.swiss_manager.player_file import (
    PlayerFileError,
    PlayerLine,
    by_start_number,
    looks_like_player_file,
    parse_player_file,
)

__all__ = [
    "PairingFileError",
    "PairingLine",
    "PlayerFileError",
    "PlayerLine",
    "by_start_number",
    "looks_like_player_file",
    "parse_pairing_file",
    "parse_player_file",
    "render_pairing_file",
]
