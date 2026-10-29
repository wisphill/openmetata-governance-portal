"""Read-only lookup of legacy Oracle proxy client accounts."""

import asyncio
import re
from typing import Any

from app.config import Settings
from app.models.contracts import AssociatedDatabaseAccount


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
class OracleAccessProvisioner:
    """Read a legacy Oracle proxy client; it never changes Oracle privileges."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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

    async def _connect(self) -> Any:
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to look up Oracle accounts") from exc
        return await asyncio.to_thread(
            oracledb.connect,
            user=self.settings.oracle_provisioner_user,
            password=self.settings.oracle_provisioner_password,
            dsn=self.settings.oracle_dsn,
        )

    @staticmethod
    async def _close(connection: Any) -> None:
        if connection:
            await asyncio.to_thread(connection.close)
