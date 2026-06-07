"""Disk-based LRU cache for projection tiles.

Re-exports disk cache types and implementation.
"""
from __future__ import annotations

from phage_annotator.cache.disk_cache_types import DiskCacheStats, DiskCacheConfig, CompressedBuffer
from phage_annotator.cache.disk_cache_core import DiskCache

__all__ = ["DiskCacheStats", "DiskCacheConfig", "CompressedBuffer", "DiskCache"]
