import json

import httpx
import pytest
from fastapi import HTTPException

from app.openmetadata.client import OpenMetadataClient


@pytest.mark.asyncio
async def test_get_translates_upstream_timeouts(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException) as exc:
            await client.get("/tasks")
    finally:
        await client.close()

    assert exc.value.status_code == 504
    assert exc.value.detail == "OpenMetadata request timed out"


@pytest.mark.asyncio
async def test_post_translates_upstream_timeouts(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException) as exc:
            await client.post("/tasks/task-1/close", {})
    finally:
        await client.close()

    assert exc.value.status_code == 504
    assert exc.value.detail == "OpenMetadata request timed out"


@pytest.mark.asyncio
async def test_get_preserves_bad_request_status_for_invalid_openmetadata_parameters(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "Unknown field"}, request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException) as exc:
            await client.get("/tasks/dataAccessRequests", {"fields": "closedBy"})
    finally:
        await client.close()

    assert exc.value.status_code == 400
    assert exc.value.detail == "OpenMetadata rejected GET /tasks/dataAccessRequests (HTTP 400)"


@pytest.mark.asyncio
async def test_post_sends_explicit_revoked_transition_to_openmetadata_task_workflow(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"] == "application/json"
        assert json.loads(request.content) == {"transitionId": "revoke-access", "resolutionType": "Revoked", "comment": "Revoked by a portal administrator."}
        return httpx.Response(200, json={"id": "task-1", "status": "Revoked"}, request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        task = await client.post("/tasks/task-1/resolve", {"transitionId": "revoke-access", "resolutionType": "Revoked", "comment": "Revoked by a portal administrator."})
    finally:
        await client.close()

    assert task["status"] == "Revoked"
