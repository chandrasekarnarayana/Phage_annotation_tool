"""Utils zero copy slicing helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from typing import Optional, Tuple, Union

import numpy as np

__all__ = [
    "ensure_writable",
    "can_avoid_copy",
]


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
