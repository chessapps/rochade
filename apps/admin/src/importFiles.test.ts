import { describe, expect, it } from "vitest";

import { isReady, joinContents, missing, primaryName, readText, rosterNote, sniff, withFile } from "./importFiles";

const PLAYERS = "Nr;Name;Titel;Identnr;EloNat;EloInt;Geburt;Fed;Sex;Nachname;Vorname\r\n1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;Brunner;Livia\r\n";
const PAIRINGS = "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS\r\n1;1;0;0;1;51;0;0;;0:0;0;;\r\n";
const TRF = "012 Rochade Open 2026\r\n001    1 m    Baumann, Lukas                 2201 SUI\r\n";
const CROSSTABLE =
  "Rochade M0 Spike\r\nRochade - 05/09/2026, 07/09/2026\r\n\r\n Cross Table at round 2\r\n\r\n" +
  "  N NAME                 Rtg   T  Fed  Pts |   1     2  \r\n";
const SORTED_PAIRS = "Rochade M0 Spike: Pairing of round 3 sorted by name\n\n====\n";

const pick = (name: string, content: string) => ({ name, content, kind: sniff(content) });

describe("telling the manager's files apart", () => {
  it("knows each of the three by its first line", () => {
    expect(sniff(PLAYERS)).toBe("players");
    expect(sniff(PAIRINGS)).toBe("pairings");
    expect(sniff(TRF)).toBe("trf");
    expect(sniff(CROSSTABLE)).toBe("crosstable");
    expect(sniff(SORTED_PAIRS)).toBe("sorted_pairs");
    expect(sniff("hello\nthere")).toBe("unknown");
  });

  it("ignores a byte order mark and leading blank lines", () => {
    expect(sniff("﻿\n\n" + PAIRINGS)).toBe("pairings");
  });
});

describe("what is still needed", () => {
  it("takes a TRF on its own", () => {
    const files = [pick("round3.trf", TRF)];
    expect(missing(files)).toBeNull();
    expect(isReady(files)).toBe(true);
  });

  it("asks for the players when only the pairings are there", () => {
    expect(missing([pick("pairings.txt", PAIRINGS)])).toMatch(/Spielerdaten/);
  });

  it("takes the pairings alone once the section holds a roster", () => {
    const files = [pick("pairings.txt", PAIRINGS)];
    expect(missing(files, true)).toBeNull();
    expect(isReady(files, true)).toBe(true);
    expect(rosterNote(files, true)).toMatch(/already held/);
    expect(rosterNote(files, false)).toBeNull();
    expect(rosterNote([pick("players.txt", PLAYERS), ...files], true)).toBeNull();
  });

  it("asks for the pairings when only the players are there", () => {
    expect(missing([pick("players.txt", PLAYERS)])).toMatch(/Spielerauslosung/);
  });

  it("is satisfied by the pair, in either order", () => {
    const one = [pick("players.txt", PLAYERS), pick("pairings.txt", PAIRINGS)];
    expect(isReady(one)).toBe(true);
    expect(isReady([...one].reverse())).toBe(true);
  });

  it("says so plainly when the file is not a manager export at all", () => {
    expect(missing([pick("notes.txt", "hello")])).toMatch(/does not look like/);
  });
});

describe("what Vega needs", () => {
  it("takes the cross table and the pairing list together, in either order", () => {
    const pair = [pick("crosstable.txt", CROSSTABLE), pick("SortedPairs.txt", SORTED_PAIRS)];
    expect(missing(pair, false, "vega")).toBeNull();
    expect(isReady([...pair].reverse(), false, "vega")).toBe(true);
    expect(primaryName(pair)).toBe("SortedPairs.txt");
    const body = joinContents([...pair].reverse());
    expect(body.indexOf("Cross Table")).toBeLessThan(body.indexOf("Pairing of round"));
  });

  it("asks for the cross table when only the pairing list is there, unless the roster is held", () => {
    const files = [pick("SortedPairs.txt", SORTED_PAIRS)];
    expect(missing(files, false, "vega")).toMatch(/crosstable.txt/);
    expect(missing(files, true, "vega")).toBeNull();
    expect(rosterNote(files, true)).toMatch(/Start numbers come from/);
    expect(rosterNote([pick("crosstable.txt", CROSSTABLE), ...files], true)).toBeNull();
  });

  it("asks for the pairing list when only the cross table is there", () => {
    expect(missing([pick("crosstable.txt", CROSSTABLE)], true, "vega")).toMatch(/SortedPairs.txt/);
  });

  it("sends each program's files back to the other", () => {
    expect(missing([pick("players.txt", PLAYERS), pick("pairings.txt", PAIRINGS)], false, "vega")).toMatch(
      /runs on Vega/,
    );
    expect(
      missing([pick("crosstable.txt", CROSSTABLE), pick("SortedPairs.txt", SORTED_PAIRS)], false, "swiss_manager"),
    ).toMatch(/runs on Swiss-Manager/);
  });
});

describe("collecting the files", () => {
  it("replaces a file of the same kind rather than keeping both", () => {
    const held = withFile([pick("old.txt", PLAYERS)], pick("new.txt", PLAYERS));
    expect(held.map((f) => f.name)).toEqual(["new.txt"]);
  });

  it("keeps the two kinds side by side", () => {
    const held = withFile([pick("players.txt", PLAYERS)], pick("pairings.txt", PAIRINGS));
    expect(held).toHaveLength(2);
  });

  it("a TRF replaces the text pair, and the pair replaces the TRF", () => {
    const pair = [pick("players.txt", PLAYERS), pick("pairings.txt", PAIRINGS)];
    expect(withFile(pair, pick("round.trf", TRF))).toHaveLength(1);
    expect(withFile([pick("round.trf", TRF)], pick("players.txt", PLAYERS))).toHaveLength(1);
  });
});

describe("what goes to the API", () => {
  it("sends the players first, whatever order they were chosen in", () => {
    const body = joinContents([pick("pairings.txt", PAIRINGS), pick("players.txt", PLAYERS)]);
    expect(body.indexOf("Nr;Name")).toBeLessThan(body.indexOf("Runde;Brett"));
  });

  it("records the name of the file that carries the round", () => {
    expect(primaryName([pick("players.txt", PLAYERS), pick("pairings.txt", PAIRINGS)])).toBe(
      "pairings.txt",
    );
    expect(primaryName([pick("round3.trf", TRF)])).toBe("round3.trf");
  });
});

describe("reading the file's bytes", () => {
  it("takes UTF-8 as it is", async () => {
    const file = new Blob([new TextEncoder().encode("Nr;Pkt\n1;2\u00bd\n")]);
    expect(await readText(file)).toBe("Nr;Pkt\n1;2\u00bd\n");
  });

  it("falls back to Windows-1252 so the half-point glyph survives", async () => {
    const bytes = new Uint8Array([0x4e, 0x72, 0x3b, 0x50, 0x6b, 0x74, 0x0a, 0x31, 0x3b, 0x32, 0xbd, 0x0a]);
    expect(await readText(new Blob([bytes]))).toBe("Nr;Pkt\n1;2\u00bd\n");
  });
});
