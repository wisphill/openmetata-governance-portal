"""Typed cache specialization for OpenMetadata user display names."""

from typing import Protocol

from app.cache.base import Cache, MemoryCache


class UserNameCache(Cache[str, str], Protocol):
    """A user-name-specific view of the generic cache adapter."""


class MemoryUserNameCache(MemoryCache[str, str]):
    """Default in-memory implementation of UserNameCache."""
