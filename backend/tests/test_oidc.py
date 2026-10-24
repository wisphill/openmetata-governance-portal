from urllib.parse import parse_qs, urlparse

from app.auth.oidc import OidcClient
from app.auth.session import SessionStore


class DiscoveryOidcClient(OidcClient):
    async def discovery(self) -> dict:
        return {"authorization_endpoint": "https://accounts.example.com/authorize"}


async def test_login_url_requests_an_account_chooser(settings):
    session = SessionStore("a" * 32).create_pending()

    url = await DiscoveryOidcClient(settings).authorization_url(session)

    assert parse_qs(urlparse(url).query)["prompt"] == ["select_account"]


async def test_login_url_omits_prompt_when_disabled(settings):
    settings.oidc_login_prompt = None
    session = SessionStore("a" * 32).create_pending()

    url = await DiscoveryOidcClient(settings).authorization_url(session)

    assert "prompt" not in parse_qs(urlparse(url).query)
