import numpy as np
import pytest

pytest.importorskip("pytest_benchmark")

from phage_annotator.io import standardize_axes


def test_standardize_axes_perf(benchmark) -> None:
    arr = np.random.random((4, 8, 512, 512))
    result = benchmark(standardize_axes, arr)
    assert result[0].shape == (4, 8, 512, 512)
