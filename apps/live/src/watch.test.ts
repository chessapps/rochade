import { WATCH_KEY, _resetWatchCache, isWatching, readWatchList, toggleWatch } from "./watch";

const ELISE = { slug: "club-open", sectionId: "s-a", startRank: 3, name: "Dubois, Elise" };

beforeEach(() => {
  localStorage.clear();
  _resetWatchCache();
});

describe("the watch list", () => {
  it("toggles and survives a reload", () => {
    expect(toggleWatch(ELISE)).toBe(true);
    expect(isWatching(ELISE)).toBe(true);

    _resetWatchCache();
    expect(readWatchList()).toEqual([ELISE]);

    expect(toggleWatch({ ...ELISE, name: "renamed" })).toBe(false);
    expect(readWatchList()).toEqual([]);
  });

  it("ignores whatever is not a watch entry in storage", () => {
    localStorage.setItem(WATCH_KEY, JSON.stringify([ELISE, { junk: true }, "x"]));
    expect(readWatchList()).toEqual([ELISE]);
    localStorage.setItem(WATCH_KEY, "not json");
    _resetWatchCache();
    expect(readWatchList()).toEqual([]);
  });
});
