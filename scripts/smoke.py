"""End-to-end smoke test against a running compose stack.

Not part of the test suite: this exercises the deployment, not the code --
migrations applied on boot, Caddy routing, both apps served, and one full round
trip through the real HTTP surface for each manager adapter.
"""

import pathlib
import re
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8092"
FIXTURES = pathlib.Path(__file__).parent.parent / "tests/fixtures"
TRF = (FIXTURES / "round1_pairings.trf").read_bytes()
#: A real Swiss-Manager export: round 3 paired and unplayed, rounds 1-2 played.
SM_TRF = (FIXTURES / "swiss_manager/round3_paired.trf").read_bytes()
SM_HEADER = "Runde;Brett;IdentW;IdentS;NrW;NrS;ErgW;ErgS;Kontumaz;Erg;Mnr;ErgEloW;ErgEloS"
staff = {"Authorization": "Bearer smoke-arbiter"}

# Adapter notes carry arrows and umlauts; a cp1252 console must not be what fails.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}{f' -- {detail}' if not condition else ''}")
    if not condition:
        raise SystemExit(1)


def await_stack(http: httpx.Client, timeout: float = 90.0) -> None:
    """The API applies migrations on boot, so the stack is up before it is ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if http.get("/health").json() == {"status": "ok"}:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise SystemExit("the stack never became ready")


with httpx.Client(base_url=BASE, timeout=20.0, follow_redirects=True) as http:
    await_stack(http)
    check("health", http.get("/health").json() == {"status": "ok"})
    check("hall app is served at the root", '<div id="root">' in http.get("/").text)
    admin_html = http.get("/admin/").text
    check("admin app is served at /admin", '<div id="root">' in admin_html)
    # The shell alone proves nothing: the admin app is served under a prefix,
    # so its script has to be reachable at the URL the HTML names.
    script = re.search(r'<script[^>]+src="([^"]+)"', admin_html)
    asset = http.get(script.group(1)) if script else None
    served_js = asset is not None and "javascript" in asset.headers.get("content-type", "")
    check(
        "admin app's script loads from under /admin",
        served_js and asset is not None and asset.status_code == 200,
        script.group(1) if script else "no <script src> in the shell",
    )

    managers = http.get("/api/managers", headers=staff)
    keys = {m["key"] for m in managers.json()} if managers.status_code == 200 else set()
    check("manager adapters are listed", keys >= {"vega", "swiss_manager"}, managers.text)
    verified = {m["key"]: m["verified"] for m in managers.json()}
    check("Swiss-Manager is the verified one", verified["swiss_manager"] and not verified["vega"])

    created = http.post(
        "/api/tournaments", json={"name": "Smoke Open", "manager": "vega"}, headers=staff
    )
    check("create tournament", created.status_code == 201, created.text)
    tournament = created.json()["id"]

    # --- section A, through the Vega adapter ---------------------------------
    content = TRF.decode("utf-8")
    preview = http.post(
        f"/api/tournaments/{tournament}/imports/preview",
        json={"section_name": "A", "content": content},
        headers=staff,
    )
    check("preview", preview.status_code == 200 and preview.json()["boards"] == 4, preview.text)

    imported = http.post(
        f"/api/tournaments/{tournament}/imports",
        json={"section_name": "A", "content": content, "filename": "r1.trf"},
        headers=staff,
    )
    check("import", imported.status_code == 201, imported.text)
    round_id = imported.json()["round_id"]

    issued = http.post(f"/api/tournaments/{tournament}/devices", json={}, headers=staff)
    check("issue device token", issued.status_code == 201, issued.text)
    phone = {"Authorization": f"Device {issued.json()['token']}"}

    boards = http.get(f"/api/tournaments/{tournament}/boards", headers=phone)
    check("hall board list", boards.status_code == 200 and len(boards.json()["boards"]) == 4)

    for board in boards.json()["boards"]:
        claimed = http.post(
            f"/api/games/{board['game_id']}/claim",
            json={"result": "draw"},
            headers={**phone, "Idempotency-Key": f"smoke-{board['game_id']}"},
        )
        check(f"claim board {board['board']}", claimed.status_code == 200, claimed.text)

    # A retry of every claim must change nothing.
    for board in boards.json()["boards"]:
        http.post(
            f"/api/games/{board['game_id']}/claim",
            json={"result": "draw"},
            headers={**phone, "Idempotency-Key": f"smoke-{board['game_id']}"},
        )
    queue = http.get(f"/api/tournaments/{tournament}/queue", headers=staff).json()
    check("retries did not create disputes", queue["disputed"] == 0, str(queue))

    released = http.post(f"/api/rounds/{round_id}/release", json={}, headers=staff)
    check("release", released.status_code == 200 and released.json()["confirmed"] == 4)

    exported = http.post(f"/api/rounds/{round_id}/export", json={}, headers=staff)
    check("export", exported.status_code == 200, exported.text)
    body = exported.json()
    check("export filename", body["filename"] == "A-round1.trf", body["filename"])
    check("export names its manager", body["manager"] == "vega", body["manager"])
    check("export names its format", body["file_format"] == "trf16", body["file_format"])
    check("export wrote every board", body["boards_written"] == 4)
    check("results are in the file", body["content"].count(" =") >= 8)

    frozen = http.post(f"/api/rounds/{round_id}/export", json={}, headers=staff)
    check("round is frozen after export", frozen.status_code == 409, frozen.text)

    # --- a second tournament on Swiss-Manager, with a real export as B ---------
    # The program is fixed per tournament, so the Swiss-Manager leg needs its own.
    sm_created = http.post(
        "/api/tournaments",
        json={"name": "Smoke Open (Swiss-Manager)", "manager": "swiss_manager"},
        headers=staff,
    )
    check("create a Swiss-Manager tournament", sm_created.status_code == 201, sm_created.text)
    vega_tournament, tournament = tournament, sm_created.json()["id"]
    sm_content = SM_TRF.decode("utf-8")
    sm_import = http.post(
        f"/api/tournaments/{tournament}/imports",
        json={"section_name": "B", "content": sm_content},
        headers=staff,
    )
    check("import a Swiss-Manager export as B", sm_import.status_code == 201, sm_import.text)
    check("it is round 3", sm_import.json()["round_number"] == 3, sm_import.text)
    sm_round = sm_import.json()["round_id"]

    detail = http.get(f"/api/tournaments/{tournament}", headers=staff).json()
    check(
        "the tournament names its program",
        detail["manager_label"] == "Swiss-Manager",
        detail["manager_label"],
    )
    labels = {s["name"]: s["manager_label"] for s in detail["sections"]}
    check(
        "the section took the tournament's program", labels == {"B": "Swiss-Manager"}, str(labels)
    )
    vega_detail = http.get(f"/api/tournaments/{vega_tournament}", headers=staff).json()
    check(
        "the Vega tournament stayed on Vega",
        vega_detail["manager_label"] == "Vega",
        vega_detail["manager_label"],
    )

    # A phone admitted to this tournament sees B's open round: four games and
    # the bye, greyed out as already entered.
    sm_issued = http.post(f"/api/tournaments/{tournament}/devices", json={}, headers=staff)
    phone = {"Authorization": f"Device {sm_issued.json()['token']}"}
    hall = http.get(f"/api/tournaments/{tournament}/boards", headers=phone).json()["boards"]
    check("hall shows the open round only", len(hall) == 5, str(len(hall)))
    check("the bye is shown as entered", [b["entered"] for b in hall if b["is_bye"]] == [True])
    sm_boards = sorted((b for b in hall if not b["is_bye"]), key=lambda b: b["board"])
    check(
        "board numbers are Swiss-Manager's",
        [b["white_name"] for b in sm_boards][:2] == ["Mueller,Tobias", "Baumann,Lukas"],
        str([(b["board"], b["white_name"]) for b in sm_boards]),
    )

    for board in sm_boards:
        http.post(
            f"/api/games/{board['game_id']}/claim",
            json={"result": "white_win"},
            headers={**phone, "Idempotency-Key": f"smoke-sm-{board['game_id']}"},
        )
    released = http.post(f"/api/rounds/{sm_round}/release", json={}, headers=staff)
    check("release B", released.status_code == 200, released.text)
    sm_export = http.post(f"/api/rounds/{sm_round}/export", json={}, headers=staff)
    check("export B", sm_export.status_code == 200, sm_export.text)
    body = sm_export.json()
    lines = body["content"].splitlines()
    check("B is a pairing file", body["filename"] == "B-round3.txt" and lines[0] == SM_HEADER)
    check(
        "every board and the bye are rows",
        len(lines) == 6 and lines[-1].endswith(";6;-1;0;0;;0:0;0;;"),
        body["content"],
    )
    check("results spelt for Swiss-Manager", all(";1;0;;1:0;" in ln for ln in lines[1:5]), lines[1])
    check("hand-off names the menu", "Daten Import/Export" in body["next_step"], body["next_step"])

    # --- a third tournament Rochade pairs itself -------------------------------
    # No files anywhere: players in, a pairing out, the vendored engine inside
    # the image doing the work.
    check("Rochade's own program is listed", "gacrux" in keys, str(keys))
    gx_created = http.post(
        "/api/tournaments",
        json={"name": "Smoke Open (Rochade)", "manager": "gacrux"},
        headers=staff,
    )
    check("create a Rochade-paired tournament", gx_created.status_code == 201, gx_created.text)
    tournament = gx_created.json()["id"]
    refused = http.post(
        f"/api/tournaments/{tournament}/imports",
        json={"section_name": "A", "content": content},
        headers=staff,
    )
    check("an import is refused", refused.status_code == 409, refused.text)

    opened = http.post(
        f"/api/tournaments/{tournament}/sections",
        json={"name": "A", "declared_rounds": 3, "top_board_colour": "white"},
        headers=staff,
    )
    check("open a section", opened.status_code == 201, opened.text)
    section = opened.json()["section_id"]
    roster = [
        ("Baumann, Lukas", 2201),
        ("Chen, Wei", 2150),
        ("Dubois, Elise", 2098),
        ("Egger, Tobias", 2044),
        ("Fischer, Jonas", 1987),
        ("Gruber, Sarah", 1922),
        ("Huber, Marco", 1870),
        ("Iten, Nadia", 1804),
        ("Jenni, Rafael", 1755),
    ]
    for name, rating in roster:
        added = http.post(
            f"/api/sections/{section}/players", json={"name": name, "rating": rating}, headers=staff
        )
        check(f"enter {name}", added.status_code == 201, added.text)

    plan = http.post(f"/api/sections/{section}/pairings/preview", json={}, headers=staff)
    check("pairing preview", plan.status_code == 200 and len(plan.json()["boards"]) == 4, plan.text)
    paired = http.post(f"/api/sections/{section}/pairings", json={}, headers=staff)
    check("pair round 1", paired.status_code == 201 and paired.json()["byes"] == 1, paired.text)
    gx_round = paired.json()["round_id"]

    gx_issued = http.post(f"/api/tournaments/{tournament}/devices", json={}, headers=staff)
    phone = {"Authorization": f"Device {gx_issued.json()['token']}"}
    hall = http.get(f"/api/tournaments/{tournament}/boards", headers=phone).json()["boards"]
    check("hall shows the paired round", len(hall) == 5, str(len(hall)))
    for board in (b for b in hall if not b["is_bye"]):
        http.post(
            f"/api/games/{board['game_id']}/claim",
            json={"result": "white_win"},
            headers={**phone, "Idempotency-Key": f"smoke-gx-{board['game_id']}"},
        )
    released = http.post(f"/api/rounds/{gx_round}/release", json={}, headers=staff)
    check(
        "release computes the standings",
        released.status_code == 200 and released.json()["standings_computed"] is True,
        released.text,
    )
    table = http.get(f"/api/tournaments/{tournament}/standings", headers=staff).json()
    rows = table["sections"][0]["rows"]
    check(
        "nine players ranked after round 1", len(rows) == 9 and rows[0]["rank"] == 1, str(rows[:2])
    )
    check(
        "tie-break columns are labelled",
        table["sections"][0]["tiebreak_names"] == ["BH/C1", "BH", "SB"],
        str(table["sections"][0]["tiebreak_names"]),
    )

    paired2 = http.post(f"/api/sections/{section}/pairings", json={}, headers=staff)
    check(
        "pair round 2 closes round 1",
        paired2.json().get("previous_round_closed") == 1,
        paired2.text,
    )
    undone = http.delete(f"/api/rounds/{paired2.json()['round_id']}", headers=staff)
    check("unpair round 2", undone.status_code == 200, undone.text)
    again = http.post(f"/api/sections/{section}/pairings", json={}, headers=staff)
    check("pair round 2 again", again.status_code == 201, again.text)
    no_export = http.post(f"/api/rounds/{gx_round}/export", json={}, headers=staff)
    check("nothing to export", no_export.status_code == 409, no_export.text)

print("\nthe loop closes end to end against the compose stack, for all three programs")
