/**
 * What the arbiter dropped, and whether it is enough to import.
 *
 * Vega hands over one TRF. Swiss-Manager hands over two plain text files --
 * the players and the pairings, from `Extras → Daten Import/Export` -- which
 * mean nothing apart: one names nobody, the other pairs nobody. They travel to
 * the API as one body, joined, and the backend tells them apart by their own
 * header lines, so the only thing this file decides is what to say to the
 * arbiter while they are still choosing.
 */

export type FileKind = "players" | "pairings" | "trf" | "unknown";

export interface PickedFile {
  name: string;
  content: string;
  kind: FileKind;
}

const PAIRING_HEADER = "Runde;Brett;IdentW";

export function sniff(content: string): FileKind {
  const first = firstLine(content);
  if (first.startsWith(PAIRING_HEADER)) return "pairings";
  if (first.startsWith("Nr;") && first.includes("Nachname")) return "players";
  // A TRF is fixed-column and starts with a numeric record code: 012 for the
  // tournament name, 001 for a player.
  if (/^(0\d\d|XX[A-Z])[ ]/.test(first)) return "trf";
  return "unknown";
}

export const KIND_LABEL: Record<FileKind, string> = {
  players: "players",
  pairings: "pairings",
  trf: "TRF16",
  unknown: "not recognised",
};

/** Add a file, replacing one of the same kind rather than piling them up. */
export function withFile(files: PickedFile[], picked: PickedFile): PickedFile[] {
  const kept = files.filter(
    (file) => file.kind !== picked.kind && !(picked.kind === "trf" || file.kind === "trf"),
  );
  return [...kept, picked];
}

export function isReady(files: PickedFile[], rosterHeld = false, manager?: string): boolean {
  return missing(files, rosterHeld, manager) === null;
}

/** What the tournament's program hands over, for the drop zone's hint. */
export function dropHint(manager: string | undefined): string {
  switch (manager) {
    case "swiss_manager":
      return "or click to choose them — Spielerdaten and Spielerauslosung, from Extras → Daten Import/Export";
    case "vega":
      return "or click to choose it — the TRF16 export of the paired round";
    default:
      return "or click to choose them";
  }
}

/**
 * The one sentence that says what is still needed, or null when nothing is.
 * A TRF stands alone; the two text files only count together -- unless the
 * section already holds a roster from an earlier round, when the pairings
 * alone will do.
 */
export function missing(
  files: PickedFile[],
  rosterHeld = false,
  manager?: string,
): string | null {
  if (files.length === 0) return "Nothing chosen yet.";
  const kinds = new Set(files.map((file) => file.kind));
  // A Vega tournament takes one TRF and nothing else. Swiss-Manager reads a
  // TRF too, so the text files are the only thing that has one home.
  if (manager === "vega" && (kinds.has("players") || kinds.has("pairings"))) {
    return "These are Swiss-Manager's text exports, and this tournament runs on Vega. Export the round from Vega as TRF16 instead.";
  }
  if (kinds.has("trf")) return null;
  if (kinds.has("players") && kinds.has("pairings")) return null;
  if (kinds.has("pairings")) {
    if (rosterHeld) return null;
    return "The pairings name nobody on their own. Add the players file: Extras → Daten Import/Export → Spielerdaten (Text-File).";
  }
  if (kinds.has("players")) {
    return rosterHeld
      ? "The players pair nobody on their own. Add the pairings file for the next round, or drop this list on the Standings page to update the table only."
      : "The players pair nobody on their own. Add the pairings file: Extras → Daten Import/Export → Spielerauslosung (Text-File).";
  }
  return "This does not look like a manager export. Choose the file the manager wrote.";
}

/** What to tell the arbiter when the pairings will be named from the roster we hold. */
export function rosterNote(files: PickedFile[], rosterHeld: boolean): string | null {
  const kinds = new Set(files.map((file) => file.kind));
  if (!rosterHeld || !kinds.has("pairings") || kinds.has("players")) return null;
  return "Names come from the players already held for this section. Add Spielerdaten only if a player was added or removed.";
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
    files.find((file) => file.kind === "trf") ?? files.find((file) => file.kind === "pairings");
  return (carrier ?? files[0])?.name ?? "";
}

function order(kind: FileKind): number {
  return kind === "players" ? 0 : 1;
}

function firstLine(content: string): string {
  for (const line of content.replace(/\r\n/g, "\n").split("\n")) {
    const trimmed = line.replace(/^﻿/, "").trim();
    if (trimmed) return trimmed;
  }
  return "";
}
