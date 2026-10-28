from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.models.contracts import AccessRequestCreate, AccessRequestCreated, CatalogOwner, CatalogTable, Identity
from app.openmetadata.catalog import OpenMetadataCatalogService
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataAccessRequestService:
    """Creates a data-access task whose reviewers approve every workflow step."""

    def __init__(self, client: OpenMetadataClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    async def create(self, requester: Identity, request: AccessRequestCreate) -> AccessRequestCreated:
        table = await OpenMetadataCatalogService(self.client).get_table(request.table_id)
        owners = OpenMetadataCatalogService.require_owners(table)
        self._validate_columns(table, request.column_ids)
        created = await self.client.post(self.settings.openmetadata_access_request_task_path, self._task_payload(requester, table, owners, request))
        return AccessRequestCreated(id=str(created["id"]), request_id=str(created.get("taskId") or created["id"]), status=created.get("status"), assignee_count=len(owners))

    @staticmethod
    def _validate_columns(table: CatalogTable, column_ids: list[str]) -> None:
        unknown = set(column_ids) - {column.id for column in table.columns}
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "One or more requested columns do not belong to the selected table")

    def _task_payload(self, requester: Identity, table: CatalogTable, owners: list[CatalogOwner], request: AccessRequestCreate) -> dict[str, Any]:
        columns = [column for column in table.columns if column.id in request.column_ids]
        table_fqn = table.fully_qualified_name or table.name
        reviewers = [owner.fully_qualified_name or owner.name for owner in owners]
        if not all(reviewers):
            raise HTTPException(status.HTTP_409_CONFLICT, "A data owner is missing an OpenMetadata fully qualified name")
        # The workflow resolves approvers from task.reviewers, never dynamically
        # from table owners. At creation time the owning team is copied into that
        # explicit reviewer list so every later stage uses the same approvers.
        expiration = datetime.now(timezone.utc) + timedelta(days=self.settings.openmetadata_access_request_expiration_days)
        return {
            # Task payload is validated against OpenMetadata's task form and
            # cannot carry portal-only fields. Use an opaque requester UUID in
            # the allowed, searchable task name for portal request history.
            "name": f"portal-access-{requester.id}-{uuid4()}",
            "category": "DataAccess",
            "type": self.settings.openmetadata_access_request_task_type,
            "about": f"<#E::table::{table_fqn}>",
            "assignees": reviewers,
            "reviewers": reviewers,
            "payload": {
                "accessType": "ColumnLevel" if columns else "FullAccess",
                "columns": [column.name for column in columns],
                "requestedAccess": request.access.title(),
                "reason": request.reason,
                "expirationDate": int(expiration.timestamp() * 1000),
            },
        }
