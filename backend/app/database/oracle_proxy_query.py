"""Execute read-only queries with the configured Oracle proxy account."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any

from app.config import Settings


_READ_ONLY_QUERY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


@dataclass(frozen=True)
class OracleQueryResult:
    columns: list[str]
    items: list[dict[str, Any]]


class OracleProxyQueryService:
    """Run a bounded, read-only query as the configured proxy principal.

    This service deliberately does not create database users or change grants.
    Database permissions belong to the configured Oracle proxy account.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(self, sql: str, parameters: dict[str, Any]) -> OracleQueryResult:
        self._validate_configuration()
        statement = self._read_only_statement(sql)
        connection = await self._connect()
        try:
            return await self._run_select(connection, statement, parameters)
        finally:
            await self._close(connection)

    def _validate_configuration(self) -> None:
        if not self.settings.database_queries_enabled:
            raise RuntimeError("The Oracle query service is disabled")
        if not all((self.settings.oracle_dsn, self.settings.oracle_proxy_user, self.settings.oracle_proxy_password)):
            raise RuntimeError("Oracle proxy query service is not configured")
        if str(self.settings.oracle_dsn).lower().startswith(("http://", "https://")):
            raise RuntimeError("ORACLE_DSN must be an Oracle Easy Connect string or connect descriptor, not an HTTP URL")

    @staticmethod
    def _read_only_statement(sql: str) -> str:
        statement = sql.strip().removesuffix(";").strip()
        if not statement or not _READ_ONLY_QUERY.match(statement) or ";" in statement:
            raise PermissionError("Only one read-only SELECT or WITH query is permitted")
        return statement

    async def _connect(self) -> Any:
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to enable Oracle queries") from exc
        return await asyncio.to_thread(
            oracledb.connect,
            user=self.settings.oracle_proxy_user,
            password=self.settings.oracle_proxy_password,
            dsn=self.settings.oracle_dsn,
        )

    async def _run_select(self, connection: Any, sql: str, parameters: dict[str, Any]) -> OracleQueryResult:
        cursor = await asyncio.to_thread(connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, sql, parameters)
            columns = [column[0].lower() for column in cursor.description]
            rows = await asyncio.to_thread(cursor.fetchmany, self.settings.oracle_query_max_rows)
            return OracleQueryResult(
                columns=columns,
                items=[dict(zip(columns, (self._json_value(value) for value in row), strict=True)) for row in rows],
            )
        finally:
            await asyncio.to_thread(cursor.close)

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bytes):
            return value.hex()
        return value

    @staticmethod
    async def _close(connection: Any) -> None:
        if connection:
            await asyncio.to_thread(connection.close)
