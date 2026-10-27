"""Validate then idempotently create/update the Data Access task workflow."""

import asyncio
import argparse
import json
from pathlib import Path

import httpx

from app.config import get_settings


WORKFLOW_PATH = Path(__file__).parents[1] / "workflows" / "data_access_request_workflow.json"


async def main(validate_only: bool) -> None:
    settings = get_settings()
    definition = json.loads(WORKFLOW_PATH.read_text())
    base_url = f"{str(settings.openmetadata_base_url).rstrip('/')}/api/{settings.openmetadata_api_version}"
    headers = {"Authorization": f"Bearer {settings.om_admin_bot_token}"}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=settings.openmetadata_timeout_seconds) as client:
        validation = await client.post("/governance/workflowDefinitions/validate", json=definition)
        validation.raise_for_status()
        if validate_only:
            print(f"Validated OpenMetadata workflow: {definition['name']}")
            return
        response = await client.put("/governance/workflowDefinitions", json=definition)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            # Some OpenMetadata deployments persist a workflow successfully but
            # fail while serializing the initial response. Confirm the stored
            # definition before treating a 5xx as a failed bootstrap.
            if response.status_code < 500:
                raise
            existing = await client.get(f"/governance/workflowDefinitions/name/{definition['name']}")
            existing.raise_for_status()
            comparable_keys = ("name", "displayName", "description", "config", "trigger", "nodes", "edges")
            if not all(existing.json().get(key) == definition.get(key) for key in comparable_keys):
                raise
    print(f"Applied OpenMetadata workflow: {definition['name']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true", help="Validate the workflow without writing it to OpenMetadata")
    args = parser.parse_args()
    asyncio.run(main(args.validate_only))
