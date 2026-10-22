import pytest

from app.config import Settings


@pytest.fixture
def settings():
    return Settings(
        session_secret="a" * 32,
        oidc_issuer="https://idp.example.com",
        oidc_client_id="portal",
        oidc_redirect_uri="http://localhost:8000/auth/callback",
        openmetadata_base_url="https://om.example.com",
        om_admin_bot_token="test-admin-bot-token",
        openmetadata_auth_mode="admin_bot",
        oracle_user_allowlist="allowed@example.com",
    )
