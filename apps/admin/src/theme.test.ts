import { apply, readChoice, resolve, setChoice, THEME_KEY } from "./theme";

describe("theme", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("follows the system unless told otherwise", () => {
    expect(readChoice()).toBe("system");
    expect(resolve("system", "dark")).toBe("dark");
    expect(resolve("system", "light")).toBe("light");
    expect(resolve("light", "dark")).toBe("light");
    expect(resolve("dark", "light")).toBe("dark");
  });

  it("remembers an explicit choice and forgets it again for system", () => {
    setChoice("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");

    setChoice("system");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(readChoice()).toBe("system");
  });

  it("ignores junk in storage", () => {
    localStorage.setItem(THEME_KEY, "sepia");
    expect(readChoice()).toBe("system");
    expect(["light", "dark"]).toContain(apply(readChoice()));
  });
});
