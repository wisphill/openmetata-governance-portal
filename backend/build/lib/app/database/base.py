from abc import ABC, abstractmethod
from typing import Any


class DatabaseAdapter(ABC):
    @abstractmethod
    async def connect(self, application_identity: str) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def execute_query(self, sql: str, parameters: dict[str, Any]) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def validate_connection(self) -> bool: ...

    @abstractmethod
    async def get_connection_info(self) -> dict[str, str]: ...
