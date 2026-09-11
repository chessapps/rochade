/**
 * The tie-breaks a section Rochade pairs itself may rank by, in the engine's
 * own spelling. Mirrors `rochade.gacrux.tiebreaks` on the server: the codes
 * are what the section stores and what the standings table shows as column
 * headings, the labels are what the picker offers.
 */

export const TIEBREAKS: readonly { code: string; label: string }[] = [
  { code: "PTS", label: "Points" },
  { code: "BH/C1", label: "Buchholz Cut 1" },
  { code: "BH", label: "Buchholz" },
  { code: "BH/M1", label: "Median Buchholz" },
  { code: "SB", label: "Sonneborn-Berger" },
  { code: "SB/C1", label: "Sonneborn-Berger Cut 1" },
  { code: "DE", label: "Direct encounter" },
  { code: "WIN", label: "Wins" },
  { code: "WON", label: "Games won" },
  { code: "BPG", label: "Games with black" },
  { code: "BWG", label: "Wins with black" },
  { code: "PS", label: "Progressive score" },
  { code: "KS", label: "Koya" },
  { code: "AOB", label: "Average of opponents' Buchholz" },
  { code: "ARO", label: "Average rating of opponents" },
  { code: "ARO/C1", label: "Average rating of opponents Cut 1" },
  { code: "TPR", label: "Tournament performance rating" },
];

export const DEFAULT_TIEBREAKS: readonly string[] = ["PTS", "BH/C1", "BH", "SB"];

export const MAX_TIEBREAKS = 9;

export function tiebreakLabel(code: string): string {
  return TIEBREAKS.find((t) => t.code === code.toUpperCase())?.label ?? code;
}
