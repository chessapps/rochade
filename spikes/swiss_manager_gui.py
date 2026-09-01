"""Drive Swiss-Manager's GUI for the spike: export TRF16, export/import pairing files.

Throwaway, Windows-only, and deliberately small. Swiss-Manager is a Delphi/VCL
application, so its controls answer to pywinauto's win32 backend; menu items are
addressed by index because their text carries accelerators, tabs and the UI
language. Indices below are for **Swiss-Manager 15.0.0.3, German UI** -- run
`menus` first on any other build and adjust.

Needs its own environment, not the project's:

    python -m venv gui-env && gui-env\\Scripts\\pip install pywinauto pillow psutil
    gui-env\\Scripts\\python spikes\\swiss_manager_gui.py menus

Commands (Swiss-Manager must already be running with the tournament open):

    menus                          print the menu tree with indices and enabled state
    trf-export  OUT.trf            Extras -> FIDE-Daten-Export TRF16, through its dialogs,
                                   then copy the silently written file to OUT
    pairings-export OUT.txt LO HI  Extras -> Daten Import/Export -> Spielerauslosung (Text-File)
    pairings-import IN.txt         the mirror: import a pairing file into the open tournament
    shot NAME                      screenshot of the main form to shots/NAME.png

Everything here was used to produce `tests/fixtures/swiss_manager/` and the
observations in `docs/m0-swiss-manager.md`.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import time

from pywinauto import Application

EXE = r"C:\Program Files (x86)\SwissManagerUniCode\SwissManager.exe"
LISTEN = pathlib.Path.home() / "Documents" / "SwissManagerUniCode" / "Listen"
SHOTS = pathlib.Path(__file__).parent / "out" / "shots"

# Menu paths, (top-level index, item index). Verified on 15.0.0.3 German.
MENU_TRF_EXPORT = (7, 12)  # Extras -> FIDE-Daten-Export TRF16
MENU_IMP_EXP = (7, 14)  # Extras -> Daten Import/Export...


def connect() -> Application:
    return Application(backend="win32").connect(path=EXE, timeout=10)


def main_form(app: Application):
    """The real main window. TApplication is Delphi's hidden shell, not the form."""
    return app.window(class_name="TMainForm")


def menu_pick(app: Application, *indices: int) -> None:
    node = main_form(app).menu().items()[indices[0]]
    for i in indices[1:]:
        node = node.sub_menu().items()[i]
    node.select()
    time.sleep(1.2)


def visible(app: Application) -> dict[str, object]:
    """Class name -> window, for whatever Swiss-Manager has on screen right now."""
    out: dict[str, object] = {}
    for w in app.windows(visible_only=True, enabled_only=False, top_level_only=True):
        try:
            if w.class_name() != "TApplication":
                out[w.class_name()] = w
        except Exception:  # noqa: BLE001 - a window may vanish mid-enumeration
            continue
    return out


def answer_messages(app: Application, *buttons: str, rounds: int = 6) -> list[str]:
    """Click through Swiss-Manager's message boxes, preferring `buttons` in order.

    Returns the texts seen, so a run can be read back later. Stops when no
    message form is showing.
    """
    seen: list[str] = []
    for _ in range(rounds):
        wins = visible(app)
        if "TMessageForm" not in wins:
            return seen
        form = app.window(class_name="TMessageForm")
        texts = [c.window_text() for c in form.wrapper_object().descendants()]
        seen.extend(t for t in texts if len(t) > 5)
        for label in buttons:
            try:
                form.child_window(title=label, class_name="TButton").click()
                break
            except Exception:  # noqa: BLE001 - try the next label
                continue
        time.sleep(1.5)
    return seen


def menus(app: Application) -> None:
    for i, item in enumerate(main_form(app).menu().items()):
        print(f"[{i}] {item.text()!r}")
        try:
            for j, sub in enumerate(item.sub_menu().items()):
                flag = "" if sub.is_enabled() else "   (disabled)"
                print(f"    [{j}] {sub.text()!r}{flag}")
        except Exception as exc:  # noqa: BLE001
            print("    ", exc)


def trf_export(app: Application, out: pathlib.Path) -> None:
    """The FIDE export writes silently to Listen\\FIDE_Export_<tournament>.TXT."""
    before = {p: p.stat().st_mtime for p in LISTEN.glob("FIDE_Export_*.TXT")}
    menu_pick(app, *MENU_TRF_EXPORT)
    for _ in range(8):
        wins = visible(app)
        if "TMessageForm" in wins:
            # Message 189 (players without FIDE id) wants ok; 112 (results
            # missing, output anyway?) wants Ja -- that is the unplayed round.
            print("message:", answer_messages(app, "Ja", "ok", rounds=1))
            continue
        if "TFRDSel" in wins:
            d = app.window(class_name="TFRDSel")
            edits = [e.window_text() for e in d.wrapper_object().descendants(class_name="TEdit")]
            print(f"round selector: {edits[-1]} bis {edits[-2]}")
            d.child_window(title="OK", class_name="TBitBtn").click()
            time.sleep(2)
            continue
        break
    time.sleep(1)
    written = [p for p in LISTEN.glob("FIDE_Export_*.TXT") if p.stat().st_mtime > before.get(p, 0)]
    if not written:
        raise SystemExit("no export appeared in Listen -- check the dialogs (round dates set?)")
    shutil.copy(written[0], out)
    print(f"copied {written[0].name} ({written[0].stat().st_size} bytes) -> {out}")


def pairings_export(app: Application, out: pathlib.Path, lo: str, hi: str) -> None:
    menu_pick(app, *MENU_IMP_EXP)
    d = app.window(class_name="TFImpExp")
    d.child_window(title="Spielerauslosung (Text-File)", class_name="TRadioButton").click()
    d.child_window(class_name="TEdit", found_index=1).set_edit_text(lo)
    d.child_window(class_name="TEdit", found_index=2).set_edit_text(hi)
    d.child_window(title="Starten", class_name="TButton", found_index=0).click()
    time.sleep(2)
    dlg = app.window(class_name="#32770", title="Daten Exportieren")
    dlg.child_window(class_name="Edit").set_edit_text(str(out))
    time.sleep(0.4)
    dlg.child_window(title_re=".*peichern", class_name="Button").click()
    time.sleep(2)
    print("messages:", answer_messages(app, "ok", "OK", "Ja"))
    d.child_window(title="OK", class_name="TBitBtn").click()
    print(f"exported rounds {lo}-{hi} -> {out}")


def pairings_import(app: Application, path: pathlib.Path) -> None:
    menu_pick(app, *MENU_IMP_EXP)
    d = app.window(class_name="TFImpExp")
    d.child_window(title="Spielerauslosung", class_name="TRadioButton").click()
    time.sleep(0.3)
    d.child_window(title="Starten", class_name="TButton", found_index=1).click()
    time.sleep(2)
    dlg = app.window(class_name="#32770", title="Datei importieren")
    dlg.child_window(class_name="Edit").set_edit_text(str(path))
    time.sleep(0.4)
    dlg.child_window(title_re=".*ffnen", class_name="Button").click()
    time.sleep(3)
    print("messages:", answer_messages(app, "ok", "OK", "Ja"))
    d.child_window(title="OK", class_name="TBitBtn").click()
    print(f"imported {path} -- check Listen -> Ergebnisse; success is silent")


def shot(app: Application, name: str) -> None:
    from PIL import Image

    SHOTS.mkdir(parents=True, exist_ok=True)
    form = main_form(app).wrapper_object()
    form.set_focus()
    time.sleep(0.5)
    img = form.capture_as_image()
    if img.width > 1700:
        img = img.resize((1700, int(img.height * 1700 / img.width)), Image.LANCZOS)
    path = SHOTS / f"{name}.png"
    img.save(path)
    print(path)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    app = connect()
    command, args = argv[0], argv[1:]
    if command == "menus":
        menus(app)
    elif command == "trf-export":
        trf_export(app, pathlib.Path(args[0]))
    elif command == "pairings-export":
        pairings_export(app, pathlib.Path(args[0]), args[1], args[2])
    elif command == "pairings-import":
        pairings_import(app, pathlib.Path(args[0]))
    elif command == "shot":
        shot(app, args[0])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
