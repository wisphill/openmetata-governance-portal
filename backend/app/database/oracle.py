import asyncio
import re
from typing import Any

from app.config import Settings
from app.database.base import DatabaseAdapter


class OracleAdapter(DatabaseAdapter):
    """Oracle proxy-session adapter; driver is optional until Oracle is configured."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection: Any | None = None

    async def connect(self, application_identity: str) -> None:
        if application_identity.lower() not in self.settings.oracle_allowlist:
            raise PermissionError("This identity is not permitted for Oracle proxy access")
        if not all([self.settings.oracle_dsn, self.settings.oracle_proxy_user, self.settings.oracle_proxy_password]):
            raise RuntimeError("Oracle proxy connection is not configured")
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to enable Oracle") from exc
        # Oracle proxy syntax is CONNECT proxy_user[client_user]; client identity is never browser-controlled.
        username = f"{self.settings.oracle_proxy_user}[{application_identity}]"
        self.connection = await asyncio.to_thread(
            oracledb.connect, user=username, password=self.settings.oracle_proxy_password, dsn=self.settings.oracle_dsn
        )

    async def disconnect(self) -> None:
        if self.connection:
            await asyncio.to_thread(self.connection.close)
            self.connection = None

    async def execute_query(self, sql: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.connection:
            raise RuntimeError("Oracle connection has not been opened")
        if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
            raise PermissionError("Only read-only SELECT queries are permitted")
        cursor = await asyncio.to_thread(self.connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, sql, parameters)
            columns = [column[0].lower() for column in cursor.description]
            rows = await asyncio.to_thread(cursor.fetchall)
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            await asyncio.to_thread(cursor.close)

    async def validate_connection(self) -> bool:
        return self.connection is not None

    async def get_connection_info(self) -> dict[str, str]:
        return {"engine": "oracle", "mode": "proxy", "configured": str(bool(self.settings.oracle_dsn)).lower()}
