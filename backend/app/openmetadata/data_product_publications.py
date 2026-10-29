"""OpenMetadata TagUpdate tasks used to publish Views as Data Products."""

from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.models.contracts import DataProductPublicationCreate, DataProductPublicationCreated, Identity, Task, TaskPage
from app.openmetadata.catalog import OpenMetadataCatalogService
from app.openmetadata.client import OpenMetadataClient
from app.openmetadata.tasks import OpenMetadataTaskService


class OpenMetadataDataProductPublicationService:
    _VISIBLE_STATUSES = ("Open", "Pending", "Approved", "Granted", "Revoked")

    def __init__(self, client: OpenMetadataClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    async def create(self, requester: Identity, request: DataProductPublicationCreate) -> DataProductPublicationCreated:
        table = await OpenMetadataCatalogService(self.client).get_publishable_view(request.table_id)
        owners = OpenMetadataCatalogService.require_owners(table)
        reviewers = [owner.fully_qualified_name or owner.name for owner in owners]
        if not all(reviewers):
            raise HTTPException(status.HTTP_409_CONFLICT, "A data owner is missing an OpenMetadata fully qualified name")
        created = await self.client.post(self.settings.openmetadata_tasks_path, {
            "name": f"portal-data-product-{requester.id}-{uuid4()}",
            # DataAccess is the portable category accepted by the deployed OM
            # task schema; the distinct task `type` selects this workflow.
            "category": "MetadataUpdate",
            "type": self.settings.openmetadata_data_product_publication_task_type,
            "about": f"<#E::table::{table.fully_qualified_name or table.name}>",
            "assignees": reviewers,
            "reviewers": reviewers,
            # TagUpdateTaskWorkflow reads these fields to render “Tags To Add”
            # and to apply the change when the reviewer approves it.
            "payload": {
                "reason": request.reason,
                "operation": "Add",
                "tagsToAdd": [{
                    "name": "Published",
                    "displayName": "Published",
                    "source": "Classification",
                    "tagFQN": self.settings.openmetadata_data_product_published_tag,
                }],
                "currentTags": [],
                "tagsToRemove": [],
            },
        })
        return DataProductPublicationCreated(id=str(created["id"]), request_id=str(created.get("taskId") or created["id"]), status=created.get("status"), assignee_count=len(owners))

    async def list_products(self, page: int, page_size: int) -> TaskPage:
        items: list[dict[str, Any]] = []
        for task_status in self._VISIBLE_STATUSES:
            payload = await self.client.get(self.settings.openmetadata_tasks_path, {
                "limit": 100, "status": task_status, "type": self.settings.openmetadata_data_product_publication_task_type,
                "q": "portal-data-product-",
                "fields": "assignees,reviewers,about,createdBy,payload",
            })
            items.extend(item for item in payload.get("data", payload.get("tasks", [])) if self._is_publication_task(item))
        normalized = [OpenMetadataTaskService(self.client, "")._normalize(item) for item in {str(item.get("id")): item for item in items}.values()]
        start = (page - 1) * page_size
        return TaskPage(items=normalized[start:start + page_size], page=page, page_size=page_size, total=len(normalized))

    async def revoke(self, task_id: str) -> Task:
        task = await self.client.get(f"{self.settings.openmetadata_tasks_path.rstrip('/')}/{task_id}", {"fields": "availableTransitions,about,payload,assignees,reviewers"})
        if not self._is_publication_task(task):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Data Product publication request was not found")
        transition = next((item for item in task.get("availableTransitions", []) if isinstance(item, dict) and item.get("id") == "revoke"), None)
        if not transition:
            raise HTTPException(status.HTTP_409_CONFLICT, "OpenMetadata does not expose a revoke transition for this Data Product")
        resolved = await self.client.post(f"{self.settings.openmetadata_tasks_path.rstrip('/')}/{task_id}/resolve", {"transitionId": "revoke", "resolutionType": "Revoked", "comment": "Revoked by a portal administrator."})
        return OpenMetadataTaskService(self.client, "")._normalize(resolved)

    def _is_publication_task(self, task: dict[str, Any]) -> bool:
        return (
            (task.get("taskType") or task.get("type")) == self.settings.openmetadata_data_product_publication_task_type
            and str(task.get("name", "")).startswith("portal-data-product-")
        )
