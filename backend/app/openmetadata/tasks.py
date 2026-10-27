import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException

from app.cache.user_names import UserNameCache
from app.config import Settings
from app.database.oracle_access_provisioning import OracleAccessProvisioner
from app.models.contracts import AccessRequestDetail, Task, TaskPage, TaskResolutionRequest
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataTaskService:
    def __init__(self, client: OpenMetadataClient, user_id: str, user_name_cache: UserNameCache | None = None, settings: Settings | None = None) -> None:
        self.client = client
        self.user_id = user_id
        self.user_name_cache = user_name_cache
        self.settings = settings

    async def list_tasks(self, page: int, page_size: int, status_filter: str | None, task_type: str | None) -> TaskPage:
        """List v2 tasks assigned to the authenticated OpenMetadata identity.

        OpenMetadata 2.0's list endpoint accepts an assignee parameter on some
        releases but silently ignores it on others. Scan its bounded pagination
        and apply the identity filter server-side so no unrelated task is exposed.
        """
        after: str | None = None
        matches: list[dict] = []
        for _ in range(self.client.settings.openmetadata_task_scan_max_pages):
            # Only actionable tasks belong in an approver's work queue. Apply
            # this at the OpenMetadata API boundary, not just in the UI.
            params = {"limit": 100, "fields": "assignees,about,createdBy,payload", "status": "Open"}
            if after:
                params["after"] = after
            payload = await self.client.get(self.client.settings.openmetadata_tasks_path, params)
            raw_items = payload.get("data", payload.get("tasks", []))
            for item in raw_items:
                if not self._is_assigned_to_current_user(item):
                    continue
                if item.get("status") != "Open":
                    continue
                if status_filter and item.get("status") != status_filter:
                    continue
                if task_type and (item.get("taskType") or item.get("type")) != task_type:
                    continue
                matches.append(item)
            after = payload.get("paging", {}).get("after")
            if not after:
                break
        requester_names = await self._requester_names(matches)
        tasks = [self._normalize(item, requester_names.get(self._requester_id(item))) for item in matches]
        start = (page - 1) * page_size
        return TaskPage(items=tasks[start:start + page_size], page=page, page_size=page_size, total=len(tasks))

    async def list_created_tasks(self, page: int, page_size: int) -> TaskPage:
        """List tasks submitted through the portal by this authenticated user."""
        after: str | None = None
        matches: list[dict] = []
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
            matches.extend(item for item in raw_items if str(item.get("name", "")).startswith(f"portal-access-{self.user_id}-"))
            after = payload.get("paging", {}).get("after")
            if not after:
                break
        requester_names = await self._requester_names(matches)
        tasks = [self._normalize(item, requester_names.get(self._requester_id(item))) for item in matches]
        start = (page - 1) * page_size
        return TaskPage(items=tasks[start:start + page_size], page=page, page_size=page_size, total=len(tasks))

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

    async def resolve_assigned_task(self, task_id: str, resolution: TaskResolutionRequest) -> Task:
        task = await self.client.get(f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}")
        if not self._is_assigned_to_current_user(task):
            raise PermissionError("You can only resolve tasks assigned to you")
        if str(task.get("status", "")).lower() not in {"open", "inprogress", "pending"}:
            raise ValueError("This task can no longer be resolved")
        provision_oracle_access = (
            resolution.resolution_type == "Approved"
            and (task.get("taskType") or task.get("type")) == self.client.settings.openmetadata_access_request_task_type
        )
        grant_target = self._oracle_grant_target(task) if provision_oracle_access else None
        resolved = await self.client.post(
            f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}/resolve",
            {"resolutionType": resolution.resolution_type, "comment": resolution.comment},
        )
        if provision_oracle_access:
            if self.settings is None:
                raise RuntimeError("Oracle access provisioning settings are required")
            requester_id, schema, table = grant_target
            await OracleAccessProvisioner(self.settings).grant_select(requester_id, schema, table)
        requester_names = await self._requester_names([resolved])
        return self._normalize(resolved, requester_names.get(self._requester_id(resolved)))

    def _oracle_grant_target(self, task: dict) -> tuple[str, str, str]:
        """Return the trusted requester and table identified by the OM task."""
        requester_id = self._requester_id(task)
        if not requester_id:
            raise ValueError("The access request has no OpenMetadata requester")
        payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
        if payload.get("accessType") == "ColumnLevel" or payload.get("columns"):
            raise ValueError("Oracle provisioning currently supports table-level access requests only")
        about = task.get("about") if isinstance(task.get("about"), dict) else {}
        fqn = about.get("fullyQualifiedName")
        if not isinstance(fqn, str):
            raise ValueError("The access request does not identify a table")
        parts = fqn.split(".")
        if len(parts) < 2:
            raise ValueError("The requested table fully qualified name is invalid")
        return requester_id, parts[-2], parts[-1]

    async def get_created_task(self, task_id: str) -> AccessRequestDetail:
        task = await self.client.get(f"{self.client.settings.openmetadata_access_request_task_path.rstrip('/')}/{task_id}")
        if not str(task.get("name", "")).startswith(f"portal-access-{self.user_id}-"):
            raise PermissionError("You can only view requests you created")
        requester_names = await self._requester_names([task])
        normalized = self._normalize(task, requester_names.get(self._requester_id(task)))
        about = task.get("about") if isinstance(task.get("about"), dict) else {}
        fqn = about.get("fullyQualifiedName") if isinstance(about.get("fullyQualifiedName"), str) else None
        parts = fqn.split(".") if fqn else []
        payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
        resolution = task.get("resolution") if isinstance(task.get("resolution"), dict) else {}
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
            resolution_type=resolution.get("type") if isinstance(resolution.get("type"), str) else None,
            resolution_comment=resolution.get("comment") if isinstance(resolution.get("comment"), str) else None,
        )

    def _normalize(self, item: dict, requester_name: str | None = None) -> Task:
        def date(value):
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            return value
        entity = item.get("entity") or item.get("about")
        assignees = self._assignees(item.get("assignees"))
        creator = item.get("createdBy") if isinstance(item.get("createdBy"), dict) else {}
        return Task(id=str(item.get("id")), request_id=item.get("taskId") or item.get("name"), type=item.get("taskType") or item.get("type"), status=item.get("status"), assignee=self.user_id, assignees=assignees, entity=entity, created_at=date(item.get("createdAt")), due_at=date(item.get("dueDate")), requester=requester_name or creator.get("displayName") or creator.get("name"), reason=(item.get("payload") or {}).get("reason"), link=item.get("entityLink"))

    async def _requester_names(self, items: list[dict]) -> dict[str, str]:
        user_ids = {user_id for item in items if (user_id := self._requester_id(item))}
        if not user_ids or self.user_name_cache is None:
            return {}
        names = await self.user_name_cache.get_many(user_ids)
        missing = user_ids - names.keys()
        if not missing:
            return names

        missing_ids = tuple(missing)
        results = await asyncio.gather(*(self._get_user_name(user_id) for user_id in missing_ids), return_exceptions=True)
        fetched = {user_id: name for user_id, name in zip(missing_ids, results) if isinstance(name, str) and name}
        await self.user_name_cache.set_many(fetched)
        return {**names, **fetched}

    async def _get_user_name(self, user_id: str) -> str | None:
        try:
            user = await self.client.get(f"/users/{user_id}", {"fields": "profile"})
        except HTTPException:
            return None
        return user.get("displayName") or user.get("name")

    @staticmethod
    def _requester_id(item: dict) -> str | None:
        creator = item.get("createdBy") if isinstance(item.get("createdBy"), dict) else {}
        value = item.get("createdById") or creator.get("id")
        return value if isinstance(value, str) else None

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

    def _is_assigned_to_current_user(self, item: dict) -> bool:
        assignees = item.get("assignees")
        if not isinstance(assignees, list):
            return False
        return any(
            (isinstance(assignee, str) and assignee == self.user_id)
            or (isinstance(assignee, dict) and assignee.get("id") == self.user_id)
            for assignee in assignees
        )
