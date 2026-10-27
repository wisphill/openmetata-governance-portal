import sys
from types import SimpleNamespace

import pytest

from app.database.oracle_access_provisioning import OracleAccessProvisioner


class Cursor:
    def __init__(self, commands):
        self.commands = commands

    def execute(self, statement):
        self.commands.append(statement)

    def close(self):
        return None


class Connection:
    def __init__(self, commands):
        self.commands = commands

    def cursor(self):
        return Cursor(self.commands)

    def close(self):
        return None


class LookupCursor:
    def __init__(self, row):
        self.row = row
        self.parameters = None

    def execute(self, statement, parameters):
        assert statement == "SELECT username, account_status, created FROM all_users WHERE username = :username"
        self.parameters = parameters

    def fetchone(self):
        return self.row

    def close(self):
        return None


class LookupConnection:
    def __init__(self, cursor):
        self.lookup_cursor = cursor

    def cursor(self):
        return self.lookup_cursor

    def close(self):
        return None


@pytest.mark.asyncio
async def test_approved_table_access_creates_om_proxy_client_and_grants_select(settings, monkeypatch):
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    settings.oracle_proxy_user = "portal_proxy"
    commands = []

    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=lambda **_: Connection(commands)))

    client = await OracleAccessProvisioner(settings).grant_select(
        "d2719c8a-6c97-4b35-b662-e791647b41b3", "app", "orders"
    )

    assert client == "om::d2719c8a-6c97-4b35-b662-e791647b41b3"
    assert commands[0].startswith('CREATE USER "om::d2719c8a-6c97-4b35-b662-e791647b41b3"')
    assert commands[1] == 'GRANT CREATE SESSION TO "om::d2719c8a-6c97-4b35-b662-e791647b41b3"'
    assert commands[2] == 'ALTER USER "om::d2719c8a-6c97-4b35-b662-e791647b41b3" GRANT CONNECT THROUGH "PORTAL_PROXY"'
    assert commands[3] == 'GRANT SELECT ON "APP"."ORDERS" TO "om::d2719c8a-6c97-4b35-b662-e791647b41b3"'


@pytest.mark.asyncio
async def test_database_account_lookup_reads_the_derived_om_client(settings, monkeypatch):
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    cursor = LookupCursor(("om::d2719c8a-6c97-4b35-b662-e791647b41b3", "OPEN", None))
    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=lambda **_: LookupConnection(cursor)))

    account = await OracleAccessProvisioner(settings).find_client_account("d2719c8a-6c97-4b35-b662-e791647b41b3")

    assert account.state == "found"
    assert account.account_status == "OPEN"
    assert cursor.parameters == {"username": "om::d2719c8a-6c97-4b35-b662-e791647b41b3"}


@pytest.mark.asyncio
async def test_admin_revoke_removes_only_the_selected_portal_table_privilege(settings, monkeypatch):
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    settings.oracle_proxy_user = "portal_proxy"
    commands = []
    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=lambda **_: Connection(commands)))

    account = await OracleAccessProvisioner(settings).revoke_select(
        "d2719c8a-6c97-4b35-b662-e791647b41b3", "app", "orders"
    )

    assert account == "om::d2719c8a-6c97-4b35-b662-e791647b41b3"
    assert commands == ['REVOKE SELECT ON "APP"."ORDERS" FROM "om::d2719c8a-6c97-4b35-b662-e791647b41b3"']


@pytest.mark.asyncio
async def test_revoke_rejects_an_http_dsn_before_connecting(settings):
    settings.oracle_dsn = "http://localhost:1521"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    settings.oracle_proxy_user = "portal_proxy"

    with pytest.raises(RuntimeError, match="not an HTTP URL"):
        await OracleAccessProvisioner(settings).revoke_select(
            "d2719c8a-6c97-4b35-b662-e791647b41b3", "app", "orders"
        )
