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
    # `select_account` lets a user deliberately choose a different SSO account
    # after ending a portal session without signing them out of Google globally.
    oidc_login_prompt: str | None = "select_account"
    oidc_audience: str | None = None
    oidc_redirect_uri: AnyHttpUrl
    oidc_logout_uri: str | None = None
    oidc_email_claim: str = "email"
    # Used only when matching OpenMetadata users by their `name` field. If the
    # IdP does not issue it, the email local part is used as a safe fallback.
    oidc_username_claim: str | None = "preferred_username"
    openmetadata_base_url: AnyHttpUrl
    om_admin_bot_token: str = Field(min_length=1)
    openmetadata_api_version: str = "v1"
    openmetadata_auth_mode: Literal["admin_bot"] = "admin_bot"
    openmetadata_user_lookup_field: Literal["email", "name"] = "email"
    openmetadata_user_lookup_page_size: int = Field(default=100, ge=1, le=1000)
    openmetadata_user_lookup_max_pages: int = Field(default=100, ge=1, le=1000)
    openmetadata_tasks_path: str = "/tasks"
    openmetadata_task_scan_max_pages: int = Field(default=100, ge=1, le=1000)
    openmetadata_user_name_cache_ttl_seconds: int = Field(default=600, ge=300, le=600)
    # The task endpoint and task type are deployment-version dependent. Keep
    # them server-side rather than exposing OpenMetadata's task shape to users.
    openmetadata_access_request_task_path: str = "/tasks"
    openmetadata_access_request_task_type: str = "DataAccessRequest"
    openmetadata_data_product_publication_task_type: str = "DataProductPublication"
    openmetadata_access_request_expiration_days: int = Field(default=30, ge=1, le=365)
    openmetadata_catalog_page_size: int = Field(default=20, ge=1, le=100)
    openmetadata_timeout_seconds: float = 10
    database_queries_enabled: bool = False
    oracle_dsn: str | None = None
    # Dedicated provisioning principal. It is used only to create and remove a
    # short-lived proxy client; it must not be the portal's runtime proxy user.
    oracle_provisioner_user: str | None = None
    oracle_provisioner_password: str | None = None
    oracle_proxy_user: str | None = None
    oracle_proxy_password: str | None = None
    oracle_user_allowlist: str = ""
    oracle_query_schema: str = "APP"
    oracle_query_table: str = "CUSTOMERS"
    oracle_query_max_rows: int = Field(default=1_000, ge=1, le=10_000)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def oracle_allowlist(self) -> set[str]:
        return {item.strip().lower() for item in self.oracle_user_allowlist.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
