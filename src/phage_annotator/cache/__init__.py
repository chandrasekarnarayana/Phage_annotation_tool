"""Cache implementations and memory management (Layer 4).

This package implements the Cache Layer, providing
intelligent caching strategies, memory budgeting, and eviction policies.

**Layer 4 Responsibilities**:
- Projection caching: RGB/statistics with LRU eviction
- Disk caching: Persistent cache for large datasets
- Memory pooling: Pre-allocated arrays for efficiency
- Cache statistics: Hit rates, memory usage monitoring
- Eviction strategies: LRU, adaptive sizing, memory pressure response

**Key Concepts**:
1. **ProjectionCache**: GPU-friendly RGB/statistic caching with fast invalidation
2. **DiskCache**: Persistent storage with compression (optional)
3. **ArrayPool**: Memory pool for zero-copy frame slicing
4. **LRU Eviction**: Automatic removal of least-recently-used items
5. **Memory Budgets**: Configurable per-cache limits

**Dependencies**:
- data: For arrays and image metadata
- algorithms: For projection computation (triangle dependency)
- Not on: core (except indirectly), ui_qt, plugins

**Design Patterns**:
- Strategy pattern: Pluggable eviction policies
- Telemetry: Built-in monitoring for debugging
- Adaptive sizing: Responds to memory pressure
- Zero-copy optimization: Uses numpy views where safe

**Usage**:
    from phage_annotator.cache import ProjectionCache, DiskCache
    
    # Fast projection get/set with automatic eviction
    proj_cache = ProjectionCache(capacity=100)
    rgb_frame = proj_cache.get_or_compute(image_id, t, z, compute_fn)
    
    # Persistent caching for reusable data
    disk_cache = DiskCache(path="./cache", capacity_mb=500)
    cached_value = disk_cache.get_or_compute(key, compute_fn)

**Architecture Evolution**:
- Physical migration from core → cache
- Eviction strategy patterns added
- Full documentation complete
"""

# Import from new locations (Phase 2.5 physical migration)
from phage_annotator.cache.projection_cache import (
    CacheItem,
    CacheTelemetry,
    ProjectionCache,
)
from phage_annotator.cache.disk_cache import (
    DiskCacheStats,
    DiskCacheConfig,
    CompressedBuffer,
    DiskCache,
)
from phage_annotator.cache.array_pool import (
    PoolConfig,
    PoolStats,
    ArrayPool,
    acquire_array,
    release_array,
    ARRAY_POOL,
)

# Phase 8.2 (P8.8.2): Cache eviction strategy patterns
from phage_annotator.cache.strategies import (
    CacheStrategies,
    EvictionStrategy,
    FIFOEvictionStrategy,
    LFUEvictionStrategy,
    LRUEvictionStrategy,
)

__all__ = [
    # projection_cache.py
    "CacheItem",
    "CacheTelemetry",
    "ProjectionCache",
    # disk_cache.py
    "DiskCacheStats",
    "DiskCacheConfig",
    "CompressedBuffer",
    "DiskCache",
    # array_pool.py
    "PoolConfig",
    "PoolStats",
    "ArrayPool",
    "acquire_array",
    "release_array",
    "ARRAY_POOL",
    # strategies.py (Phase 8.2)
    "EvictionStrategy",
    "LRUEvictionStrategy",
    "LFUEvictionStrategy",
    "FIFOEvictionStrategy",
    "CacheStrategies",
]
