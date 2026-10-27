"""Reusable asynchronous cache contracts and in-memory implementation."""

import asyncio
import time
from collections.abc import Callable, Hashable
from typing import Generic, Protocol, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class Cache(Protocol[K, V]):
    """A batch cache contract suitable for memory, Redis, or another backend."""

    async def get_many(self, keys: set[K]) -> dict[K, V]: ...

    async def set_many(self, values: dict[K, V]) -> None: ...


class MemoryCache(Generic[K, V]):
    """Process-local TTL cache; replace with an implementation of Cache for Redis."""

    def __init__(self, ttl_seconds: int = 600, now: Callable[[], float] = time.monotonic) -> None:
        self._ttl_seconds = ttl_seconds
        self._now = now
        self._entries: dict[K, tuple[V, float]] = {}
        self._lock = asyncio.Lock()

    async def get_many(self, keys: set[K]) -> dict[K, V]:
        now = self._now()
        async with self._lock:
            for key, (_, expires_at) in list(self._entries.items()):
                if expires_at <= now:
                    del self._entries[key]
            return {key: self._entries[key][0] for key in keys if key in self._entries}

    async def set_many(self, values: dict[K, V]) -> None:
        if not values:
            return
        expires_at = self._now() + self._ttl_seconds
        async with self._lock:
            self._entries.update({key: (value, expires_at) for key, value in values.items()})
