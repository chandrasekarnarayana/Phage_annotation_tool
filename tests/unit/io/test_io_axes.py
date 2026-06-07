"""Unit tests for supported image-axis normalization shapes."""

import numpy as np
import pytest

from phage_annotator.io import standardize_axes


def test_standardize_axes_basic_shapes() -> None:
    """Verify standardize axes basic shapes for the current workflow."""
    arr2d = np.zeros((4, 5))
    std, has_time, has_z = standardize_axes(arr2d)
    assert std.shape == (1, 1, 4, 5)
    assert has_time is False and has_z is False

    arr3d_z = np.zeros((6, 4, 5))  # treat as Z stack
    std, has_time, has_z = standardize_axes(arr3d_z)
    assert std.shape == (1, 6, 4, 5)
    assert has_time is False and has_z is True

    arr3d_t = np.zeros((3, 4, 5))  # treat as time stack (heuristic < 20)
    std, has_time, has_z = standardize_axes(arr3d_t)
    assert std.shape == (3, 1, 4, 5)
    assert has_time is True and has_z is False

    arr4d = np.zeros((2, 3, 4, 5))
    std, has_time, has_z = standardize_axes(arr4d)
    assert std.shape == (2, 3, 4, 5)
    assert has_time is True and has_z is True


def test_standardize_axes_degenerate_shapes() -> None:
    """Verify standardize axes degenerate shapes for the current workflow."""
    arr3d_single = np.zeros((1, 4, 5))  # ambiguous single axis -> treat as time
    std, has_time, has_z = standardize_axes(arr3d_single)
    assert std.shape == (1, 1, 4, 5)
    assert has_time is True and has_z is False

    arr4d_single_z = np.zeros((2, 1, 4, 5))
    std, has_time, has_z = standardize_axes(arr4d_single_z)
    assert std.shape == (2, 1, 4, 5)
    assert has_time is True and has_z is True

    arr4d_single_t = np.zeros((1, 3, 4, 5))
    std, has_time, has_z = standardize_axes(arr4d_single_t)
    assert std.shape == (1, 3, 4, 5)
    assert has_time is True and has_z is True


def test_standardize_axes_invalid_ome_axes_strict() -> None:
    """Verify standardize axes invalid ome axes strict for the current workflow."""
    arr = np.zeros((3, 4, 5))
    std, has_time, has_z = standardize_axes(arr, ome_axes="CYX", strict=True)
    assert std.shape == (1, 1, 4, 5)
    assert has_time is False and has_z is False

    with pytest.raises(ValueError):
        standardize_axes(arr, ome_axes="TYXW", strict=True)
