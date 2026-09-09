import json
import pathlib
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROCHADE_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rochade:rochade@localhost:5432/rochade"
    #: Accept a bearer token as the staff subject verbatim, with no verification.
    #: Off by default: an insecure auth mode must be asked for, never inherited.
    #: With an OIDC issuer configured as well, a bearer shaped like a JWT goes
    #: to the issuer and anything else is taken as a dev subject -- so the
    #: smoke and browser scripts keep working against a stack that has Zitadel.
    dev_auth_enabled: bool = False
    #: Bring the database up to date when the API starts. On by default so a
    #: fresh checkout runs against an empty database; a deployment that
    #: migrates as its own step turns it off.
    migrate_on_start: bool = True

    #: The issuer as the browser sees it, e.g. https://auth.example.com. Setting
    #: it switches staff auth to OIDC.
    oidc_issuer: str = ""
    #: The public client the admin app signs in with. Handed to the browser by
    #: /api/auth/config; also the default audience, because a Zitadel access
    #: token names the client it was issued to.
    oidc_client_id: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    #: Where the API reaches the issuer from inside the stack when the public
    #: name does not resolve there (http://zitadel:8080 in compose). Requests
    #: still carry the issuer's host, which is how Zitadel finds its instance.
    oidc_internal_url: str = ""
    #: A JSON file the Zitadel setup step writes ({"issuer", "client_id",
    #: "project_id"}). Fills in whichever of the fields above are unset, so
    #: the client id that Zitadel generates never has to be copied by hand.
    oidc_config_file: str = ""

    #: Let a phone mint its own device by typing a tournament's join code.
    #: Off by default: a six-character code is short enough to guess at, and
    #: the QR is the intended way in. See `features/devices/join_device.py`.
    device_join_enabled: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]

    @property
    def token_audience(self) -> str:
        return self.oidc_audience or self.oidc_client_id

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer)

    def with_oidc_file(self) -> "Settings":
        """Fill unset OIDC fields from the setup file, when there is one."""
        if not self.oidc_config_file:
            return self
        path = pathlib.Path(self.oidc_config_file)
        if not path.is_file():
            return self
        written = json.loads(path.read_text(encoding="utf-8"))
        patch = {
            key: str(written[source])
            for key, source in (("oidc_issuer", "issuer"), ("oidc_client_id", "client_id"))
            if not getattr(self, key) and written.get(source)
        }
        return self.model_copy(update=patch) if patch else self


@lru_cache
def settings() -> Settings:
    return Settings().with_oidc_file()
