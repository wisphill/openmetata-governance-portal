import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
import re
import secrets
from typing import Any
from urllib.parse import urlparse

from app.config import Settings


logger = logging.getLogger(__name__)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}$")
_READ_ONLY_QUERY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


@dataclass(frozen=True)
class OracleQueryResult:
    columns: list[str]
    items: list[dict[str, Any]]


class OracleTemporaryProxyQueryService:
    """Execute one SELECT through a dedicated client user that is always removed.

    Provisioning and cleanup intentionally live together for now. They can later
    become independently managed lifecycle operations without changing the API.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def execute(self, sql: str, parameters: dict[str, Any]) -> OracleQueryResult:
        self._validate_configuration()
        statement = self._read_only_statement(sql)
        client_user = self._temporary_username()
        client_password = f"Aa1!{secrets.token_hex(12)}"
        admin = await self._connect(self.settings.oracle_provisioner_user, self.settings.oracle_provisioner_password)
        created = False
        failed = False
        try:
            await self._create_client(admin, client_user, client_password)
            created = True
            await self._grant_client_access(admin, client_user)
            proxy = await self._connect(f"{self.settings.oracle_proxy_user}[{client_user}]", self.settings.oracle_proxy_password)
            try:
                return await self._run_select(proxy, statement, parameters)
            finally:
                await self._close(proxy)
        except Exception:
            failed = True
            raise
        finally:
            try:
                if created:
                    await self._drop_client(admin, client_user)
            except Exception:
                logger.exception("Could not remove temporary Oracle query client")
                if not failed:
                    raise RuntimeError("The temporary Oracle query user could not be removed") from None
            finally:
                await self._close(admin)

    def _validate_configuration(self) -> None:
        if not self.settings.database_queries_enabled:
            raise RuntimeError("The Oracle query service is disabled")
        required = (
            self.settings.oracle_dsn,
            self.settings.oracle_provisioner_user,
            self.settings.oracle_provisioner_password,
            self.settings.oracle_proxy_user,
            self.settings.oracle_proxy_password,
        )
        if not all(required):
            raise RuntimeError("Oracle temporary-proxy query service is not configured")
        self._quoted_identifier(self.settings.oracle_query_schema)
        self._quoted_identifier(self.settings.oracle_query_table)

    @staticmethod
    def _read_only_statement(sql: str) -> str:
        statement = sql.strip().removesuffix(";").strip()
        if not statement or not _READ_ONLY_QUERY.match(statement) or ";" in statement:
            raise PermissionError("Only one read-only SELECT or WITH query is permitted")
        return statement

    @staticmethod
    def _temporary_username() -> str:
        return f"PORTAL_Q_{secrets.token_hex(10).upper()}"

    @staticmethod
    def _quoted_identifier(value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise RuntimeError("Oracle query schema and table names must be simple identifiers")
        return f'"{value.upper()}"'

    async def _connect(self, user: str | None, password: str | None) -> Any:
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("Install the backend oracle dependency to enable Oracle queries") from exc
        return await asyncio.to_thread(oracledb.connect, user=user, password=password, dsn=self._connection_dsn())

    def _connection_dsn(self) -> str:
        """Accept an accidental http(s) prefix in local configuration as Easy Connect."""
        dsn = self.settings.oracle_dsn or ""
        parsed = urlparse(dsn)
        if parsed.scheme not in {"http", "https"}:
            return dsn
        if not parsed.hostname:
            raise RuntimeError("Oracle DSN must include a database host")
        port = f":{parsed.port}" if parsed.port else ""
        service = parsed.path.lstrip("/")
        return f"{parsed.hostname}{port}/{service}" if service else f"{parsed.hostname}{port}"

    async def _create_client(self, admin: Any, client_user: str, client_password: str) -> None:
        client = self._quoted_identifier(client_user)
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            try:
                await asyncio.to_thread(cursor.execute, f'CREATE USER {client} IDENTIFIED BY "{client_password}"')
            except Exception as exc:
                if "ORA-01031" in str(exc):
                    raise RuntimeError("Oracle provisioner needs CREATE USER privilege to start a temporary-proxy query") from exc
                raise
        finally:
            await asyncio.to_thread(cursor.close)

    async def _grant_client_access(self, admin: Any, client_user: str) -> None:
        client = self._quoted_identifier(client_user)
        schema = self._quoted_identifier(self.settings.oracle_query_schema)
        table = self._quoted_identifier(self.settings.oracle_query_table)
        proxy = self._quoted_identifier(self.settings.oracle_proxy_user or "")
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            await asyncio.to_thread(cursor.execute, f"GRANT CREATE SESSION TO {client}")
            await asyncio.to_thread(cursor.execute, f"GRANT SELECT ON {schema}.{table} TO {client}")
            await asyncio.to_thread(cursor.execute, f"ALTER USER {client} GRANT CONNECT THROUGH {proxy}")
        finally:
            await asyncio.to_thread(cursor.close)

    async def _drop_client(self, admin: Any, client_user: str) -> None:
        cursor = await asyncio.to_thread(admin.cursor)
        try:
            await asyncio.to_thread(cursor.execute, f"DROP USER {self._quoted_identifier(client_user)} CASCADE")
        finally:
            await asyncio.to_thread(cursor.close)

    async def _run_select(self, connection: Any, sql: str, parameters: dict[str, Any]) -> OracleQueryResult:
        cursor = await asyncio.to_thread(connection.cursor)
        try:
            await asyncio.to_thread(cursor.execute, sql, parameters)
            columns = [column[0].lower() for column in cursor.description]
            rows = await asyncio.to_thread(cursor.fetchmany, self.settings.oracle_query_max_rows)
            return OracleQueryResult(columns=columns, items=[dict(zip(columns, (self._json_value(value) for value in row), strict=True)) for row in rows])
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
