"""Validate then idempotently create/update the Data Product publication workflow."""

import asyncio
import json
from pathlib import Path

import httpx

from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    definition = json.loads((Path(__file__).parents[1] / "workflows" / "data_product_publication_workflow.json").read_text())
    headers = {"Authorization": f"Bearer {settings.om_admin_bot_token}"}
    async with httpx.AsyncClient(base_url=f"{str(settings.openmetadata_base_url).rstrip('/')}/api/{settings.openmetadata_api_version}", headers=headers, timeout=settings.openmetadata_timeout_seconds) as client:
        validation = await client.post("/governance/workflowDefinitions/validate", json=definition)
        if validation.is_error:
            raise RuntimeError(f"OpenMetadata rejected workflow validation ({validation.status_code}): {validation.text}")
        response = await client.put("/governance/workflowDefinitions", json=definition)
        response.raise_for_status()
    print(f"Applied OpenMetadata workflow: {definition['name']}")


if __name__ == "__main__":
    asyncio.run(main())
