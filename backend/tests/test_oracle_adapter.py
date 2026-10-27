import sys
from types import SimpleNamespace

import pytest

from app.database.oracle import OracleAdapter


@pytest.mark.asyncio
async def test_oracle_proxy_client_identity_is_quoted(settings, monkeypatch):
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_proxy_user = "portal_proxy"
    settings.oracle_proxy_password = "proxy-password"
    connection_args = {}

    def connect(**kwargs):
        connection_args.update(kwargs)
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=connect))
    adapter = OracleAdapter(settings)

    await adapter.connect("om::123")

    assert connection_args["user"] == 'portal_proxy["om::123"]'
