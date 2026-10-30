"""Desired-state synchronisation of OpenMetadata view grants to Oracle."""

import asyncio
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.database.oracle_access_provisioning import OracleAccessProvisioner
from app.openmetadata.policy_sync import OpenMetadataViewGrant


_VIEW = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}\.[A-Za-z][A-Za-z0-9_$#]{0,127}$")
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")
_LEDGER = "OM_POLICY_SYNC_GRANTS"


@dataclass(frozen=True, order=True)
class ManagedGrant:
    username: str
    owner: str
    view: str


@dataclass(frozen=True)
class PolicySyncResult:
    created_clients: int = 0
    granted: int = 0
    revoked: int = 0
    unchanged: int = 0


class OraclePolicySynchronizer:
    """Apply an OM desired-state snapshot without touching manual grants."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._view_map = self._parse_view_map(settings.oracle_policy_sync_view_map)

    async def sync(self, source_grants: list[OpenMetadataViewGrant]) -> PolicySyncResult:
        self._validate_configuration()
        desired = self._desired(source_grants)
        connection = await self._connect()
        try:
            await self._execute(connection, f"""
                CREATE TABLE {_LEDGER} (
                    client_username VARCHAR2(128) NOT NULL,
                    view_owner VARCHAR2(128) NOT NULL,
                    view_name VARCHAR2(128) NOT NULL,
                    CONSTRAINT om_policy_sync_grants_pk PRIMARY KEY (client_username, view_owner, view_name)
                )
            """)
        except Exception as exc:
            # ORA-00955: the durable ledger already exists.
            if "ORA-00955" not in str(exc):
                await self._close(connection)
                raise
        try:
            existing = await self._load_ledger(connection)
            for entry in desired:
                await self._assert_view(connection, entry.owner, entry.view)
            created = 0
            for username in sorted({item.username for item in desired - existing}):
                if await self._ensure_proxy_client(connection, username):
                    created += 1
            for entry in sorted(desired - existing):
                await self._grant(connection, entry)
            for entry in sorted(existing - desired):
                await self._revoke(connection, entry)
            await asyncio.to_thread(connection.commit)
            return PolicySyncResult(created, len(desired - existing), len(existing - desired), len(desired & existing))
        except Exception:
            await asyncio.to_thread(connection.rollback)
            raise
        finally:
            await self._close(connection)

    def _desired(self, source_grants: list[OpenMetadataViewGrant]) -> set[ManagedGrant]:
        desired: set[ManagedGrant] = set()
        for grant in source_grants:
            oracle_view = self._view_map.get(grant.table_fqn or "") or self._view_map.get(grant.table_id or "")
            if not oracle_view:
                continue
            owner, view = oracle_view.split(".", 1)
            desired.add(ManagedGrant(OracleAccessProvisioner.client_username(grant.user_id), owner, view))
        return desired

    @staticmethod
    def _parse_view_map(raw: str) -> dict[str, str]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("ORACLE_POLICY_SYNC_VIEW_MAP must be a JSON object") from exc
        if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(target, str) for key, target in value.items()):
            raise ValueError("ORACLE_POLICY_SYNC_VIEW_MAP must map OM FQNs or IDs to Oracle SCHEMA.VIEW names")
        result: dict[str, str] = {}
        for key, target in value.items():
            if not _VIEW.fullmatch(target):
                raise ValueError(f"Unsafe Oracle view mapping for {key!r}; use unquoted SCHEMA.VIEW")
            result[key] = target.upper()
        return result

    def _validate_configuration(self) -> None:
        if not self.settings.oracle_policy_sync_enabled:
            raise RuntimeError("Oracle policy sync is disabled")
        if not all((self.settings.oracle_dsn, self.settings.oracle_provisioner_user, self.settings.oracle_provisioner_password, self.settings.oracle_proxy_user)):
            raise RuntimeError("Policy sync requires ORACLE_DSN, ORACLE_PROVISIONER_USER, ORACLE_PROVISIONER_PASSWORD, and ORACLE_PROXY_USER")
        if not _IDENTIFIER.fullmatch(self.settings.oracle_proxy_user):
            raise RuntimeError("ORACLE_PROXY_USER must be an unquoted Oracle identifier")

    async def _ensure_proxy_client(self, connection: Any, username: str) -> bool:
        if await self._fetchone(connection, "SELECT 1 FROM all_users WHERE username = :username", {"username": username}):
            return False
        quoted = self._quote(username)
        password = secrets.token_urlsafe(36).replace("-", "A").replace("_", "B")
        await self._execute(connection, f"CREATE USER {quoted} IDENTIFIED BY {self._quote(password)}")
        await self._execute(connection, f"GRANT CREATE SESSION TO {quoted}")
        await self._execute(connection, f"ALTER USER {quoted} GRANT CONNECT THROUGH {self.settings.oracle_proxy_user.upper()}")
        return True

    async def _assert_view(self, connection: Any, owner: str, view: str) -> None:
        if not await self._fetchone(connection, "SELECT 1 FROM all_views WHERE owner = :owner AND view_name = :view_name", {"owner": owner, "view_name": view}):
            raise RuntimeError(f"Mapped Oracle object {owner}.{view} is not a view visible to the provisioner")

    async def _load_ledger(self, connection: Any) -> set[ManagedGrant]:
        rows = await self._fetchall(connection, f"SELECT client_username, view_owner, view_name FROM {_LEDGER}")
        return {ManagedGrant(str(row[0]), str(row[1]), str(row[2])) for row in rows}

    async def _grant(self, connection: Any, entry: ManagedGrant) -> None:
        await self._execute(connection, f"GRANT SELECT ON {entry.owner}.{entry.view} TO {self._quote(entry.username)}")
        await self._execute(connection, f"INSERT INTO {_LEDGER} (client_username, view_owner, view_name) VALUES (:username, :owner, :view)", {"username": entry.username, "owner": entry.owner, "view": entry.view})

    async def _revoke(self, connection: Any, entry: ManagedGrant) -> None:
        await self._execute(connection, f"REVOKE SELECT ON {entry.owner}.{entry.view} FROM {self._quote(entry.username)}")
        await self._execute(connection, f"DELETE FROM {_LEDGER} WHERE client_username = :username AND view_owner = :owner AND view_name = :view", {"username": entry.username, "owner": entry.owner, "view": entry.view})

    async def _execute(self, connection: Any, statement: str, params: dict | None = None) -> None:
        cursor = await asyncio.to_thread(connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, statement, params or {})
        finally:
            await asyncio.to_thread(cursor.close)

    async def _fetchone(self, connection: Any, statement: str, params: dict) -> Any:
        cursor = await asyncio.to_thread(connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, statement, params)
            return await asyncio.to_thread(cursor.fetchone)
        finally:
            await asyncio.to_thread(cursor.close)

    async def _fetchall(self, connection: Any, statement: str) -> list[Any]:
        cursor = await asyncio.to_thread(connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, statement)
            return await asyncio.to_thread(cursor.fetchall)
        finally:
            await asyncio.to_thread(cursor.close)

    async def _connect(self) -> Any:
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to run policy sync") from exc
        return await asyncio.to_thread(oracledb.connect, user=self.settings.oracle_provisioner_user, password=self.settings.oracle_provisioner_password, dsn=self.settings.oracle_dsn)

    @staticmethod
    def _quote(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    @staticmethod
    async def _close(connection: Any) -> None:
        if connection:
            await asyncio.to_thread(connection.close)
