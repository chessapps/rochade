"""A tournament Rochade pairs itself has no files: every file use case says so.

The refusals matter as much as the pairing: an arbiter who drops a
Swiss-Manager export into a Rochade-paired tournament must be told at once,
not have a section silently rebuilt from it.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rochade.features.imports.import_round import ImportRound
from rochade.features.imports.preview_import import PreviewImport
from rochade.features.rounds.export_round import ExportRound, GetExportFile
from rochade.features.standings.import_standings import ImportStandings
from rochade.features.standings.name_tiebreaks import NameTiebreaks
from rochade.features.tournaments.get_tournament import GetTournament
from rochade.features.tournaments.list_tournaments import ListTournaments
from rochade.platform.errors import Conflict
from rochade.shared.enums import RoundState
from rochade.shared.models import Round, Section, Tournament
from tests.conftest import Send

pytestmark = [pytest.mark.db, pytest.mark.manager("gacrux")]


def test_the_tournament_says_it_is_native(send: Send, tournament: Tournament) -> None:
    detail = send(GetTournament(tournament_id=tournament.id))
    assert detail.native is True
    assert detail.manager_label == "Rochade (Gacrux engine)"
    listed = {t.id: t for t in send(ListTournaments())}
    assert listed[tournament.id].native is True


def test_import_and_preview_are_refused(
    send: Send, tournament: Tournament, round1_text: str
) -> None:
    with pytest.raises(Conflict, match="paired in Rochade"):
        send(PreviewImport(tournament_id=tournament.id, section_name="A", content=round1_text))
    with pytest.raises(Conflict, match="paired in Rochade"):
        send(ImportRound(tournament_id=tournament.id, section_name="A", content=round1_text))


def test_export_is_refused(send: Send, session: Session, tournament: Tournament) -> None:
    section = Section(tournament_id=tournament.id, name="A", manager="gacrux")
    session.add(section)
    session.flush()
    round_ = Round(section_id=section.id, number=1, state=RoundState.CONFIRMED, source_trf="x")
    session.add(round_)
    session.commit()

    with pytest.raises(Conflict, match="no file to export"):
        send(ExportRound(round_id=round_.id))
    round_.state = RoundState.EXPORTED
    session.commit()
    with pytest.raises(Conflict, match="no file to export"):
        send(GetExportFile(round_id=round_.id))


def test_standings_cannot_be_imported_or_relabelled(
    send: Send, session: Session, tournament: Tournament
) -> None:
    session.add(Section(tournament_id=tournament.id, name="A", manager="gacrux"))
    session.commit()
    with pytest.raises(Conflict, match="computed at every release"):
        send(ImportStandings(tournament_id=tournament.id, section_name="A", content="Nr;Name\n"))
    with pytest.raises(Conflict, match="computed at every release"):
        send(NameTiebreaks(tournament_id=tournament.id, section_name="A", names=["BH"]))
