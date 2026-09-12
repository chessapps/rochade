/**
 * How a round runs when Swiss-Manager pairs it: what happens there, what
 * happens here, and the two text files that carry the round between the
 * two. The same story as docs/arbiter-guide-swiss-manager.md, on the screen
 * the arbiter has open anyway. Verified against Swiss-Manager 15.0.0.3.
 */

import { Link } from "react-router";

import { Code, Fact, File, Files, Kbd, Loop, M, Note, Section, Step, Steps } from "../components/Guide";
import { PageHeader } from "../components/PageHeader";

export function SwissManagerGuide() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: "/?all", label: "Tournaments" }}
        title="Running a tournament with Swiss-Manager"
        lead="Swiss-Manager pairs, Rochade collects the results in the hall, Swiss-Manager gets them back. Two text exports in and one file out per round; everything else is what you do already. Written for Swiss-Manager 15.0.0.3 with the German menus, named as they appear there."
      />

      <Loop
        cells={[
          {
            where: "In Swiss-Manager",
            title: "Pair the round, export two files",
            body: (
              <>
                <M>Extras → Daten Import/Export</M>: <Code>Spielerdaten</Code> and{" "}
                <Code>Spielerauslosung</Code> as text files.
              </>
            ),
          },
          {
            where: "In Rochade",
            title: "Import, play, release",
            body: (
              <>
                Drop the two files. Enter the results. Release, then{" "}
                <b>Export for Swiss-Manager</b> downloads <Code>&lt;section&gt;-round&lt;N&gt;.txt</Code>.
              </>
            ),
          },
          {
            where: "In Swiss-Manager",
            title: "Import the results",
            body: (
              <>
                <M>Extras → Daten Import/Export</M>, import <Code>Spielerauslosung</Code>. Then
                pair the next round.
              </>
            ),
          },
        ]}
      />

      <Section title="Once, before the tournament">
        <Steps>
          <Step title="Set the round dates in Swiss-Manager">
            <M>Eingabe → Termine für die einzelnen Runden…</M> → <M>Übernehmen</M> → <M>OK</M>. A
            rated tournament needs them anyway, and Swiss-Manager&rsquo;s exports are happier with
            them set.
          </Step>
          <Step title="Create the tournament in Rochade">
            <b>New tournament</b> on the tournaments page, choose <b>Swiss-Manager</b> as the
            program that pairs it. That choice is fixed for the tournament: every import and
            export from then on is Swiss-Manager&rsquo;s, and nothing asks again.
          </Step>
          <Step title="Set up the hall device">
            <b>Devices → Issue a QR code</b> and scan it with the tablet at the desk where results
            are entered. The code admits that device for as long as the tournament runs, and you
            can revoke it at any time. If the tablet cannot scan, <b>Open joining with a code</b>{" "}
            shows six characters to type instead.
          </Step>
          <Step title="Publish it, if the public may follow">
            <b>Publish…</b> on the tournament home. Anyone with the link then sees the pairings of
            every round, results as they come in, marked preliminary until you confirm them or
            release the round, the standings, and every game of a player. Nothing is public until
            you press it; <b>Hide</b> takes it down at once.
          </Step>
        </Steps>
      </Section>

      <Section title="Every round">
        <Steps>
          <Step n={1} title="Pair the round in Swiss-Manager">
            <M>Auslosen → Auslosungsmenü…</M> (<Kbd>F6</Kbd>), <M>Starten</M>, <M>OK</M>. As
            always.
          </Step>

          <Step n={2} title="Export it for Rochade">
            <p>
              <M>Extras → Daten Import/Export…</M>, on the <b>export</b> side, the left column:
            </p>
            <Files>
              <File name="Spielerdaten (Text-File)">
                <M>Starten</M>, save it, say as <Code>players.txt</Code>. The entry list.
              </File>
              <File name="Spielerauslosung (Text-File)">
                set <M>Runde</M> to the round you just paired, both boxes the same number,{" "}
                <M>Starten</M>, save it, say as <Code>round4.txt</Code>. The boards.
              </File>
            </Files>
            <p>
              <M>OK</M> closes the dialog. Neither export asks anything else, and neither says
              anything when it works. In Rochade the section card says <b>Import round N</b>.
              Press it, drop both files on the page, <b>Preview the changes</b>, read what they
              change, <b>Import</b>. You land on the round board, with the board numbers
              Swiss-Manager printed on the pairing list.
            </p>
            <Note tone="good">
              <b>From round 2 on, the pairings file alone is enough.</b> Rochade names the boards
              from the players it already holds. Export Spielerdaten again only when a player was
              added or removed; Rochade tells you if the pairings mention a start number it does
              not know.
            </Note>
            <Note tone="warn">
              <b>Not Extras → FIDE-Daten-Export TRF16.</b> On 15.0.0.3 it crashes with an access
              violation for a tournament Swiss-Manager paired itself and leaves a file with a
              header and no players. The two text exports are the way. Rochade still reads a TRF
              if you have one.
            </Note>
          </Step>

          <Step n={3} title="Play">
            Results are entered on the hall device at the desk, or by you on the round board.
            The board updates every few seconds and opens on <b>Attention</b>: the boards with no
            result yet, so an empty list means the round is done. A no-show is yours: <b>more…</b> on the board, then <b>+:−</b>, <b>−:+</b> or{" "}
            <b>−:−</b>. The same menu has the unrated results and, under <b>Any pair</b>, every
            code for either side. With a board focused, <Kbd>1</Kbd> <Kbd>=</Kbd> <Kbd>0</Kbd> on
            the keyboard set it too. <b>Entered → Confirm all</b> confirms checked results in one
            go without releasing the round; a confirmed board is closed to the hall device, so a
            late correction comes to you instead of overwriting what you checked.
          </Step>

          <Step n={4} title="Release and export">
            When Attention is empty the bar at the bottom says <b>Release round N</b>; press it.
            Then <b>Export for Swiss-Manager</b>: a file named after the section and the round,
            for instance <Code>A-round4.txt</Code>, downloads. The round is now frozen; from here
            on Swiss-Manager owns it. The green card at the top of the round says what to do in
            Swiss-Manager, holds the file again should the download go astray, and has{" "}
            <b>Import round N+1</b> on it too.
          </Step>

          <Step n={5} title="Import the results into Swiss-Manager">
            <p>
              <M>Extras → Daten Import/Export…</M>, under <M>Importart</M> choose{" "}
              <M>Spielerauslosung</M>, <M>Starten</M>, pick the downloaded file, <M>OK</M>.
            </p>
            <p>
              Nothing is shown on success. Check <M>Listen → Ergebnisse</M> (<Kbd>F9</Kbd>): the
              results are there, forfeits as <Code>+ - -</Code>, the bye scored by your
              tournament&rsquo;s setting. Then pair the next round: back to step 1.
            </p>
            <Note tone="warn">
              <b>Not Datei → FIDE-Datenformat importieren TRF16.</b> It creates a <i>new</i>{" "}
              tournament from the file every time, sets the round count from what the file holds
              and guesses the bye value. It is for rebuilding a tournament for the rating office,
              not for continuing yours.
            </Note>
          </Step>

          <Step n={6} title="Standings">
            Swiss-Manager&rsquo;s player list carries its Rangliste: points, the tie-breaks in the
            order of your tournament settings, and the rank. Whenever you import a round with both
            files, the standings after the previous round come along, and <b>Standings</b> shows
            them; players see the same table in the hall app. Nothing is computed in Rochade.
            After the last round there is no pairing to import: export Spielerdaten once more and
            drop it on the Standings page. The file numbers the tie-break columns without naming
            them; <b>Name them</b> once from your tournament settings and the names stay.
          </Step>
        </Steps>
      </Section>

      <Section title="Things to know">
        <ul className="flex flex-col gap-2 text-body-sm text-ink-2">
          <Fact>
            <b>Names appear as Swiss-Manager exports them:</b> <Code>Surname,Given</Code>, and
            transliterated for the tournament&rsquo;s own federation (Müller becomes Mueller).
            Players find their board by typing part of their name, so this rarely matters. Titles
            are not in the export.
          </Fact>
          <Fact>
            <b>Re-paired a round after exporting it?</b> A late entrant, a correction: export
            again and re-import in Rochade <b>before</b> sending results back. The results file
            carries the pairings too, and Swiss-Manager takes them; a file built from the old
            pairings would quietly undo your re-pairing. The preview shows which boards moved and
            which entered results would be dropped, and applies nothing until you accept it.
          </Fact>
          <Fact>
            <b>Byes and withdrawals</b> are set in Swiss-Manager before pairing, as always.
            Rochade shows them and never writes them back.
          </Fact>
        </ul>
      </Section>

      <p className="text-body-sm text-ink-3">
        The same guide, with what was watched and what was not, is in the repository as{" "}
        <Code>docs/arbiter-guide-swiss-manager.md</Code>.{" "}
        <Link to="/?all" className="font-medium text-accent hover:underline">
          Back to the tournaments
        </Link>
        .
      </p>
    </div>
  );
}
