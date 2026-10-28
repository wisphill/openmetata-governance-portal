import json

import httpx
import pytest
from fastapi import HTTPException

from app.models.contracts import AccessRequestCreate, Identity
from app.openmetadata.access_requests import OpenMetadataAccessRequestService
from app.openmetadata.client import OpenMetadataClient


@pytest.mark.asyncio
async def test_access_request_uses_bot_token_and_table_owner(settings):
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-admin-bot-token"
        if request.method == "GET":
            return httpx.Response(200, json={
                "id": "table-1", "name": "customers", "fullyQualifiedName": "warehouse.public.customers",
                    "owners": [{"id": "owner-team", "type": "team", "name": "CustomerOwners", "fullyQualifiedName": "CustomerOwners"}],
                "columns": [{"name": "email", "dataType": "VARCHAR"}],
            })
        assert request.url.path == "/api/v1/tasks"
        body = json.loads(request.content)
        assert body["category"] == "DataAccess"
        assert body["about"] == "<#E::table::warehouse.public.customers>"
        assert body["assignees"] == ["CustomerOwners"]
        assert body["reviewers"] == ["CustomerOwners"]
        assert body["payload"]["accessType"] == "ColumnLevel"
        assert body["payload"]["columns"] == ["email"]
        assert body["payload"]["requestedAccess"] == "Read"
        return httpx.Response(201, json={"id": "task-1", "taskId": "TASK-00001", "status": "Open"})

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        result = await OpenMetadataAccessRequestService(client, settings).create(
            Identity(id="requester-1", username="alice"),
            AccessRequestCreate(table_id="table-1", column_ids=["email"], reason="Monthly customer metrics"),
        )
    finally:
        await client.close()

    assert result.id == "task-1"
    assert result.request_id == "TASK-00001"
    assert result.assignee_count == 1
    assert [call.method for call in calls] == ["GET", "POST"]


@pytest.mark.asyncio
async def test_access_request_rejects_columns_not_on_the_selected_table(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "table-1", "name": "customers",
            "owners": [{"id": "owner-team", "type": "team", "fullyQualifiedName": "CustomerOwners"}], "columns": [{"name": "email"}],
        })

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException) as exc:
            await OpenMetadataAccessRequestService(client, settings).create(
                Identity(id="requester-1", username="alice"),
                AccessRequestCreate(table_id="table-1", column_ids=["not-a-column"], reason="Monthly customer metrics"),
            )
    finally:
        await client.close()

    assert exc.value.status_code == 422
