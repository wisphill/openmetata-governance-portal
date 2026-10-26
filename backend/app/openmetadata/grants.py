from datetime import datetime, timezone

from app.models.contracts import GrantedAccess, GrantedAccessPage
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataGrantedAccessService:
    """Reads native Granted DataAccessRequest tasks for one portal user."""

    def __init__(self, client: OpenMetadataClient, user_id: str) -> None:
        self.client = client
        self.user_id = user_id

    async def list_granted(self) -> GrantedAccessPage:
        # Native UI-created requests use requestedById. Portal-created requests
        # are created by the server bot, so their allowed task-name correlation
        # is queried separately.
        direct = await self._list({"requestedById": self.user_id})
        portal = await self._list({"q": f"portal-access-{self.user_id}"})
        by_id = {str(task.get("id")): task for task in [*direct, *portal]}
        return GrantedAccessPage(items=[self._normalize(task) for task in by_id.values()], total=len(by_id))

    async def _list(self, filters: dict[str, str]) -> list[dict]:
        items: list[dict] = []
        offset = 0
        limit = 100
        while True:
            payload = await self.client.get("/tasks/dataAccessRequests", {
                "status": "Granted", "limit": limit, "offset": offset,
                "fields": "about,payload,createdBy", **filters,
            })
            page = payload.get("data", [])
            items.extend(page)
            if len(page) < limit:
                return items
            offset += limit

    @staticmethod
    def _normalize(task: dict) -> GrantedAccess:
        payload = task.get("payload") or {}
        about = task.get("about") or {}
        def date(value):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc) if isinstance(value, (int, float)) else value
        return GrantedAccess(
            id=str(task.get("id")), request_id=task.get("taskId"), table_id=about.get("id"),
            table_name=about.get("displayName") or about.get("name"), table_fully_qualified_name=about.get("fullyQualifiedName"),
            access_type=payload.get("accessType"), access_level=payload.get("requestedAccess"),
            columns=payload.get("columns") or [], granted_at=date(task.get("approvedAt") or task.get("updatedAt")),
            expires_at=date(payload.get("expirationDate")),
        )
