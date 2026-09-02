import { relativeTime, resultLabel } from "./format";

describe("resultLabel", () => {
  it("prints a played game as on the pairing list", () => {
    expect(resultLabel("1", "0")).toBe("1:0");
    expect(resultLabel("=", "=")).toBe("½:½");
    expect(resultLabel("0", "1")).toBe("0:1");
  });

  it("prints forfeits with the codes an arbiter knows", () => {
    expect(resultLabel("+", "-")).toBe("+:−");
    expect(resultLabel("-", "+")).toBe("−:+");
    expect(resultLabel("-", "-")).toBe("−:−");
  });

  it("prints a bye by what it was worth", () => {
    expect(resultLabel("U", " ", true)).toBe("1 · bye");
    expect(resultLabel("H", " ", true)).toBe("½ · bye");
    expect(resultLabel("Z", " ", true)).toBe("0 · absent");
  });

  it("is blank when there is no result", () => {
    expect(resultLabel(" ", " ")).toBe("");
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-09-02T14:30:00Z");

  it("steps from seconds to minutes to the clock", () => {
    expect(relativeTime("2026-09-02T14:29:58Z", now)).toBe("just now");
    expect(relativeTime("2026-09-02T14:29:40Z", now)).toBe("20s ago");
    expect(relativeTime("2026-09-02T14:26:00Z", now)).toBe("4 min ago");
    expect(relativeTime("2026-09-02T12:00:00Z", now)).toMatch(/\d/);
  });

  it("says never for nothing", () => {
    expect(relativeTime(null, now)).toBe("never");
  });
});
