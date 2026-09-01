"""End-to-end smoke test against a running compose stack.

Not part of the test suite: this exercises the deployment, not the code --
migrations applied on boot, Caddy routing, both apps served, and one full round
trip through the real HTTP surface.
"""

import pathlib
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
TRF = (pathlib.Path(__file__).parent.parent / "tests/fixtures/round1_pairings.trf").read_bytes()
staff = {"Authorization": "Bearer smoke-arbiter"}


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}{f' -- {detail}' if detail else ''}")
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
    check("admin app is served at /admin", '<div id="root">' in http.get("/admin/").text)

    managers = http.get("/api/managers", headers=staff)
    check(
        "manager adapters are listed",
        managers.status_code == 200 and any(m["key"] == "vega" for m in managers.json()),
        managers.text,
    )

    created = http.post("/api/tournaments", json={"name": "Smoke Open"}, headers=staff)
    check("create tournament", created.status_code == 201, created.text)
    tournament = created.json()["id"]

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

print("\nthe loop closes end to end against the compose stack")
