#!/usr/bin/env python3
"""Synchronise approved OpenMetadata view access into Oracle.

Run this repeatedly (for example every five minutes); it is desired-state and
idempotent.  It intentionally performs no action unless explicitly enabled.
"""

import asyncio
import logging

from app.config import get_settings
from app.database.oracle_policy_sync import OraclePolicySynchronizer
from app.openmetadata.client import OpenMetadataClient
from app.openmetadata.policy_sync import OpenMetadataPolicySyncSource


async def main() -> None:
    settings = get_settings()
    client = OpenMetadataClient(settings)
    try:
        source = OpenMetadataPolicySyncSource(client, settings.oracle_policy_sync_user_page_size, settings.oracle_policy_sync_user_max_pages)
        result = await OraclePolicySynchronizer(settings).sync(await source.list_view_grants())
    finally:
        await client.close()
    logging.info("policy sync complete: clients=%d granted=%d revoked=%d unchanged=%d", result.created_clients, result.granted, result.revoked, result.unchanged)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())
