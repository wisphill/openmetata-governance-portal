from datetime import datetime, timezone

from app.models.contracts import Task, TaskPage
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

    def _normalize(self, item: dict) -> Task:
        def date(value):
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            return value
        entity = item.get("entity") or item.get("about")
        return Task(id=str(item.get("id")), type=item.get("taskType") or item.get("type"), status=item.get("status"), assignee=self.user_id, entity=entity, created_at=date(item.get("createdAt")), due_at=date(item.get("dueDate")), requester=(item.get("createdBy") or {}).get("name"), link=item.get("entityLink"))
