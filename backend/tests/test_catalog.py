import httpx
import pytest
from fastapi import HTTPException

from app.openmetadata.catalog import OpenMetadataCatalogService
from app.openmetadata.client import OpenMetadataClient


@pytest.mark.asyncio
async def test_catalog_skips_source_tables_and_technical_views(settings):
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={
                "data": [
                    {"id": "source-1", "name": "BOOKING", "tableType": "Regular", "tags": [{"tagFQN": "DataProduct.Published"}]},
                    {"id": "technical-view", "name": "BOOKING_INTERNAL_V", "tableType": "View", "dataProducts": []},
                ],
                "paging": {"after": "next-page"},
            })
        return httpx.Response(200, json={
            "data": [{
                "id": "product-view", "name": "DP_BOOKING_ANALYTICS_V", "tableType": "View",
                    "tags": [{"tagFQN": "DataProduct.Published"}],
                "columns": [],
            }],
            "paging": {},
        })

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        page = await OpenMetadataCatalogService(client).list_tables(limit=10, after=None)
    finally:
        await client.close()

    assert [table.id for table in page.items] == ["product-view"]
    assert calls == 2


@pytest.mark.asyncio
async def test_catalog_rejects_a_source_table_by_id(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "source-1", "name": "BOOKING", "tableType": "Regular", "dataProducts": [{"id": "product-1"}]})

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HTTPException) as exc:
            await OpenMetadataCatalogService(client).get_table("source-1")
    finally:
        await client.close()

    assert exc.value.status_code == 403
