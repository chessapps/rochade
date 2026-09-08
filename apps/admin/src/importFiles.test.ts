import { describe, expect, it } from "vitest";

import { isReady, joinContents, missing, primaryName, rosterNote, sniff, withFile } from "./importFiles";

const PLAYERS = "Nr;Name;Titel;Identnr;EloNat;EloInt;Geburt;Fed;Sex;Nachname;Vorname\r\n1;Brunner Livia;WGM;;0;2447;01.06.1992;SUI;W;Brunner;Livia\r\n";
const PAIRINGS = "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS\r\n1;1;0;0;1;51;0;0;;0:0;0;;\r\n";
const TRF = "012 Seebach Open 2026\r\n001    1 m    Baumann, Lukas                 2201 SUI\r\n";

const pick = (name: string, content: string) => ({ name, content, kind: sniff(content) });

describe("telling the manager's files apart", () => {
  it("knows each of the three by its first line", () => {
    expect(sniff(PLAYERS)).toBe("players");
    expect(sniff(PAIRINGS)).toBe("pairings");
    expect(sniff(TRF)).toBe("trf");
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
