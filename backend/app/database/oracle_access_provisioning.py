"""Provision Oracle proxy client accounts from approved OpenMetadata requests."""

import asyncio
import re
import secrets
from typing import Any

from app.config import Settings
from app.models.contracts import AssociatedDatabaseAccount


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_SIMPLE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}$")


class OracleAccessProvisioner:
    """Creates a durable Oracle proxy client and grants table-level SELECT.

    The client name intentionally contains the immutable OpenMetadata UUID. It
    requires Oracle 12.2+ extended identifiers because it is a quoted name.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def grant_select(self, openmetadata_user_id: str, schema: str, table: str) -> str:
        self._validate_configuration()
        client = self.client_username(openmetadata_user_id)
        admin = await self._connect()
        try:
            await self._ensure_client(admin, client)
            await self._grant_proxy_access(admin, client)
            await self._grant_select(admin, client, schema, table)
        finally:
            await self._close(admin)
        return client

    async def revoke_select(self, openmetadata_user_id: str, schema: str, table: str) -> str:
        """Remove one portal-managed table privilege from an OM client account."""
        self._validate_configuration()
        client = self.client_username(openmetadata_user_id)
        admin = await self._connect()
        try:
            cursor = await asyncio.to_thread(admin.cursor)
            try:
                statement = f"REVOKE SELECT ON {self._simple_identifier(schema)}.{self._simple_identifier(table)} FROM {self._quoted(client)}"
                await asyncio.to_thread(cursor.execute, statement)
            finally:
                await asyncio.to_thread(cursor.close)
        finally:
            await self._close(admin)
        return client

    async def find_client_account(self, openmetadata_user_id: str) -> AssociatedDatabaseAccount:
        """Read the durable Oracle client account derived from an OM user UUID."""
        client = self.client_username(openmetadata_user_id)
        if not all((self.settings.oracle_dsn, self.settings.oracle_provisioner_user, self.settings.oracle_provisioner_password)):
            return AssociatedDatabaseAccount(account_name=client, state="not_configured")
        try:
            admin = await self._connect()
            try:
                cursor = await asyncio.to_thread(admin.cursor)
                try:
                    await asyncio.to_thread(
                        cursor.execute,
                        # ALL_USERS is available to the provisioner without
                        # DBA dictionary privileges. It does not expose
                        # ACCOUNT_STATUS (that column is in DBA_USERS), so
                        # querying it made every audit lookup appear
                        # unavailable with ORA-00904.
                        "SELECT username, created FROM all_users WHERE username = :username",
                        {"username": client},
                    )
                    row = await asyncio.to_thread(cursor.fetchone)
                finally:
                    await asyncio.to_thread(cursor.close)
            finally:
                await self._close(admin)
        except Exception:
            # The lookup is informational; do not expose connection details or
            # credentials through an access-audit screen.
            return AssociatedDatabaseAccount(account_name=client, state="unavailable")
        if not row:
            return AssociatedDatabaseAccount(account_name=client, state="not_found")
        return AssociatedDatabaseAccount(
            account_name=str(row[0]), state="found", created_at=row[1],
        )

    @staticmethod
    def client_username(openmetadata_user_id: str) -> str:
        if not _UUID.fullmatch(openmetadata_user_id):
            raise ValueError("The OpenMetadata requester id must be a UUID")
        return f"om::{openmetadata_user_id.lower()}"

    def _validate_configuration(self) -> None:
        if not all((self.settings.oracle_dsn, self.settings.oracle_provisioner_user, self.settings.oracle_provisioner_password, self.settings.oracle_proxy_user)):
            raise RuntimeError("Oracle access provisioning is not configured")
        if str(self.settings.oracle_dsn).lower().startswith(("http://", "https://")):
            raise RuntimeError("ORACLE_DSN must be an Oracle Easy Connect string or connect descriptor, not an HTTP URL")
        self._simple_identifier(self.settings.oracle_proxy_user or "")

    async def _connect(self) -> Any:
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to enable Oracle provisioning") from exc
        return await asyncio.to_thread(
            oracledb.connect,
            user=self.settings.oracle_provisioner_user,
            password=self.settings.oracle_provisioner_password,
            dsn=self.settings.oracle_dsn,
        )

    async def _ensure_client(self, admin: Any, client: str) -> None:
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            try:
                password = f"Aa1!{secrets.token_hex(24)}"
                await asyncio.to_thread(cursor.execute, f"CREATE USER {self._quoted(client)} IDENTIFIED BY \"{password}\"")
            except Exception as exc:
                # ORA-01920 means a repeated request found the existing account.
                if "ORA-01920" not in str(exc):
                    raise
            await asyncio.to_thread(cursor.execute, f"GRANT CREATE SESSION TO {self._quoted(client)}")
        finally:
            await asyncio.to_thread(cursor.close)

    async def _grant_proxy_access(self, admin: Any, client: str) -> None:
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            await asyncio.to_thread(cursor.execute, f"ALTER USER {self._quoted(client)} GRANT CONNECT THROUGH {self._simple_identifier(self.settings.oracle_proxy_user or '')}")
        finally:
            await asyncio.to_thread(cursor.close)

    async def _grant_select(self, admin: Any, client: str, schema: str, table: str) -> None:
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            await asyncio.to_thread(cursor.execute, f"GRANT SELECT ON {self._simple_identifier(schema)}.{self._simple_identifier(table)} TO {self._quoted(client)}")
        finally:
            await asyncio.to_thread(cursor.close)

    @staticmethod
    def _quoted(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    @staticmethod
    def _simple_identifier(value: str) -> str:
        if not _SIMPLE_IDENTIFIER.fullmatch(value):
            raise ValueError("Oracle schema, table, and proxy user names must be simple identifiers")
        return f'"{value.upper()}"'

    @staticmethod
    async def _close(connection: Any) -> None:
        if connection:
            await asyncio.to_thread(connection.close)
