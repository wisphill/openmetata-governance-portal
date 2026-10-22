from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    portal_public_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"
    session_secret: str = Field(min_length=32)
    session_cookie_secure: bool = True
    oidc_issuer: AnyHttpUrl
    oidc_client_id: str
    oidc_client_secret: str | None = None
    oidc_scopes: str = "openid profile email"
    oidc_audience: str | None = None
    oidc_redirect_uri: AnyHttpUrl
    oidc_logout_uri: str | None = None
    oidc_email_claim: str = "email"
    openmetadata_base_url: AnyHttpUrl
    openmetadata_api_version: str = "v1"
    openmetadata_auth_mode: Literal["user_token"] = "user_token"
    openmetadata_user_lookup_field: Literal["email", "name"] = "email"
    openmetadata_tasks_path: str = "/feed"
    openmetadata_timeout_seconds: float = 10
    database_queries_enabled: bool = False
    oracle_dsn: str | None = None
    oracle_proxy_user: str | None = None
    oracle_proxy_password: str | None = None
    oracle_user_allowlist: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def oracle_allowlist(self) -> set[str]:
        return {item.strip().lower() for item in self.oracle_user_allowlist.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
