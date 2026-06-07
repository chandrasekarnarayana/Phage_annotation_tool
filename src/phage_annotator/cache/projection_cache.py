"""Projection cache for in-memory tile caching.

Re-exports cache types and implementation.
"""
from __future__ import annotations

from phage_annotator.cache.projection_cache_types import CacheItem, CacheTelemetry
from phage_annotator.cache.projection_cache_core import ProjectionCache

__all__ = ["CacheItem", "CacheTelemetry", "ProjectionCache"]
