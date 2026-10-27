import re
import sys
from types import SimpleNamespace

import pytest

from app.database.oracle_temporary_proxy import OracleTemporaryProxyQueryService


class Cursor:
    def __init__(self, commands, query=False):
        self.commands = commands
        self.query = query
        self.description = [("CUSTOMER_ID",), ("CUSTOMER_NAME",)] if query else None

    def execute(self, statement, parameters=None):
        self.commands.append((statement, parameters))

    def fetchmany(self, limit):
        assert limit == 1000
        return [(1001, "Acme Retail"), (1002, "Northwind Traders")]

    def close(self):
        return None


class Connection:
    def __init__(self, commands, query=False):
        self.commands = commands
        self.query = query

    def cursor(self):
        return Cursor(self.commands, self.query)

    def close(self):
        return None


@pytest.mark.asyncio
async def test_query_uses_and_removes_a_temporary_proxy_client(settings, monkeypatch):
    settings.database_queries_enabled = True
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    settings.oracle_proxy_user = "portal_proxy"
    settings.oracle_proxy_password = "proxy-password"
    commands = []
    connections = []

    def connect(*, user, password, dsn):
        connections.append((user, password, dsn))
        return Connection(commands, query="[" in user)

    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=connect))

    result = await OracleTemporaryProxyQueryService(settings).execute("SELECT * FROM customers;", {})

    assert result.columns == ["customer_id", "customer_name"]
    assert result.items[0]["customer_name"] == "Acme Retail"
    assert connections[0][0] == "provisioner"
    assert re.fullmatch(r'portal_proxy\[PORTAL_Q_[0-9A-F]{20}\]', connections[1][0])
    assert commands[0][0].startswith('CREATE USER "PORTAL_Q_')
    assert 'GRANT SELECT ON "APP"."CUSTOMERS"' in commands[2][0]
    assert commands[-1][0].startswith('DROP USER "PORTAL_Q_')


def test_query_accepts_http_url_for_an_easy_connect_dsn(settings):
    settings.oracle_dsn = "http://oracle.example.com:1521/freepdb1"

    assert OracleTemporaryProxyQueryService(settings)._connection_dsn() == "oracle.example.com:1521/freepdb1"
