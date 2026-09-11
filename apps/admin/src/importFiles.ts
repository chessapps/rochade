/**
 * What the arbiter dropped, and whether it is enough to import.
 *
 * Swiss-Manager hands over two plain text files -- the players and the
 * pairings, from `Extras → Daten Import/Export` -- which mean nothing apart:
 * one names nobody, the other pairs nobody. Vega hands over two files from
 * its tournament folder: `engine26.trf` (or `crosstable.txt`), the players
 * with every result so far, and `SortedPairs.txt`, the boards of the round
 * just paired. A TRF on its own is taken for either program. The files travel to the API as one body,
 * joined, and the backend tells them apart by their own header lines, so the
 * only thing this file decides is what to say to the arbiter while they are
 * still choosing.
 */

export type FileKind =
  | "players"
  | "pairings"
  | "crosstable"
  | "sorted_pairs"
  | "standings"
  | "trf"
  | "unknown";

export interface PickedFile {
  name: string;
  content: string;
  kind: FileKind;
}

const PAIRING_HEADER = "Runde;Brett;IdentW";
const SWISS_MANAGER_KINDS: FileKind[] = ["players", "pairings"];
const VEGA_KINDS: FileKind[] = ["crosstable", "sorted_pairs"];

export function sniff(content: string): FileKind {
  const first = firstLine(content);
  if (first.startsWith(PAIRING_HEADER)) return "pairings";
  if (first.startsWith("Nr;") && first.includes("Nachname")) return "players";
  if (/Pairing of round \d+ sorted by name$/.test(first)) return "sorted_pairs";
  // A TRF is fixed-column and starts with a numeric record code: 012 for the
  // tournament name, 001 for a player.
  if (/^(0\d\d|XX[A-Z])[ ]/.test(first)) return "trf";
  // Vega's cross table starts with the tournament's name; its own header is
  // a few lines down.
  if (/^\s*Cross Table at round \d+\s*$/m.test(content)) return "crosstable";
  if (/^\s*Standings at round \d+\s*$/m.test(content)) return "standings";
  return "unknown";
}

export const KIND_LABEL: Record<FileKind, string> = {
  players: "players",
  pairings: "pairings",
  crosstable: "cross table",
  sorted_pairs: "pairing list",
  standings: "standings",
  trf: "TRF16",
  unknown: "not recognised",
};

/**
 * Add a file, replacing one of the same kind rather than piling them up. A
 * TRF and Swiss-Manager's text pair replace each other -- each is the whole
 * round on its own -- while Vega's engine file is a TRF that belongs beside
 * the pairing list.
 */
export function withFile(files: PickedFile[], picked: PickedFile): PickedFile[] {
  const isSwissManager = (kind: FileKind) => SWISS_MANAGER_KINDS.includes(kind);
  const kept = files.filter((file) => {
    if (file.kind === picked.kind) return false;
    const swap =
      (picked.kind === "trf" && isSwissManager(file.kind)) ||
      (file.kind === "trf" && isSwissManager(picked.kind));
    return !swap;
  });
  return [...kept, picked];
}

export function isReady(files: PickedFile[], rosterHeld = false, manager?: string): boolean {
  return missing(files, rosterHeld, manager) === null;
}

/**
 * What the tournament's program hands over, for the drop zone's hint. Once
 * the section holds players, the pairings alone are the round.
 */
export function dropHint(manager: string | undefined, rosterHeld = false): string {
  switch (manager) {
    case "swiss_manager":
      return rosterHeld
        ? "or click to choose it — Spielerauslosung, from Extras → Daten Import/Export; Spielerdaten too only if a player was added or removed"
        : "or click to choose them — Spielerdaten and Spielerauslosung, from Extras → Daten Import/Export";
    case "vega":
      return rosterHeld
        ? "or click to choose it — SortedPairs.txt, from the tournament folder; engine26.trf too only if a player was added or removed"
        : "or click to choose them — engine26.trf and SortedPairs.txt, from the tournament folder";
    default:
      return "or click to choose them";
  }
}

/**
 * The one sentence that says what is still needed, or null when nothing is.
 * A TRF stands alone; the two text files of either program only count
 * together -- unless the section already holds a roster from an earlier
 * round, when the pairings alone will do.
 */
export function missing(
  files: PickedFile[],
  rosterHeld = false,
  manager?: string,
): string | null {
  if (files.length === 0) return "Nothing chosen yet.";
  const kinds = new Set(files.map((file) => file.kind));
  // Each program's text files have one home. A TRF reads for either.
  if (manager === "vega" && SWISS_MANAGER_KINDS.some((kind) => kinds.has(kind))) {
    return "These are Swiss-Manager's text exports, and this tournament runs on Vega. Hand over engine26.trf and SortedPairs.txt from Vega's tournament folder instead.";
  }
  if (manager === "swiss_manager" && VEGA_KINDS.some((kind) => kinds.has(kind))) {
    return "These are Vega's tournament-folder files, and this tournament runs on Swiss-Manager. Export Spielerdaten and Spielerauslosung instead.";
  }
  if (kinds.has("trf")) return null;
  if (kinds.has("players") && kinds.has("pairings")) return null;
  if (kinds.has("crosstable") && kinds.has("sorted_pairs")) return null;
  if (kinds.has("pairings")) {
    if (rosterHeld) return null;
    return "The pairings name nobody on their own. Add the players file: Extras → Daten Import/Export → Spielerdaten (Text-File).";
  }
  if (kinds.has("players")) {
    return rosterHeld
      ? "The players pair nobody on their own. Add the pairings file for the next round, or drop this list on the Standings page to update the table only."
      : "The players pair nobody on their own. Add the pairings file: Extras → Daten Import/Export → Spielerauslosung (Text-File).";
  }
  if (kinds.has("sorted_pairs")) {
    if (rosterHeld) return null;
    return "The pairing list names the players but not their start numbers. Add engine26.trf (or crosstable.txt) from the same tournament folder.";
  }
  if (kinds.has("crosstable")) {
    return "The cross table pairs nobody on its own. Add SortedPairs.txt, which Vega writes when it pairs the round.";
  }
  if (kinds.has("standings")) {
    return "This is Vega's standings.txt. It belongs on the Standings page; the round comes in as SortedPairs.txt.";
  }
  return "This does not look like a manager export. Choose the file the manager wrote.";
}

/** What to tell the arbiter when the pairings will be named from the roster we hold. */
export function rosterNote(files: PickedFile[], rosterHeld: boolean): string | null {
  const kinds = new Set(files.map((file) => file.kind));
  if (!rosterHeld) return null;
  if (kinds.has("pairings") && !kinds.has("players")) {
    return "Names come from the players already held for this section. Add Spielerdaten only if a player was added or removed.";
  }
  if (kinds.has("sorted_pairs") && !kinds.has("crosstable") && !kinds.has("trf")) {
    return "Start numbers come from the players already held for this section. Add engine26.trf only if a player was added or removed.";
  }
  return null;
}

/**
 * The file's text. Swiss-Manager writes UTF-8, but an older build or a
 * re-saved file may be Windows-1252, where the half-point glyph is one byte
 * that UTF-8 decoding would turn into U+FFFD. Strict UTF-8 first, then 1252.
 */
export async function readText(file: Blob): Promise<string> {
  const bytes = await bytesOf(file);
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1252").decode(bytes);
  }
}

function bytesOf(file: Blob): Promise<ArrayBuffer> {
  // FileReader is the one reader every browser and test runtime has.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error ?? new Error("could not read the file"));
    reader.readAsArrayBuffer(file);
  });
}

/** One body for the API: the files as they were, in a stable order. */
export function joinContents(files: PickedFile[]): string {
  return [...files]
    .sort((a, b) => order(a.kind) - order(b.kind))
    .map((file) => file.content.trimEnd())
    .join("\n");
}

/** The name worth recording: the one that carries the round. */
export function primaryName(files: PickedFile[]): string {
  const carrier =
    files.find((file) => file.kind === "pairings") ??
    files.find((file) => file.kind === "sorted_pairs") ??
    files.find((file) => file.kind === "trf");
  return (carrier ?? files[0])?.name ?? "";
}

function order(kind: FileKind): number {
  return kind === "players" || kind === "crosstable" || kind === "trf" ? 0 : 1;
}

function firstLine(content: string): string {
  for (const line of content.replace(/\r\n/g, "\n").split("\n")) {
    const trimmed = line.replace(/^﻿/, "").trim();
    if (trimmed) return trimmed;
  }
  return "";
}
