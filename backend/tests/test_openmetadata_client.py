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
