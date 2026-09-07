from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEEBACH_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://seebach:seebach@localhost:5432/seebach"
    #: Accept a bearer token as the staff subject verbatim, with no verification.
    #: This is how M1-M3 run before Zitadel is wired up, and it is off by
    #: default: an insecure auth mode must be asked for, never inherited.
    dev_auth_enabled: bool = False
    #: Bring the database up to date when the API starts. On by default so a
    #: fresh checkout runs against an empty database; a deployment that
    #: migrates as its own step turns it off.
    migrate_on_start: bool = True

    oidc_issuer: str = ""
    oidc_audience: str = "seebach-api"
    oidc_jwks_url: str = ""

    device_token_ttl_hours: int = 14
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]


@lru_cache
def settings() -> Settings:
    return Settings()
