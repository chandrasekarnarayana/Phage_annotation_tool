"""Utilities package.

Contains:
- logging: Logging configuration and helpers
- zero_copy: Zero-copy array view utilities
- memory_profiling: Memory profiling decorators and helpers
"""

from phage_annotator.utils.memory_profiling import (
    MemoryTracker,
    assert_no_memory_regression,
    get_current_memory_mb,
    get_peak_memory_mb,
    memory_snapshot,
    profile_memory,
)
from phage_annotator.utils.zero_copy import (
    can_avoid_copy,
    ensure_contiguous,
    ensure_writable,
    frame_view_4d,
    is_view_of,
    memory_size_mb,
    readonly_view,
    safe_slice_2d,
    safe_view,
)

__all__ = [
    # Zero-copy utilities
    "safe_view",
    "readonly_view",
    "ensure_contiguous",
    "ensure_writable",
    "is_view_of",
    "memory_size_mb",
    "can_avoid_copy",
    "safe_slice_2d",
    "frame_view_4d",
    # Memory profiling
    "profile_memory",
    "memory_snapshot",
    "get_current_memory_mb",
    "get_peak_memory_mb",
    "MemoryTracker",
    "assert_no_memory_regression",
]
