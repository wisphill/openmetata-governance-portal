from typing import Any

from fastapi import HTTPException, status

from app.models.contracts import CatalogColumn, CatalogOwner, CatalogPage, CatalogTable
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataCatalogService:
    """Maps the small, safe catalogue read model used by the portal."""

    # The deployed OpenMetadata instance exposes table owners as `owners`.
    # The normalizer also accepts the singular form for compatible deployments.
    _FIELDS = "owners,columns,tags,service,database,databaseSchema"

    def __init__(self, client: OpenMetadataClient) -> None:
        self.client = client

    async def list_tables(self, limit: int, after: str | None) -> CatalogPage:
        params: dict[str, Any] = {"limit": limit, "fields": self._FIELDS, "include": "non-deleted"}
        if after:
            params["after"] = after
        payload = await self.client.get("/tables", params)
        return CatalogPage(
            items=[self._normalize_table(table) for table in payload.get("data", [])],
            after=payload.get("paging", {}).get("after"),
        )

    async def get_table(self, table_id: str) -> CatalogTable:
        payload = await self.client.get(f"/tables/{table_id}", {"fields": self._FIELDS})
        return self._normalize_table(payload)

    @staticmethod
    def _normalize_table(table: dict[str, Any]) -> CatalogTable:
        def entity_name(value: Any) -> str | None:
            return value.get("fullyQualifiedName") or value.get("name") if isinstance(value, dict) else None

        raw_owners = table.get("owners") or ([table["owner"]] if table.get("owner") else [])
        owners = [
            CatalogOwner(id=str(owner["id"]), type=owner["type"], name=owner.get("name"), display_name=owner.get("displayName"), fully_qualified_name=owner.get("fullyQualifiedName"))
            for owner in raw_owners
            if isinstance(owner, dict) and owner.get("id") and owner.get("type") in {"user", "team"}
        ]
        columns = [
            CatalogColumn(
                id=str(column.get("id") or column["name"]), name=column["name"],
                data_type=column.get("dataTypeDisplay") or column.get("dataType"), description=column.get("description"),
                tags=[tag.get("tagFQN") or tag.get("name") for tag in column.get("tags", []) if isinstance(tag, dict) and (tag.get("tagFQN") or tag.get("name"))],
            ) for column in table.get("columns", []) if isinstance(column, dict) and column.get("name")
        ]
        return CatalogTable(
            id=str(table["id"]), name=table.get("name", str(table["id"])), fully_qualified_name=table.get("fullyQualifiedName"),
            description=table.get("description"), service=entity_name(table.get("service")), database=entity_name(table.get("database")),
            schema_name=entity_name(table.get("databaseSchema")), owners=owners, columns=columns,
            tags=[tag.get("tagFQN") or tag.get("name") for tag in table.get("tags", []) if isinstance(tag, dict) and (tag.get("tagFQN") or tag.get("name"))],
        )

    @staticmethod
    def require_owners(table: CatalogTable) -> list[CatalogOwner]:
        if not table.owners:
            raise HTTPException(status.HTTP_409_CONFLICT, "This table has no OpenMetadata data owner to receive an access request")
        return table.owners
