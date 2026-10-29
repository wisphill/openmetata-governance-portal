import sys
from types import SimpleNamespace

import pytest

from app.database.oracle_proxy_query import OracleProxyQueryService


class Cursor:
    description = [("CUSTOMER_ID",), ("CUSTOMER_NAME",)]

    def __init__(self, commands):
        self.commands = commands

    def execute(self, statement, parameters=None):
        self.commands.append((statement, parameters))

    def fetchmany(self, limit):
        assert limit == 1000
        return [(1001, "Acme Retail"), (1002, "Northwind Traders")]

    def close(self):
        return None


class Connection:
    def __init__(self, commands):
        self.commands = commands
        self.closed = False

    def cursor(self):
        return Cursor(self.commands)

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_query_uses_configured_proxy_without_creating_a_client_or_granting_permissions(settings, monkeypatch):
    settings.database_queries_enabled = True
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_proxy_user = "portal_proxy"
    settings.oracle_proxy_password = "proxy-password"
    commands = []
    connection_args = {}
    connection = Connection(commands)

    def connect(**kwargs):
        connection_args.update(kwargs)
        return connection

    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=connect))

    result = await OracleProxyQueryService(settings).execute("SELECT * FROM customers;", {})

    assert result.columns == ["customer_id", "customer_name"]
    assert result.items[0]["customer_name"] == "Acme Retail"
    assert connection_args == {
        "user": "portal_proxy",
        "password": "proxy-password",
        "dsn": "oracle.example.com:1521/freepdb1",
    }
    assert commands == [("SELECT * FROM customers", {})]
    assert connection.closed


@pytest.mark.asyncio
async def test_query_does_not_require_a_provisioning_principal(settings, monkeypatch):
    settings.database_queries_enabled = True
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_proxy_user = "portal_proxy"
    settings.oracle_proxy_password = "proxy-password"
    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=lambda **_: Connection([])))

    await OracleProxyQueryService(settings).execute("SELECT 1 FROM dual", {})


def test_query_rejects_non_read_only_statements(settings):
    with pytest.raises(PermissionError, match="read-only"):
        OracleProxyQueryService(settings)._read_only_statement("SELECT 1 FROM dual; DELETE FROM users")
