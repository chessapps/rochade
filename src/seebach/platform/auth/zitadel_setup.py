"""Register the admin app with a fresh Zitadel, once, and write down what it got.

Zitadel generates client ids; nothing declarative hands one out at first
start. So the compose stack runs this after Zitadel is healthy, with the
personal access token Zitadel wrote for its bootstrap machine user:

    python -m seebach.platform.auth.zitadel_setup

It makes a project and one OIDC app for the arbiter frontend (a public
client, authorization code with PKCE, JWT access tokens), idempotently -- a
second run finds both by name and only refreshes the redirect URIs. The
result lands in a JSON file the API reads at start (SEEBACH_OIDC_CONFIG_FILE).

Environment:
    ZITADEL_URL          where Zitadel answers from inside the stack, http://zitadel:8080
    ZITADEL_ISSUER       the public issuer, what the browser and the tokens say
    ZITADEL_PAT_FILE     the bootstrap machine user's PAT
    SEEBACH_PUBLIC_URL   the app's origin, for the redirect URIs
    SEEBACH_OIDC_CONFIG_FILE  where to write the result
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from typing import Any

import httpx

PROJECT_NAME = "seebach"
APP_NAME = "arbiter"


def main() -> int:
    base = os.environ["ZITADEL_URL"].rstrip("/")
    issuer = os.environ["ZITADEL_ISSUER"].rstrip("/")
    public_url = os.environ["SEEBACH_PUBLIC_URL"].rstrip("/")
    out = pathlib.Path(os.environ["SEEBACH_OIDC_CONFIG_FILE"])
    pat = _read_pat(pathlib.Path(os.environ["ZITADEL_PAT_FILE"]))

    # Zitadel finds its instance by the Host header, not by where the request
    # arrived, so calls from inside the stack must still carry the public name.
    headers = {"Authorization": f"Bearer {pat}", "Host": httpx.URL(issuer).netloc.decode()}
    with httpx.Client(base_url=base, headers=headers, timeout=30.0) as client:
        _await_ready(client)
        project_id = _ensure_project(client)
        client_id = _ensure_app(client, project_id, public_url)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"issuer": issuer, "client_id": client_id, "project_id": project_id}, indent=2),
        encoding="utf-8",
    )
    print(f"zitadel: app {APP_NAME!r} in project {PROJECT_NAME!r} is client {client_id}")
    return 0


def _read_pat(path: pathlib.Path, timeout: float = 120.0) -> str:
    """Zitadel writes the PAT on first start; wait for it rather than race it."""
    deadline = time.monotonic() + timeout
    while True:
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return path.read_text(encoding="utf-8").strip()
        if time.monotonic() > deadline:
            raise SystemExit(f"no personal access token at {path} after {timeout:.0f}s")
        time.sleep(2)


def _await_ready(client: httpx.Client, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            response = client.get("/debug/ready")
            if response.status_code == 200:
                return
            last = f"{response.status_code} {response.text[:200]}"
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(2)
    raise SystemExit(f"zitadel not ready after {timeout:.0f}s: {last}")


def _ensure_project(client: httpx.Client) -> str:
    found = _post(
        client,
        "/management/v1/projects/_search",
        {"queries": [{"nameQuery": {"name": PROJECT_NAME, "method": "TEXT_QUERY_METHOD_EQUALS"}}]},
    )
    for project in found.get("result", []):
        return str(project["id"])
    created = _post(
        client,
        "/management/v1/projects",
        {"name": PROJECT_NAME, "projectRoleAssertion": False, "hasProjectCheck": False},
    )
    return str(created["id"])


def _ensure_app(client: httpx.Client, project_id: str, public_url: str) -> str:
    redirect_uris = [f"{public_url}/admin/callback"]
    post_logout_uris = [f"{public_url}/admin/"]
    dev_mode = public_url.startswith("http://")

    # Everything this script owns about the app. A second run puts the app
    # back to exactly this, so a change here or a hand edit in the console
    # is reconciled rather than left to drift.
    desired: dict[str, Any] = {
        "redirectUris": redirect_uris,
        "postLogoutRedirectUris": post_logout_uris,
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_USER_AGENT",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
        # A JWT, so the API can verify it against the JWKS without a round
        # trip to the introspection endpoint on every request.
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": False,
        "idTokenRoleAssertion": False,
        "idTokenUserinfoAssertion": True,
        # Zitadel refuses http:// redirect URIs unless the app is in dev mode.
        "devMode": dev_mode,
    }

    found = _post(
        client,
        f"/management/v1/projects/{project_id}/apps/_search",
        {"queries": [{"nameQuery": {"name": APP_NAME, "method": "TEXT_QUERY_METHOD_EQUALS"}}]},
    )
    for app in found.get("result", []):
        app_id = str(app["id"])
        oidc = app.get("oidcConfig") or {}
        if any(_differs(oidc.get(key), value) for key, value in desired.items()):
            _put(client, f"/management/v1/projects/{project_id}/apps/{app_id}/oidc_config", desired)
            print(f"zitadel: app {APP_NAME!r} brought back to the configuration here")
        return str(oidc["clientId"])

    created = _post(
        client, f"/management/v1/projects/{project_id}/apps/oidc", {"name": APP_NAME, **desired}
    )
    return str(created["clientId"])


def _differs(current: Any, desired: Any) -> bool:
    if isinstance(desired, list):
        return sorted(current or []) != sorted(desired)
    # Zitadel omits false booleans from its answers.
    if isinstance(desired, bool):
        return bool(current) != desired
    return bool(current != desired)


def _post(client: httpx.Client, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    if response.status_code >= 400:
        raise SystemExit(f"POST {path} -> {response.status_code}: {response.text[:500]}")
    data: dict[str, Any] = response.json()
    return data


def _put(client: httpx.Client, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.put(path, json=body)
    if response.status_code >= 400:
        raise SystemExit(f"PUT {path} -> {response.status_code}: {response.text[:500]}")
    data: dict[str, Any] = response.json()
    return data


if __name__ == "__main__":
    sys.exit(main())
