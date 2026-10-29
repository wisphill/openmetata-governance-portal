from typing import Any

from fastapi import HTTPException, status

from app.models.contracts import CatalogColumn, CatalogOwner, CatalogPage, CatalogTable
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataCatalogService:
    """Maps published Data Product views to the portal catalogue.

    A physical table is a source asset, even if it happens to have an owner or
    classification.  It must never be offered as an access-request target.
    The request catalogue therefore admits only views that are explicitly
    linked to an OpenMetadata Data Product; a technical view is not enough.
    """

    # The deployed OpenMetadata instance exposes table owners as `owners`.
    # The normalizer also accepts the singular form for compatible deployments.
    _FIELDS = "owners,columns,tags,service,database,databaseSchema,dataProducts"

    def __init__(self, client: OpenMetadataClient) -> None:
        self.client = client

    async def list_tables(self, limit: int, after: str | None) -> CatalogPage:
        # Keep following OM's cursor until this page is full of eligible
        # products.  Otherwise a catalogue page containing only source tables
        # would look empty even though a product view is on the next page.
        items: list[CatalogTable] = []
        cursor = after
        next_cursor: str | None = None
        while len(items) < limit:
            params: dict[str, Any] = {"limit": limit, "fields": self._FIELDS, "include": "non-deleted"}
            if cursor:
                params["after"] = cursor
            payload = await self.client.get("/tables", params)
            items.extend(
                normalized for table in payload.get("data", [])
                if self.is_requestable_data_product_view(table)
                if (normalized := self._normalize_table(table))
            )
            next_cursor = payload.get("paging", {}).get("after")
            if not next_cursor:
                break
            cursor = next_cursor
        return CatalogPage(
            items=items[:limit],
            after=next_cursor,
        )

    async def get_table(self, table_id: str) -> CatalogTable:
        payload = await self.client.get(f"/tables/{table_id}", {"fields": self._FIELDS})
        self.require_requestable_data_product_view(payload)
        return self._normalize_table(payload)

    async def list_publishable_views(self, limit: int, after: str | None) -> CatalogPage:
        params: dict[str, Any] = {"limit": limit, "fields": self._FIELDS, "include": "non-deleted"}
        if after:
            params["after"] = after
        payload = await self.client.get("/tables", params)
        return CatalogPage(
            items=[self._normalize_table(table) for table in payload.get("data", []) if self.is_publishable_view(table)],
            after=payload.get("paging", {}).get("after"),
        )

    async def get_publishable_view(self, table_id: str) -> CatalogTable:
        payload = await self.client.get(f"/tables/{table_id}", {"fields": self._FIELDS})
        if not self.is_publishable_view(payload):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only unpublished views can be submitted as Data Products")
        return self._normalize_table(payload)

    @staticmethod
    def is_requestable_data_product_view(table: dict[str, Any]) -> bool:
        """Whether OM explicitly identifies this table as a published product view."""
        table_type = str(table.get("tableType") or table.get("table_type") or "").casefold()
        data_products = table.get("dataProducts") or table.get("dataProduct")
        return table_type == "view" and isinstance(data_products, list) and any(
            isinstance(product, dict) and (product.get("id") or product.get("fullyQualifiedName") or product.get("name"))
            for product in data_products
        )

    @staticmethod
    def is_publishable_view(table: dict[str, Any]) -> bool:
        table_type = str(table.get("tableType") or table.get("table_type") or "").casefold()
        data_products = table.get("dataProducts") or table.get("dataProduct")
        return table_type == "view" and not data_products

    @classmethod
    def require_requestable_data_product_view(cls, table: dict[str, Any]) -> None:
        if not cls.is_requestable_data_product_view(table):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only published Data Product views can be requested; source tables and technical views are excluded",
            )

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
