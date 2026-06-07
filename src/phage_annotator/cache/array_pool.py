"""Lightweight numpy array pooling for tile-sized buffers."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class PoolConfig:
    """Configuration for array pool behavior."""

    max_entries_per_key: int = 4
    max_entry_bytes: int = 64 * 1024 * 1024


@dataclass
class PoolStats:
    """Snapshot of array pool telemetry counters."""

    hits: int
    misses: int
    releases: int
    drops: int
    entries: int


class ArrayPool:
    """Reusable buffer pool keyed by (shape, dtype)."""

    def __init__(self, config: PoolConfig | None = None) -> None:
        """Initialize the object and prepare its runtime state."""
        self._config = config or PoolConfig()
        self._pool: Dict[Tuple[Tuple[int, ...], np.dtype], List[np.ndarray]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._releases = 0
        self._drops = 0

    def acquire(self, shape: Tuple[int, ...], dtype: np.dtype, *, fill: float | None = 0.0) -> np.ndarray:
        """Return a pooled array or allocate a new one if none available."""
        key = (tuple(shape), np.dtype(dtype))
        with self._lock:
            bucket = self._pool.get(key)
            if bucket:
                arr = bucket.pop()
                self._hits += 1
            else:
                arr = np.empty(shape, dtype=dtype)
                self._misses += 1
        if fill is not None:
            arr.fill(fill)
        return arr

    def release(self, arr: np.ndarray) -> None:
        """Return an array to the pool if it meets size limits."""
        if arr is None:
            return
        if arr.nbytes > self._config.max_entry_bytes:
            with self._lock:
                self._drops += 1
            return
        key = (arr.shape, arr.dtype)
        with self._lock:
            bucket = self._pool.setdefault(key, [])
            if len(bucket) >= self._config.max_entries_per_key:
                self._drops += 1
                return
            bucket.append(arr)
            self._releases += 1

    def clear(self) -> None:
        """Drop all pooled buffers."""
        with self._lock:
            self._pool.clear()

    def stats(self) -> PoolStats:
        """Return a snapshot of pool telemetry."""
        with self._lock:
            entries = sum(len(bucket) for bucket in self._pool.values())
            return PoolStats(
                hits=self._hits,
                misses=self._misses,
                releases=self._releases,
                drops=self._drops,
                entries=entries,
            )


ARRAY_POOL = ArrayPool()


def acquire_array(shape: Tuple[int, ...], dtype: np.dtype, *, fill: float | None = 0.0) -> np.ndarray:
    """Convenience wrapper for ARRAY_POOL.acquire."""
    return ARRAY_POOL.acquire(shape, dtype, fill=fill)


def release_array(arr: np.ndarray) -> None:
    """Convenience wrapper for ARRAY_POOL.release."""
    ARRAY_POOL.release(arr)
