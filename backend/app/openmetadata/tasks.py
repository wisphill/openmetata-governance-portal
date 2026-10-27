from datetime import datetime, timezone

from app.models.contracts import AccessRequestDetail, Task, TaskPage
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataTaskService:
    def __init__(self, client: OpenMetadataClient, user_id: str) -> None:
        self.client = client
        self.user_id = user_id

    async def list_tasks(self, page: int, page_size: int, status_filter: str | None, task_type: str | None) -> TaskPage:
        params = {"assignee": self.user_id, "limit": page_size, "offset": (page - 1) * page_size}
        if status_filter:
            params["status"] = status_filter
        if task_type:
            params["taskType"] = task_type
        payload = await self.client.get(self.client.settings.openmetadata_tasks_path, params)
        raw_items = payload.get("data", payload.get("tasks", []))
        return TaskPage(items=[self._normalize(item) for item in raw_items], page=page, page_size=page_size, total=payload.get("total"))

    async def list_created_tasks(self, page: int, page_size: int) -> TaskPage:
        """List tasks submitted through the portal by this authenticated user."""
        after: str | None = None
        matches: list[Task] = []
        for _ in range(self.client.settings.openmetadata_task_scan_max_pages):
            params = {
                "limit": 100,
                "fields": "about,createdBy,payload,assignees",
                "type": self.client.settings.openmetadata_access_request_task_type,
                "q": f"portal-access-{self.user_id}",
            }
            if after:
                params["after"] = after
            payload = await self.client.get(self.client.settings.openmetadata_access_request_task_path, params)
            raw_items = payload.get("data", payload.get("tasks", []))
            matches.extend(
                self._normalize(item, item.get("createdById") or (item.get("createdBy") or {}).get("id"))
                for item in raw_items
                if str(item.get("name", "")).startswith(f"portal-access-{self.user_id}-")
            )
            after = payload.get("paging", {}).get("after")
            if not after:
                break
        start = (page - 1) * page_size
        return TaskPage(items=matches[start:start + page_size], page=page, page_size=page_size, total=len(matches))

    async def cancel_created_task(self, task_id: str) -> None:
        """Close a portal-created request after confirming its requester scope."""
        task = await self.client.get(f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}")
        if not str(task.get("name", "")).startswith(f"portal-access-{self.user_id}-"):
            raise PermissionError("You can only cancel requests you created")
        if str(task.get("status", "")).lower() in {"approved", "cancelled", "closed", "rejected"}:
            raise ValueError("This request can no longer be cancelled")
        # OpenMetadata closes tasks through its dedicated lifecycle endpoint;
        # updating the task entity itself is not a supported cancellation action.
        await self.client.post(f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}/close", {})

    async def get_created_task(self, task_id: str) -> AccessRequestDetail:
        task = await self.client.get(f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}")
        if not str(task.get("name", "")).startswith(f"portal-access-{self.user_id}-"):
            raise PermissionError("You can only view requests you created")
        normalized = self._normalize(task, task.get("createdById") or (task.get("createdBy") or {}).get("id"))
        about = task.get("about") if isinstance(task.get("about"), dict) else {}
        fqn = about.get("fullyQualifiedName") if isinstance(about.get("fullyQualifiedName"), str) else None
        parts = fqn.split(".") if fqn else []
        payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
        expiration = payload.get("expirationDate")
        expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc) if isinstance(expiration, (int, float)) else None
        return AccessRequestDetail(
            **normalized.model_dump(),
            table_name=about.get("displayName") or about.get("name") or (parts[-1] if parts else None),
            table_fully_qualified_name=fqn,
            database=parts[-3] if len(parts) >= 3 else None,
            schema_name=parts[-2] if len(parts) >= 2 else None,
            access_type=payload.get("accessType"),
            access_level=payload.get("requestedAccess"),
            columns=[column for column in payload.get("columns", []) if isinstance(column, str)],
            expires_at=expires_at,
        )

    def _normalize(self, item: dict, requester_id: str | None = None) -> Task:
        def date(value):
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            return value
        entity = item.get("entity") or item.get("about")
        assignees = self._assignees(item.get("assignees"))
        return Task(id=str(item.get("id")), request_id=item.get("taskId") or item.get("name"), type=item.get("taskType") or item.get("type"), status=item.get("status"), assignee=self.user_id, assignees=assignees, entity=entity, created_at=date(item.get("createdAt")), due_at=date(item.get("dueDate")), requester=requester_id or (item.get("createdBy") or {}).get("name"), reason=(item.get("payload") or {}).get("reason"), link=item.get("entityLink"))

    @staticmethod
    def _assignees(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        assignees: list[str] = []
        for assignee in value:
            if isinstance(assignee, str):
                assignees.append(assignee)
            elif isinstance(assignee, dict):
                name = assignee.get("displayName") or assignee.get("display_name") or assignee.get("name") or assignee.get("fullyQualifiedName") or assignee.get("id")
                if isinstance(name, str):
                    assignees.append(name)
        return assignees
