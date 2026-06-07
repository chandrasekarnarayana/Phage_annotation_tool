"""Memory profiling utilities for zero-copy optimizations.

Provides decorators and context managers to measure memory usage and track
the effectiveness of zero-copy optimizations.

Usage:
    >>> @profile_memory
    ... def render_frame(image):
    ...     slice_data = image[0, 0, :, :]
    ...     return process(slice_data)
    >>> 
    >>> with memory_snapshot("projection computation"):
    ...     mean_proj = compute_mean_projection(stack)
"""

from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

try:
    import psutil
except ImportError:
    psutil = None

__all__ = [
    "profile_memory",
    "memory_snapshot",
    "get_current_memory_mb",
    "get_peak_memory_mb",
]

logger = logging.getLogger(__name__)


from phage_annotator.utils.memory_profiling_funcs import get_current_memory_mb, get_peak_memory_mb, memory_snapshot, profile_memory
from phage_annotator.utils.memory_profiling_tracker import MemoryTracker, assert_no_memory_regression, _example_usage









# Advanced helpers for detailed profiling




# Testing helpers




# Example usage for documentation
