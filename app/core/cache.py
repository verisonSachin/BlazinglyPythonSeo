"""A TTL cache with APCu's observable semantics.

``www/src/Util.php`` stores the merged settings array under ``settings`` for
60 seconds and the server secret under ``server-secret`` for 3600 seconds
(60 seconds when the secret is missing). ``www/common_lib.inc`` caches location
lookups for 60-120 seconds. The migration preserves those TTLs so that a config
change becomes visible on the same schedule operators expect.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Hashable

__all__ = ["TTLCache"]

_MISSING = object()


class TTLCache:
    """Thread-safe in-process cache with per-entry TTLs.

    ``ttl=0`` means "no expiry", matching ``apcu_store($key, $value, 0)``.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._entries: dict[Hashable, tuple[Any, float | None]] = {}

    def fetch(self, key: Hashable) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and self._clock() >= expires_at:
                del self._entries[key]
                return None
            return value

    def store(self, key: Hashable, value: Any, ttl: float = 0) -> None:
        expires_at = None if ttl <= 0 else self._clock() + ttl
        with self._lock:
            self._entries[key] = (value, expires_at)

    def delete(self, key: Hashable) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def get_or_store(self, key: Hashable, factory: Callable[[], Any], ttl: float = 0) -> Any:
        """Return the cached value, computing and storing it on a miss."""

        sentinel = _MISSING
        value = self.fetch(key)
        if value is not None:
            return value
        value = factory()
        if value is not None and value is not sentinel:
            self.store(key, value, ttl)
        return value
