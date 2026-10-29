import json
import logging

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main
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
async def test_post_timeout_is_logged_with_its_operation_and_path(settings, caplog):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="app.openmetadata.client"):
        try:
            with pytest.raises(HTTPException):
                await client.post("/tasks/task-1/resolve", {"transitionId": "grant"})
        finally:
            await client.close()

    assert "OpenMetadata POST timed out: path=/tasks/task-1/resolve" in caplog.text


def test_backend_logs_error_responses_with_a_request_id(settings, monkeypatch, caplog):
    monkeypatch.setattr(app.main, "get_settings", lambda: settings)
    test_app = app.main.create_app()

    with caplog.at_level(logging.WARNING, logger="app.main"):
        response = TestClient(test_app).get("/api/not-a-route", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "request-123"
    assert "request_id=request-123 method=GET path=/api/not-a-route status=404" in caplog.text


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


@pytest.mark.asyncio
async def test_delete_passes_openmetadata_hard_delete_parameter(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/v1/tasks/task-1"
        assert request.url.params["hardDelete"] == "true"
        return httpx.Response(200, request=request)

    client = OpenMetadataClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.delete("/tasks/task-1", {"hardDelete": "true"})
    finally:
        await client.close()
