# Rochade — design brief

*For the designer agent. This describes what the product does, every screen it
has, and the look we want. Live at <https://rochade.app>. Source: two React +
Tailwind 4 apps under `apps/hall` (players' phones) and `apps/admin` (arbiter).*

## What we want from you

A **modern, slick visual identity and screen designs** that make Rochade read
as a contemporary chess application: confident, precise, quiet. Think of the
polish of Lichess and Chess.com's newer surfaces, and of the way a good
scoreboard app looks on a phone, not of a tournament spreadsheet. The current
build is deliberately plain (black on white in the hall app, slate and blue
in the admin app); keep its clarity and its meaning-carrying colours, and give
it a look people would screenshot.

Deliverables we expect:

1. A small design system: palette (light and dark), type scale, spacing,
   radius, elevation, the state colours below, iconography, a logo mark and
   wordmark for "Rochade".
2. High-fidelity mockups for every screen listed under *Screens*, at phone
   width for the hall app and at laptop plus phone width for the admin app.
3. Component specs for the pieces that recur: board row, result button,
   state chip, round stepper, section card, dialog, toast, QR poster.
4. Motion notes: a result landing, a board pulsing when a phone reports it,
   the stepper advancing. Subtle, fast, never decorative for its own sake.

## The product in one paragraph

Rochade is **digital result entry for chess tournaments that another program
is running**. The arbiter keeps using Swiss-Manager or Vega for setup,
pairings, tiebreaks and reports. Rochade does the one thing those programs
cannot: it puts a phone in every player's hand. Each round the arbiter
imports the pairing file, players enter their own results by tapping on their
phone, the arbiter reviews the boards as they come in, settles what two
phones disagree about, releases the round, and exports one file back to the
manager for the next pairing. Two file operations per round, nothing else.

```
  manager                       Rochade                       manager
  pair round N
  export      -------------->  import, open round N
                               players enter results (hall app)
                               arbiter reviews + releases
                              export      ----------------->  import results
                                                             pair round N+1 --> loop
```

## The two audiences, and why they get two apps

**Players in the hall.** They have just played four hours of chess, they are
standing in a badly lit room, often on an old Android phone, and they want to
leave. They arrive by scanning a QR poster (or typing a six-character join
code). No install, no sign-in, no account. They find their board, tap the
result, and they are done: **two taps from the sketch**. Everything is
anonymous per board; the result is provisional until the arbiter confirms it.

**The arbiter at the desk.** Usually one person on a laptop, sometimes glancing
at a phone while walking the hall. They sign in with a passkey or password.
Their day is a loop that repeats every round, and the interface should always
name the next step. They read position and status at a glance: which boards
have no result, which are disputed, whether the round can be released.

A shared colour vocabulary ties the two together so a colour means the same
thing on the laptop and on the phone:

| State | Meaning | Current hue |
|---|---|---|
| empty | no result yet | slate |
| claimed | a phone entered a result | amber |
| disputed | two phones disagree | rose |
| confirmed | arbiter released it | emerald |

Round states: **open** (accent blue), **released/confirmed** (amber),
**exported** (slate, frozen).

Everywhere a player name appears, a small **white or black disc** marks which
colour they play. Keep that device; it is the chess signal in the product.

## Screens

### Landing page (rochade.app, any browser with no credential)

- Wordmark, one-line promise ("Chess results, from the board to the arbiter"),
  a short paragraph.
- Card **"Playing today?"**: scan the QR the arbiter put up; when join codes
  are switched on, a large monospaced six-character input (ABC123).
- Card **"Running a tournament?"**: a primary button to the arbiter area.
- A phone that scanned a QR never sees this page; it lands straight on its
  board list.

### Hall app (players' phones, PWA, works offline and queues sends)

1. **Board list.** Sticky header with the tournament name, a status line
   ("Offline", "2 waiting to send", or "48 boards"), and a search field
   "Your name or board". Optional Boards | Standings tabs. Below, a ruled list
   of boards: board number, white player, black player, and on the right
   either a chevron (open), "sending...", the score once entered (1 – 0, ½ – ½),
   or "bye". Grouped by section and round when a tournament has several
   sections (groups A/B/C searched at once; a player types their name and
   finds their board without knowing the group). Two columns on a tablet.
2. **Result choice.** Board heading, both players with colour discs, and
   three large buttons: **1 : 0 White wins**, **½ : ½ Draw**, **0 : 1 Black
   wins**, each with a subline naming the winner. Tapping sends immediately;
   there is no confirm step, the names on the button are the check. A
   secondary "Back to the list".
3. **Done.** The result as it will appear on the pairing sheet: two rows, one
   per colour, the winner's row inverted. A note if it is queued offline. A
   "Correct it" path that returns to the choice screen, and "Back to the list".
4. **Standings** (when the manager's file carried them): rank, name,
   federation, rating, points, tiebreaks. Read-only.

Design constraints: huge tap targets, high contrast in poor light, legible at
arm's length, tabular numerals, safe-area padding above the home bar. Dark
mode is welcome here; many halls are dim.

### Admin app (arbiter, /admin/)

**Shell.** Top bar: wordmark, tournament name (a switcher when there are
several), tabs **Rounds · Standings · Devices**, account name, Sign out.
Content in a centred column, max about 1150px, light background, read at a
desk.

1. **Sign in.** Handled by Zitadel (passkey or password); we only need a
   branded entry screen with one "Sign in" button and an explanatory line.
2. **Tournament list.** Title, "New tournament" button, empty state "Create
   the first one", list of tournaments. Create dialog: name only.
3. **Tournament home.** Title and details, then one **section card** per
   section (a tournament may hold several manager files as sections). Each
   card shows the latest round with a four-dot **round stepper**
   (Imported, Entry open, Released, Exported, with clock times), a
   progress bar of results in, and one large primary button that always names
   the next step: "Import round 3", "Open round 3", "Export for
   Swiss-Manager". Earlier rounds are listed small beneath.
4. **Import wizard.** Two steps: choose the file(s) (Swiss-Manager writes the
   players and the pairings as two text files; Vega one TRF file), then read
   the diff: what blocks the import on top, what must be read in the middle,
   the roster diff (players added, removed, boards changed) below, and a
   checkbox "I have read the changes above" before "Import". Nothing is
   written before that.
5. **Round board.** The screen the arbiter lives on during a round. Title
   "Round 3", round chip, polling every few seconds. Filter tabs with counts:
   **Attention** (boards with no result plus the disputed ones), All, Empty,
   Entered, Disputed, Confirmed. A search box. A table of boards: number, white
   and black with colour discs, the state chip, the result, and for a dispute
   *which phone said what*. Clicking a row opens result entry with forfeits one
   tap further away; the keyboard keys 1, = and 0 also work. A sticky footer
   card at the bottom: "Every board has a result. Release round 3." or
   "Release anyway...", and after release "Export for Swiss-Manager". Rows
   pulse briefly when a new result arrives.
6. **Release dialog** (lists empty and disputed boards it would confirm) and
   **Export dialog** (downloads the file, freezes the round, tells the arbiter
   which menu in the manager to use, keeps the file a click away).
7. **Standings.** The manager's table as imported: rank, name, federation,
   rating, points, tiebreak columns. Per section.
8. **Devices ("Phones in the hall").** "Issue a QR code" (optional label),
   dialog showing the QR to scan or print, the join code when enabled, a list
   of active and revoked devices with when each last entered a result,
   "Revoke", "Remove all revoked".
9. **Poster.** A print-optimised page: tournament name, large QR, the join
   code, one line of instructions. Should look good pinned to a hall door.

## Tone and constraints

- **Modern and slick, but calm.** Chess is a quiet game; the UI should feel
  precise and unhurried. No gamification, no confetti. One accent colour used
  sparingly for the single next action on a screen.
- **Chess, not "chess-themed".** Avoid clip-art pieces and checkerboard
  wallpaper. The colour discs, tabular numerals, a crisp wordmark and a
  restrained mark (a castling motif is the obvious pun on "Rochade", the
  German word for castling) are enough.
- **Status is the content.** Empty, entered, disputed, confirmed must be
  distinguishable at a glance, including for colour-blind users; pair colour
  with shape or label.
- **Accessibility.** WCAG AA contrast, 44px targets on the phone, visible
  focus rings, works with keyboard alone on the admin side.
- **Two themes.** Light for the admin app by default; light and dark for the
  hall app. Provide tokens for both.
- **Stack reality.** Tailwind 4 with CSS variables in an `@theme` block, React,
  no component library. Deliver tokens in a form that maps to that.
- **Languages.** English now; German soon. Leave room for longer strings.
