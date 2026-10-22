from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings


class OpenMetadataClient:
    def __init__(self, settings: Settings, access_token: str) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=f"{str(settings.openmetadata_base_url).rstrip('/')}/api/{settings.openmetadata_api_version}",
            timeout=settings.openmetadata_timeout_seconds,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        response = await self._client.get(path, params=params)
        if response.status_code in (401, 403, 404, 409, 429):
            raise HTTPException(response.status_code, "OpenMetadata request was not allowed or unavailable")
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenMetadata request failed")
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
