import pytest

from app.cache.base import MemoryCache
from app.cache.user_names import MemoryUserNameCache


@pytest.mark.asyncio
async def test_memory_cache_supports_any_hashable_key_and_value_type():
    cache: MemoryCache[int, dict[str, bool]] = MemoryCache()

    await cache.set_many({42: {"enabled": True}})

    assert await cache.get_many({42, 99}) == {42: {"enabled": True}}


@pytest.mark.asyncio
async def test_memory_user_name_cache_expires_entries():
    clock = [100.0]
    cache = MemoryUserNameCache(ttl_seconds=600, now=lambda: clock[0])

    await cache.set_many({"user-1": "Alice"})
    assert await cache.get_many({"user-1", "user-2"}) == {"user-1": "Alice"}

    clock[0] += 600
    assert await cache.get_many({"user-1"}) == {}
