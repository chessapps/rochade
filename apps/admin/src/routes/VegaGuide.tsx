/**
 * How a round runs when Vega pairs it: what happens in Vega, what happens
 * here, and which files carry the round between the two. The same story as
 * docs/arbiter-guide-vega.md, on the screen the arbiter has open anyway.
 * Verified against Vega 12.1.8.
 */

import { Link } from "react-router";

import { PageHeader } from "../components/PageHeader";
import { Code, Fact, File, Files, Kbd, Loop, M, Note, Section, Step, Steps } from "../components/Guide";

export function VegaGuide() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: "/?all", label: "Tournaments" }}
        title="Running a tournament with Vega"
        lead="Vega pairs, Rochade collects the results in the hall, Vega gets them back. Two files in and one file out per round; everything else is what you do already. Written for Vega 12.1.8 with the English menus."
      />

      <Loop
        cells={[
          {
            where: "In Vega",
            title: "Pair the round",
            body: (
              <>
                Vega writes <Code>engine26.trf</Code> and <Code>SortedPairs.txt</Code> into the
                tournament folder.
              </>
            ),
          },
          {
            where: "In Rochade",
            title: "Import, play, release",
            body: (
              <>
                Drop the two files. Enter the results. Release, then <b>Export for Vega</b>{" "}
                downloads <Code>&lt;section&gt;.trf</Code>.
              </>
            ),
          },
          {
            where: "In Vega",
            title: "Import the results",
            body: (
              <>
                <M>File → Import tournament in FIDE format - TRF2026</M>. Then pair the next round.
              </>
            ),
          },
        ]}
      />

      <Section title="Once, before the tournament">
        <Steps>
          <Step title="Create the tournament in Vega">
            <M>File → New Tournament</M>, as always, with a <b>tournament folder</b>. Vega writes
            the files Rochade reads into that folder, so know where it is. Register the players and
            close the registration.
          </Step>
          <Step title="Create the tournament in Rochade">
            <b>New tournament</b> on the tournaments page, choose <b>Vega</b> as the program that
            pairs it. That choice is fixed for the tournament: every import and export from then on
            is Vega&rsquo;s.
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
          <Step n={1} title="Pair the round in Vega">
            <M>Round Manager → Automatic</M> (or <M>Manual</M>, or <M>Modify Pairing</M>{" "}
            afterwards). Rochade reads the boards as they stand, not as the engine first proposed
            them.
          </Step>

          <Step n={2} title="Hand the round to Rochade">
            <p>
              Vega has already written the two files into the tournament folder; there is nothing
              to export:
            </p>
            <Files>
              <File name="engine26.trf">
                the players with their start numbers, every result so far and the number of
                rounds. Written each time Vega&rsquo;s engine pairs, from round 1 on.
              </File>
              <File name="SortedPairs.txt">the boards of the round you just paired.</File>
            </Files>
            <p>
              In Rochade the section card says <b>Import round N</b>. Press it, drop both files
              on the page, <b>Preview the changes</b>, read what they change, <b>Import</b>.
            </p>
            <Note tone="good">
              <b>From round 2 on, SortedPairs.txt alone is enough.</b> Rochade names the boards
              from the players it already holds. Add engine26.trf again only when a player was
              added or removed; Rochade tells you if the list names somebody it does not know.
            </Note>
            <Note>
              <b>Paired by hand?</b> Then the engine did not run and engine26.trf is still the
              previous round&rsquo;s. Rochade refuses a file that is behind and says so. Hand over{" "}
              <b>crosstable.txt</b> instead (Vega writes it once a result has been entered), or
              SortedPairs.txt alone if Rochade already holds the players. Without an engine file,
              Rochade asks once how many rounds the tournament has.
            </Note>
            <Note tone="warn">
              <b>Not Rating Report → FIDE.</b> It refuses to write anything while a paired round
              has no results, which is exactly when you need it. The folder files are the way.
            </Note>
          </Step>

          <Step n={3} title="Play">
            Results are entered on the hall device at the desk, or by you on the round board.
            The board updates every few seconds and opens on <b>Attention</b>: the boards with no
            result yet. A no-show is yours: <b>more…</b> on the board, then <b>+:−</b>, <b>−:+</b> or{" "}
            <b>−:−</b>. With a board focused, <Kbd>1</Kbd> <Kbd>=</Kbd> <Kbd>0</Kbd> on the
            keyboard set it too. <b>Entered → Confirm all</b> confirms checked results without
            releasing the round.
          </Step>

          <Step n={4} title="Release and export">
            When Attention is empty the bar at the bottom says <b>Release round N</b>; press it.
            Then <b>Export for Vega</b>: a file named after the section, for instance{" "}
            <Code>A.trf</Code>, downloads. It has the same name every round, on purpose. The
            round is now frozen; from here on Vega owns it. The green card at the top of the round
            says what to do in Vega and holds the file again should the download go astray.
          </Step>

          <Step n={5} title="Import the results into Vega">
            <p>
              <M>File → Import tournament in FIDE format - TRF2026</M>, choose the downloaded
              file. Nothing is shown on success: the boards of the round show the results,
              forfeits as <Code>1F-0F</Code>, the bye as <Code>1</Code>.
            </p>
            <Note>
              <b>Vega replaces the open tournament with the file</b> and names the tournament
              after it. Since the file is named after the section, the tournament is called{" "}
              <Code>A</Code> from the first import on and saved as <Code>A.vegz</Code> next to
              the one you created. The earlier file and Vega&rsquo;s own backups stay where they
              are.
            </Note>
            <Note>
              <b>Tie-breaks other than Buchholz are reset</b> by that import. If Vega&rsquo;s own
              standings are what you print, set them again under{" "}
              <M>File → Tournament manager → Modify Tournament → Tie Breaks</M> after the first
              import. Play system, round count and dates survive.
            </Note>
            <p>Then pair the next round: back to step 1.</p>
          </Step>

          <Step n={6} title="Standings">
            Vega computes them, Rochade shows them. Vega rewrites <b>standings.txt</b> in the
            tournament folder at every result, tie-breaks included. On Rochade&rsquo;s{" "}
            <b>Standings</b> page, drop that file: points, tie-breaks and ranks are taken as Vega
            printed them, matched on the start number, and the tie-break columns carry
            Vega&rsquo;s names. The hall app shows the same table. Do it after the results of a
            round went back to Vega, or after the last round.
          </Step>
        </Steps>
      </Section>

      <Section title="Things to know">
        <ul className="flex flex-col gap-2 text-body-sm text-ink-2">
          <Fact>
            <b>Names must match.</b> Rochade joins the two files by name. Both come from the same
            Vega tournament, so they do. Accented names are fine; Rochade writes the file back
            the way Vega reads it.
          </Fact>
          <Fact>
            <b>Re-paired a round after handing it over?</b> A late-comer, a correction: hand
            SortedPairs.txt over again <b>before</b> sending results back. The preview shows
            which boards moved and which entered results would be dropped, and applies nothing
            until you accept it. A late-comer needs engine26.trf too.
          </Fact>
          <Fact>
            <b>Byes and withdrawals</b> are set in Vega before pairing, as always; the player is
            simply not on the list. Rochade shows the bye and writes it back as it came.
          </Fact>
          <Fact>
            <b>Loading many players into Vega</b> goes through its Players tab: <M>Database 1 →
            Set DB</M> with a fixed-length national archive and a matching filter file, then one{" "}
            <b>Add Selected</b> per player. There is no import on the File menu.
          </Fact>
          <Fact>
            An unregistered Vega is limited to 20 players; the club&rsquo;s own licence applies as
            usual.
          </Fact>
        </ul>
      </Section>

      <p className="text-body-sm text-ink-3">
        The same guide, with what was watched and what was not, is in the repository as{" "}
        <Code>docs/arbiter-guide-vega.md</Code>.{" "}
        <Link to="/?all" className="font-medium text-accent hover:underline">
          Back to the tournaments
        </Link>
        .
      </p>
    </div>
  );
}
