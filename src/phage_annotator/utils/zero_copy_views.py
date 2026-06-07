"""Utils zero copy views helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
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


def safe_view(arr: np.ndarray, *, readonly: bool = True) -> np.ndarray:
    """Return a view of the array, optionally marked read-only.

    This is the primary zero-copy helper for returning array data from functions
    when the caller should not modify the underlying data.

    Parameters
    ----------
    arr : np.ndarray
        Source array
    readonly : bool, default=True
        If True, mark the view as read-only (WRITEABLE=False)

    Returns
    -------
    np.ndarray
        View of the array (zero-copy)

    Examples
    --------
    >>> data = np.arange(100)
    >>> view = safe_view(data)
    >>> view[0] = 999  # Raises ValueError (read-only)
    
    Notes
    -----
    The returned view shares memory with the source array. Changes to the source
    will be reflected in the view. Use this when:
    - Returning data that should not be modified
    - Passing temporary arrays to rendering code
    - Exposing internal buffers for inspection
    """
    view = arr.view()
    if readonly:
        view.flags.writeable = False
    return view

def readonly_view(arr: np.ndarray) -> np.ndarray:
    """Return a read-only view of the array (convenience wrapper for safe_view).

    Equivalent to `safe_view(arr, readonly=True)`.

    Parameters
    ----------
    arr : np.ndarray
        Source array

    Returns
    -------
    np.ndarray
        Read-only view

    Examples
    --------
    >>> mask = np.ones((100, 100), dtype=bool)
    >>> exposed_mask = readonly_view(mask)
    >>> exposed_mask[0, 0] = False  # Raises ValueError
    """
    return safe_view(arr, readonly=True)

def ensure_contiguous(
    arr: np.ndarray, *, order: str = "C", readonly: bool = False
) -> np.ndarray:
    """Return a contiguous array, copying only if necessary.

    Many operations (e.g., rendering, file I/O) require C-contiguous arrays.
    This helper avoids unnecessary copies when the array is already contiguous.

    Parameters
    ----------
    arr : np.ndarray
        Source array
    order : str, default='C'
        Memory layout: 'C' (row-major) or 'F' (column-major)
    readonly : bool, default=False
        If True and a copy is made, mark result as read-only

    Returns
    -------
    np.ndarray
        Contiguous array (view if already contiguous, copy otherwise)

    Examples
    --------
    >>> strided = np.arange(1000)[::2]
    >>> contig = ensure_contiguous(strided)  # Makes copy
    >>> assert contig.flags['C_CONTIGUOUS']
    
    >>> already_contig = np.arange(1000)
    >>> result = ensure_contiguous(already_contig)  # No copy
    >>> assert result is already_contig
    
    Notes
    -----
    Performance:
    - If already contiguous: Returns original array (zero overhead)
    - If non-contiguous: Returns np.ascontiguousarray(arr) (single copy)
    """
    if order == "C":
        if arr.flags["C_CONTIGUOUS"]:
            return arr
        result = np.ascontiguousarray(arr)
    elif order == "F":
        if arr.flags["F_CONTIGUOUS"]:
            return arr
        result = np.asfortranarray(arr)
    else:
        raise ValueError(f"Invalid order: {order!r} (must be 'C' or 'F')")
    
    if readonly:
        result.flags.writeable = False
    return result

def is_view_of(arr: np.ndarray, base: np.ndarray) -> bool:
    """Check if arr is a view of base (shares memory).

    Parameters
    ----------
    arr : np.ndarray
        Potential view array
    base : np.ndarray
        Potential base array

    Returns
    -------
    bool
        True if arr shares memory with base

    Examples
    --------
    >>> data = np.arange(100)
    >>> view = data[10:20]
    >>> assert is_view_of(view, data)
    >>> 
    >>> copy = data.copy()
    >>> assert not is_view_of(copy, data)
    
    Notes
    -----
    This uses np.shares_memory which is conservative: it may return True for
    arrays that overlap but are not strict views. For strict base checking,
    use `arr.base is base`.
    """
    return np.shares_memory(arr, base)

def memory_size_mb(arr: np.ndarray) -> float:
    """Return the memory size of array in megabytes.

    Parameters
    ----------
    arr : np.ndarray
        Array to measure

    Returns
    -------
    float
        Memory size in MB

    Examples
    --------
    >>> arr = np.zeros((1024, 1024), dtype=np.float32)
    >>> assert memory_size_mb(arr) == 4.0  # 1024*1024*4 bytes = 4 MB
    
    Notes
    -----
    This measures the array data size, not including Python object overhead
    or metadata. For views, this measures the size of the view (which may be
    smaller than the base array).
    """
    return arr.nbytes / (1024 * 1024)

def _check_view_safety_example():
    """Example demonstrating view safety patterns (for documentation).
    
    This function is not called at runtime; it serves as executable documentation
    for zero-copy patterns.
    """
    # SAFE: Read-only view returned from function
    def get_frame_safe(stack, t, z):
        """Return frame safe for the current workflow."""
        return safe_view(stack[t, z, :, :], readonly=True)
    
    # UNSAFE: Returning mutable view of internal state
    def get_frame_unsafe(stack, t, z):
        """Return frame unsafe for the current workflow."""
        return stack[t, z, :, :]  # Caller can mutate internal buffer!
    
    # SAFE: Copy when caller needs to modify result
    def get_frame_for_modification(stack, t, z):
        """Return frame for modification for the current workflow."""
        return stack[t, z, :, :].copy()
    
    # SAFE: Contiguous copy only when needed
    def get_frame_contiguous(stack, t, z):
        """Return frame contiguous for the current workflow."""
        frame = stack[t, z, :, :]
        return ensure_contiguous(frame, readonly=False)
    
    # Memory size checks
    stack = np.zeros((1000, 5, 2048, 2048), dtype=np.float32)
    print(f"Full stack: {memory_size_mb(stack):.1f} MB")
    
    frame = stack[0, 0, :, :]
    print(f"Single frame view: {memory_size_mb(frame):.1f} MB")
    print(f"Is view: {is_view_of(frame, stack)}")
