from app.database.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):
    """Future adapter contract placeholder; routes do not depend on MySQL details."""

    async def connect(self, application_identity: str) -> None:
        raise NotImplementedError("MySQL support has not been configured")

    async def disconnect(self) -> None:
        return None

    async def execute_query(self, sql: str, parameters: dict) -> list[dict]:
        raise NotImplementedError("MySQL support has not been configured")

    async def validate_connection(self) -> bool:
        return False

    async def get_connection_info(self) -> dict[str, str]:
        return {"engine": "mysql", "status": "not implemented"}
