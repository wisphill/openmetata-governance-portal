import sys
from types import SimpleNamespace

import pytest

from app.database.oracle_access_provisioning import OracleAccessProvisioner


class LookupCursor:
    def __init__(self, row):
        self.row = row
        self.parameters = None

    def execute(self, statement, parameters):
        assert statement == "SELECT username, created FROM all_users WHERE username = :username"
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
async def test_database_account_lookup_reads_the_derived_om_client(settings, monkeypatch):
    settings.oracle_dsn = "oracle.example.com:1521/freepdb1"
    settings.oracle_provisioner_user = "provisioner"
    settings.oracle_provisioner_password = "provisioner-password"
    cursor = LookupCursor(("om::d2719c8a-6c97-4b35-b662-e791647b41b3", None))
    monkeypatch.setitem(sys.modules, "oracledb", SimpleNamespace(connect=lambda **_: LookupConnection(cursor)))

    account = await OracleAccessProvisioner(settings).find_client_account("d2719c8a-6c97-4b35-b662-e791647b41b3")

    assert account.state == "found"
    assert account.account_status is None
    assert cursor.parameters == {"username": "om::d2719c8a-6c97-4b35-b662-e791647b41b3"}
