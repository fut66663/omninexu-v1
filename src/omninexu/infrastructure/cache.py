"""Redis cache wrapper."""

import json
from typing import Any, Protocol

import redis

from omninexu.config.settings import settings


class CacheBackend(Protocol):
    """Protocol for cache implementations used by the application layer."""

    def get_json(self, key: str) -> Any | None:
        """Return the cached JSON value, or None if missing."""
        ...

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a JSON-serializable value with an optional TTL."""
        ...

    def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        ...


class Cache:
    """Simple Redis cache wrapper."""

    def __init__(self, redis_url: str = settings.redis_url):
        self.client = redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> str | None:
        """Return the raw cached value, or None if missing."""
        value = self.client.get(key)
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    def get_json(self, key: str) -> Any | None:
        """Return the cached JSON value, or None if missing."""
        value = self.client.get(key)
        if value is None:
            return None
        return json.loads(value)

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """Store a raw string value with an optional TTL in seconds."""
        self.client.set(key, value, ex=ttl)

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a JSON-serializable value with an optional TTL in seconds."""
        self.client.set(key, json.dumps(value, default=str), ex=ttl)

    def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        self.client.delete(key)


# Global cache instance
cache = Cache()
