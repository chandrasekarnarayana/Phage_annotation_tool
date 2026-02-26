import numpy as np

from phage_annotator.io import standardize_axes


def test_standardize_axes_basic_shapes() -> None:
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
