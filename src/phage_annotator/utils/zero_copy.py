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


def ensure_writable(arr: np.ndarray) -> np.ndarray:
    """Return a writable copy if array is read-only, otherwise return original.

    Use this when you need to modify an array that might be a read-only view.

    Parameters
    ----------
    arr : np.ndarray
        Source array

    Returns
    -------
    np.ndarray
        Writable array (copy if source is read-only, original otherwise)

    Examples
    --------
    >>> readonly = np.arange(100)
    >>> readonly.flags.writeable = False
    >>> writable = ensure_writable(readonly)  # Makes copy
    >>> writable[0] = 999  # OK
    
    >>> already_writable = np.arange(100)
    >>> result = ensure_writable(already_writable)  # No copy
    >>> assert result is already_writable
    """
    if arr.flags.writeable:
        return arr
    return arr.copy()


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


def can_avoid_copy(
    arr: np.ndarray,
    *,
    require_contiguous: bool = False,
    require_dtype: Optional[np.dtype] = None,
    require_order: str = "C",
) -> bool:
    """Check if an array operation can avoid copying based on requirements.

    This is a diagnostic helper to check if views can be used instead of copies.

    Parameters
    ----------
    arr : np.ndarray
        Array to check
    require_contiguous : bool, default=False
        If True, check if array is contiguous
    require_dtype : np.dtype, optional
        If provided, check if array has this dtype
    require_order : str, default='C'
        Memory layout to check ('C' or 'F')

    Returns
    -------
    bool
        True if no copy needed to satisfy requirements

    Examples
    --------
    >>> arr = np.arange(1000, dtype=np.int32)
    >>> assert can_avoid_copy(arr, require_dtype=np.dtype('int32'))
    >>> assert not can_avoid_copy(arr, require_dtype=np.dtype('float32'))
    >>> 
    >>> strided = arr[::2]
    >>> assert not can_avoid_copy(strided, require_contiguous=True)
    """
    if require_contiguous:
        if require_order == "C" and not arr.flags["C_CONTIGUOUS"]:
            return False
        if require_order == "F" and not arr.flags["F_CONTIGUOUS"]:
            return False
    
    if require_dtype is not None:
        if arr.dtype != require_dtype:
            return False
    
    return True


# Advanced helpers for specific use cases


def safe_slice_2d(
    arr: np.ndarray,
    y_start: int,
    y_stop: int,
    x_start: int,
    x_stop: int,
    *,
    readonly: bool = True,
) -> np.ndarray:
    """Extract a 2D slice with bounds checking, returning a safe view.

    This is a convenience wrapper for common slicing operations in rendering code.

    Parameters
    ----------
    arr : np.ndarray
        Source array (must be at least 2D)
    y_start, y_stop : int
        Y slice range
    x_start, x_stop : int
        X slice range
    readonly : bool, default=True
        If True, mark result as read-only

    Returns
    -------
    np.ndarray
        2D slice view (zero-copy)

    Examples
    --------
    >>> frame = np.arange(100*100).reshape(100, 100)
    >>> roi = safe_slice_2d(frame, 10, 20, 30, 40)
    >>> assert roi.shape == (10, 10)
    >>> roi[0, 0] = 999  # Raises ValueError (read-only)
    
    Notes
    -----
    Bounds are clamped to valid ranges automatically.
    """
    assert arr.ndim >= 2
    h, w = arr.shape[-2:]
    
    y_start = max(0, min(y_start, h))
    y_stop = max(0, min(y_stop, h))
    x_start = max(0, min(x_start, w))
    x_stop = max(0, min(x_stop, w))
    
    if arr.ndim == 2:
        view = arr[y_start:y_stop, x_start:x_stop]
    else:
        # For higher-dimensional arrays, slice only last two dims
        view = arr[..., y_start:y_stop, x_start:x_stop]
    
    if readonly:
        view.flags.writeable = False
    return view


def frame_view_4d(
    arr: np.ndarray, t: int, z: int, *, readonly: bool = True
) -> np.ndarray:
    """Extract a 2D frame from a 4D (T, Z, Y, X) stack as a safe view.

    This is the canonical way to extract frames for rendering.

    Parameters
    ----------
    arr : np.ndarray
        4D image stack with shape (T, Z, Y, X)
    t : int
        Time index
    z : int
        Z-slice index
    readonly : bool, default=True
        If True, mark result as read-only

    Returns
    -------
    np.ndarray
        2D frame view of shape (Y, X)

    Examples
    --------
    >>> stack = np.random.rand(100, 5, 512, 512)  # T=100, Z=5
    >>> frame = frame_view_4d(stack, t=50, z=2)
    >>> assert frame.shape == (512, 512)
    >>> frame[0, 0] = 1.0  # Raises ValueError (read-only)
    
    Notes
    -----
    No bounds checking is performed—use this after validating indices.
    """
    assert arr.ndim == 4
    view = arr[t, z, :, :]
    if readonly:
        view.flags.writeable = False
    return view


# Memory safety documentation


def _check_view_safety_example():
    """Example demonstrating view safety patterns (for documentation).
    
    This function is not called at runtime; it serves as executable documentation
    for zero-copy patterns.
    """
    # SAFE: Read-only view returned from function
    def get_frame_safe(stack, t, z):
        return safe_view(stack[t, z, :, :], readonly=True)
    
    # UNSAFE: Returning mutable view of internal state
    def get_frame_unsafe(stack, t, z):
        return stack[t, z, :, :]  # Caller can mutate internal buffer!
    
    # SAFE: Copy when caller needs to modify result
    def get_frame_for_modification(stack, t, z):
        return stack[t, z, :, :].copy()
    
    # SAFE: Contiguous copy only when needed
    def get_frame_contiguous(stack, t, z):
        frame = stack[t, z, :, :]
        return ensure_contiguous(frame, readonly=False)
    
    # Memory size checks
    stack = np.zeros((1000, 5, 2048, 2048), dtype=np.float32)
    print(f"Full stack: {memory_size_mb(stack):.1f} MB")
    
    frame = stack[0, 0, :, :]
    print(f"Single frame view: {memory_size_mb(frame):.1f} MB")
    print(f"Is view: {is_view_of(frame, stack)}")


# Type safety note: readonly flags are not enforced by type system
# Use runtime checks or trust calling convention
