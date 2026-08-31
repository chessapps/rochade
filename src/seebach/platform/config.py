from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEEBACH_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://seebach:seebach@localhost:5432/seebach"
    #: Bootstrap staff subject, used before Zitadel is wired up (M1-M3).
    dev_staff_subject: str = "dev-arbiter"
    dev_auth_enabled: bool = True

    oidc_issuer: str = ""
    oidc_audience: str = "seebach-api"
    oidc_jwks_url: str = ""

    device_token_ttl_hours: int = 14
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]


@lru_cache
def settings() -> Settings:
    return Settings()
