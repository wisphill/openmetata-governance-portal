"""Read the OpenMetadata state that is authoritative for Oracle policy sync."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.openmetadata.client import OpenMetadataClient
from app.openmetadata.grants import OpenMetadataGrantedAccessService


@dataclass(frozen=True)
class OpenMetadataViewGrant:
    user_id: str
    table_id: str | None
    table_fqn: str | None


class OpenMetadataPolicySyncSource:
    """Enumerate every OM user and that user's currently approved grants.

    Revoked, rejected, cancelled, and expired tasks are intentionally absent:
    their absence from this desired-state snapshot causes the Oracle grant to
    be removed by the synchronizer.
    """

    def __init__(self, client: OpenMetadataClient, page_size: int, max_pages: int) -> None:
        self.client = client
        self.page_size = page_size
        self.max_pages = max_pages

    async def list_view_grants(self) -> list[OpenMetadataViewGrant]:
        grants: list[OpenMetadataViewGrant] = []
        for user in await self._list_users():
            user_id = str(user.get("id") or "")
            if not user_id:
                continue
            page = await OpenMetadataGrantedAccessService(self.client, user_id).list_granted()
            for grant in page.items:
                # Oracle views are read-only data products. Write requests must
                # have a separate, explicitly designed workflow.
                if (grant.access_level or "").upper() != "READ":
                    continue
                if grant.expires_at and grant.expires_at <= datetime.now(timezone.utc):
                    continue
                grants.append(OpenMetadataViewGrant(user_id, grant.table_id, grant.table_fully_qualified_name))
        return grants

    async def _list_users(self) -> list[dict]:
        users: list[dict] = []
        after: str | None = None
        for _ in range(self.max_pages):
            params = {"limit": self.page_size, "fields": "name,displayName,email"}
            if after:
                params["after"] = after
            payload = await self.client.get("/users", params)
            page = payload.get("data") or []
            users.extend(item for item in page if isinstance(item, dict))
            after = (payload.get("paging") or {}).get("after")
            if not after:
                return users
        raise RuntimeError("OpenMetadata user scan exceeded ORACLE_POLICY_SYNC_USER_MAX_PAGES")
