"""Tests for projection helpers."""

from __future__ import annotations

import numpy as np

from phage_annotator.algorithms.analysis import compute_projection, compute_projections


def _make_data() -> np.ndarray:
    # Shape: (T, Z, Y, X)
    data = np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5)
    return data


def test_compute_projection_mean() -> None:
    data = _make_data()
    expected = data.mean(axis=(0, 1))
    result = compute_projection(data, "mean")
    assert np.allclose(result, expected)


def test_compute_projection_std() -> None:
    data = _make_data()
    expected = data.std(axis=(0, 1))
    result = compute_projection(data, "std")
    assert np.allclose(result, expected)


def test_compute_projection_min() -> None:
    data = _make_data()
    expected = data.min(axis=(0, 1))
    result = compute_projection(data, "min")
    assert np.allclose(result, expected)


def test_compute_projection_max() -> None:
    data = _make_data()
    expected = data.max(axis=(0, 1))
    result = compute_projection(data, "max")
    assert np.allclose(result, expected)


def test_compute_projections_multiple() -> None:
    data = _make_data()
    result = compute_projections(data, ["mean", "std", "min", "max"])
    assert set(result.keys()) == {"mean", "std", "min", "max"}
    assert np.allclose(result["mean"], data.mean(axis=(0, 1)))
    assert np.allclose(result["std"], data.std(axis=(0, 1)))
    assert np.allclose(result["min"], data.min(axis=(0, 1)))
    assert np.allclose(result["max"], data.max(axis=(0, 1)))


def test_compute_projection_axis_t() -> None:
    data = _make_data()
    expected = data.mean(axis=(0,))
    result = compute_projection(data, "mean", axis="t")
    assert np.allclose(result, expected)


def test_compute_projection_axis_z() -> None:
    data = _make_data()
    expected = data.mean(axis=(1,))
    result = compute_projection(data, "mean", axis="z")
    assert np.allclose(result, expected)


def test_compute_projections_invalid_kind() -> None:
    data = _make_data()
    try:
        compute_projection(data, "median")
    except ValueError as exc:
        assert "Unsupported projection kind" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid projection kind")
