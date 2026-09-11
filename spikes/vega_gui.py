"""Drive Vega's GUI for the spike: clicks by coordinate, keys, screenshots.

Throwaway, Windows-only. Vega is an Ultimate++ application and exposes no
controls to pywinauto (`uia` sees nothing, `win32` sees one `UPP-CLASS-W`
window with no children and no menu handle), so this drives it the crude
way: the main window is moved to a fixed rectangle, everything is a click at
window-relative pixel coordinates read off a screenshot, and every step ends
in another screenshot. Coordinates below are for **Vega 12.1.8, English UI,
250 % scaling, the window at (1160, 230) 2695x2065 px** -- take a `shot`
first on any other box and read the numbers off it.

Needs its own environment, not the project's:

    python -m venv gui-env && gui-env\\Scripts\\pip install pywinauto pillow psutil
    gui-env\\Scripts\\python spikes\\vega_gui.py shot main

Commands (Vega must already be running):

    settle                  after a restart: click through the licence and
                            "Insert missing result" notices, restore the window
    shot NAME               screenshot of the window (plus a margin) to out/shots/NAME.png
    click X Y [NAME]        left click at window-relative physical pixels
    dclick X Y [NAME]       double click
    rclick X Y [NAME]       right click
    keys "{ESC}" [NAME]     pywinauto send_keys syntax
    type TEXT [NAME]        literal text
    seq step;step;...       c:X,Y  d:X,Y  r:X,Y  k:KEYS  t:TEXT  w:SECS  s:NAME

Everything here was used to produce `tests/fixtures/vega/` and the
observations in `docs/m0-vega.md`; the screenshots that record each step are
under `spikes/out/shots/`. The whole run, with the coordinates that worked on
2026-09-11, is in the session that wrote it; the menus that matter are
`File → Import tournament in FIDE format - TRF2026`, `File → Tournament
manager → Modify Tournament`, `Round Manager → Automatic` and
`Round Manager → Modify Pairing`.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as W
import pathlib
import sys
import time

from PIL import ImageGrab
from pywinauto import keyboard

OUT = pathlib.Path(__file__).parent / "out" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
u = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # older Windows
    u.SetProcessDPIAware()

#: Where the main window is put, so that coordinates read off one screenshot
#: stay valid for the next run.
RECT = (1160, 230, 2695, 2065)


def rect(h: int) -> tuple[int, int, int, int]:
    r = W.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def windows() -> list[tuple[int, str]]:
    """Every visible U++ top-level window, (handle, title)."""
    out: list[tuple[int, str]] = []
    h = u.FindWindowW("UPP-CLASS-W", None)
    while h:
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, buf, 256)
        if u.IsWindowVisible(h):
            out.append((h, buf.value))
        h = u.FindWindowExW(0, h, "UPP-CLASS-W", None)
    return out


def main_window() -> int:
    """The widest visible window whose title names the program."""
    best, best_w = 0, -1
    for h, title in windows():
        if "Vega 12" in title:
            left, _, right, _ = rect(h)
            if right - left > best_w:
                best, best_w = h, right - left
    return best


def front() -> int:
    h = main_window()
    if not h:
        raise SystemExit("no Vega main window; is it running, and past its start-up notices?")
    if u.IsIconic(h):
        u.ShowWindow(h, 9)
    u.SetForegroundWindow(h)
    time.sleep(0.5)
    return h


def shot(name: str) -> None:
    """Grab the main window plus a margin (popups may extend past it)."""
    h = main_window()
    left, top, right, bottom = rect(h)
    box = (max(left - 200, 0), max(top - 100, 0), right + 200, bottom + 100)
    img = ImageGrab.grab(bbox=box, all_screens=True)
    path = OUT / f"{name}.png"
    img.save(path)
    print("shot", path.name, img.size, "origin", box[:2])


def click(x: int, y: int, button: str = "left", double: bool = False) -> None:
    left, top, _, _ = rect(main_window())
    u.SetCursorPos(left + x, top + y)
    time.sleep(0.15)
    down, up = (2, 4) if button == "left" else (8, 16)
    u.mouse_event(down, 0, 0, 0, 0)
    u.mouse_event(up, 0, 0, 0, 0)
    if double:
        time.sleep(0.08)
        u.mouse_event(down, 0, 0, 0, 0)
        u.mouse_event(up, 0, 0, 0, 0)
    time.sleep(0.6)


def settle() -> None:
    """Click OK on the small notices Vega shows on start-up, then place the window."""
    for _ in range(12):
        if main_window():
            break
        for h, title in windows():
            if "Vega 12" in title:
                continue
            left, top, right, bottom = rect(h)
            u.SetForegroundWindow(h)
            time.sleep(0.4)
            # OK sits centred near the bottom of every notice seen so far.
            u.SetCursorPos((left + right) // 2, bottom - 80)
            time.sleep(0.2)
            u.mouse_event(2, 0, 0, 0, 0)
            time.sleep(0.1)
            u.mouse_event(4, 0, 0, 0, 0)
            print("dismissed", repr(title), (left, top, right, bottom))
            time.sleep(2)
        time.sleep(1.5)
    h = main_window()
    if not h:
        raise SystemExit("main window never appeared")
    u.MoveWindow(h, *RECT, True)
    time.sleep(1)
    front()
    print("main", rect(h))


def run(steps: list[str]) -> None:
    for step in steps:
        if not step:
            continue
        kind, _, arg = step.partition(":")
        if kind in ("c", "d", "r"):
            x, y = (int(v) for v in arg.split(","))
            click(x, y, "right" if kind == "r" else "left", double=kind == "d")
        elif kind == "k":
            keyboard.send_keys(arg, pause=0.05)
            time.sleep(0.4)
        elif kind == "t":
            keyboard.send_keys(arg, with_spaces=True, with_tabs=False, pause=0.02)
            time.sleep(0.3)
        elif kind == "w":
            time.sleep(float(arg))
        elif kind == "s":
            shot(arg)
        else:
            raise SystemExit(f"unknown step {step!r}")


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "settle":
        settle()
        return
    front()
    if cmd == "shot":
        shot(args[0])
    elif cmd in ("click", "dclick", "rclick"):
        click(int(args[0]), int(args[1]), "right" if cmd == "rclick" else "left", cmd == "dclick")
        if len(args) > 2:
            shot(args[2])
    elif cmd == "keys":
        keyboard.send_keys(args[0], pause=0.05)
        time.sleep(0.5)
        if len(args) > 1:
            shot(args[1])
    elif cmd == "type":
        keyboard.send_keys(args[0], with_spaces=True, pause=0.02)
        if len(args) > 1:
            shot(args[1])
    elif cmd == "seq":
        run(args[0].split(";"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
