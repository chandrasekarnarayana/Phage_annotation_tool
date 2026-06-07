"""Zero-copy array view utilities for memory-efficient operations.

Provides safe, memory-efficient view operations to minimize array copies
throughout the rendering and analysis pipeline.

Key Principles:
    1. Return views instead of copies whenever safe
    2. Mark views as read-only when mutation is unintended
    3. Only copy when absolutely necessary (e.g., non-contiguous to contiguous)
    4. Document ownership and mutation semantics clearly

Usage Examples:
    >>> arr = np.arange(1000000).reshape(1000, 1000)
    >>> view = safe_view(arr)  # Zero-copy read-only view
    >>> view[0, 0] = 999  # Raises error
    
    >>> result = ensure_contiguous(arr[::2, ::2])  # Copies only if needed
    >>> assert result.flags['C_CONTIGUOUS']
"""

from __future__ import annotations

from typing import Optional, Tuple, Union

import numpy as np

__all__ = [
    "safe_view",
    "readonly_view",
    "ensure_contiguous",
    "ensure_writable",
    "is_view_of",
    "memory_size_mb",
    "can_avoid_copy",
]


from phage_annotator.utils.zero_copy_views import safe_view, readonly_view, ensure_contiguous, is_view_of, memory_size_mb, _check_view_safety_example
from phage_annotator.utils.zero_copy_slicing import ensure_writable, can_avoid_copy, safe_slice_2d, frame_view_4d
