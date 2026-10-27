import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings


logger = logging.getLogger(__name__)


class OpenMetadataClient:
    """OpenMetadata client authenticated only with the server-side admin bot."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=f"{str(settings.openmetadata_base_url).rstrip('/')}/api/{settings.openmetadata_api_version}",
            timeout=settings.openmetadata_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.om_admin_bot_token}"},
            transport=transport,
        )

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "OpenMetadata request timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request was unavailable") from exc
        if response.status_code in (400, 401, 403, 404, 409, 422, 429):
            # Do not put upstream response bodies in the browser response or
            # logs; they can contain implementation details or user data.
            logger.warning("OpenMetadata GET failed: status=%s path=%s", response.status_code, path)
            raise HTTPException(response.status_code, f"OpenMetadata rejected GET {path} (HTTP {response.status_code})")
        if response.is_error:
            logger.warning("OpenMetadata GET failed: status=%s path=%s", response.status_code, path)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request failed")
        return response.json()

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "OpenMetadata request timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request was unavailable") from exc
        if response.status_code in (400, 401, 403, 404, 409, 422, 429):
            try:
                upstream = response.json()
            except ValueError:
                upstream = {}
            detail = upstream.get("message") or upstream.get("detail") or "OpenMetadata rejected the request"
            raise HTTPException(response.status_code, str(detail))
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request failed")
        return response.json() if response.status_code != status.HTTP_204_NO_CONTENT else {}

    async def put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.put(path, json=payload)
        except httpx.TimeoutException as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "OpenMetadata request timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request was unavailable") from exc
        if response.status_code in (400, 401, 403, 404, 409, 422, 429):
            try:
                upstream = response.json()
            except ValueError:
                upstream = {}
            detail = upstream.get("message") or upstream.get("detail") or "OpenMetadata rejected the request update"
            raise HTTPException(response.status_code, str(detail))
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request update failed")
        return response.json()

    async def delete(self, path: str, params: dict | None = None) -> None:
        try:
            response = await self._client.delete(path, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "OpenMetadata request timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request was unavailable") from exc
        if response.status_code in (400, 401, 403, 404, 409, 422, 429):
            try:
                upstream = response.json()
            except ValueError:
                upstream = {}
            detail = upstream.get("message") or upstream.get("detail") or "OpenMetadata rejected the delete request"
            raise HTTPException(response.status_code, str(detail))
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata delete request failed")

    async def close(self) -> None:
        await self._client.aclose()
