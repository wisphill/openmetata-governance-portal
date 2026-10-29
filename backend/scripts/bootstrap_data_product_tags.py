"""Create the OpenMetadata tags used to designate published Data Product Views."""

import argparse
import asyncio

import httpx

from app.config import get_settings


CLASSIFICATION = "DataProduct"
TAG = "Published"
TAG_FQN = f"{CLASSIFICATION}.{TAG}"


async def get_by_name(client: httpx.AsyncClient, path: str) -> dict | None:
    response = await client.get(path)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def main(validate_only: bool) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.om_admin_bot_token}"}
    base_url = f"{str(settings.openmetadata_base_url).rstrip('/')}/api/{settings.openmetadata_api_version}"
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=settings.openmetadata_timeout_seconds) as client:
        classification = await get_by_name(client, f"/classifications/name/{CLASSIFICATION}")
        tag = await get_by_name(client, f"/tags/name/{TAG_FQN}")
        if validate_only:
            state = "exists" if classification and tag else "missing"
            print(f"{TAG_FQN}: {state}")
            return
        if not classification:
            response = await client.post("/classifications", json={
                "name": CLASSIFICATION,
                "displayName": "Data Product",
                "description": "Governed tags used to designate data products published to consumers.",
                "mutuallyExclusive": False,
            })
            response.raise_for_status()
        if not tag:
            response = await client.post("/tags", json={
                "name": TAG,
                "displayName": "Published",
                "description": "A security View approved and published as a Data Product.",
                "classification": CLASSIFICATION,
            })
            response.raise_for_status()
    print(f"Ensured OpenMetadata tag: {TAG_FQN}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true", help="Report whether the classification and tag already exist")
    args = parser.parse_args()
    asyncio.run(main(args.validate_only))
