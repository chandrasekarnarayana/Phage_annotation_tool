"""Unit tests for the ONNX-runtime density inference engine.

All tests run without a real ONNX model or GPU. The onnxruntime dependency
is mocked where needed so the tests pass in any CI environment.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import phage_annotator.algorithms.onnx_infer as onnx_mod
from phage_annotator.algorithms.onnx_infer import (
    OnnxDensityOptions,
    OnnxDensityResult,
    is_onnxruntime_available,
    list_available_providers,
    resolve_execution_provider,
    get_model_metadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_ort(providers=None):
    """Build a minimal mock onnxruntime module."""
    if providers is None:
        providers = ["CPUExecutionProvider", "CUDAExecutionProvider"]

    ort = types.ModuleType("onnxruntime")
    sess = MagicMock()
    sess.get_inputs.return_value = [
        MagicMock(name="input", shape=[1, 64, 64, 1], type="tensor(float)")
    ]
    sess.get_outputs.return_value = [
        MagicMock(name="output", shape=[1, 64, 64], type="tensor(float)")
    ]
    sess.run.return_value = [np.zeros((1, 64, 64), dtype=np.float32)]
    sess.get_providers.return_value = providers[:1]
    ort.InferenceSession = MagicMock(return_value=sess)

    so_mock = MagicMock()
    ort.SessionOptions = MagicMock(return_value=so_mock)
    ort.GraphOptimizationLevel = MagicMock()
    ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99
    ort.get_available_providers = MagicMock(return_value=providers)
    return ort, sess


# ---------------------------------------------------------------------------
# OnnxDensityOptions — dataclass validation
# ---------------------------------------------------------------------------

class TestOnnxDensityOptions:
    def test_defaults(self):
        opts = OnnxDensityOptions(model_path="model.onnx")
        assert opts.execution_provider == "auto"
        assert opts.channel_format == "NHWC"
        assert opts.tile_size == 256
        assert opts.overlap == 32
        assert opts.count_scale == 1.0

    def test_custom_values(self):
        opts = OnnxDensityOptions(
            model_path="m.onnx",
            execution_provider="CUDAExecutionProvider",
            tile_size=128,
            overlap=16,
            count_scale=2.5,
        )
        assert opts.tile_size == 128
        assert opts.count_scale == 2.5

    def test_frozen(self):
        opts = OnnxDensityOptions(model_path="m.onnx")
        with pytest.raises((TypeError, AttributeError)):
            opts.tile_size = 512  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OnnxDensityResult — dataclass
# ---------------------------------------------------------------------------

class TestOnnxDensityResult:
    def test_basic_fields(self):
        dm = np.zeros((64, 64), dtype=np.float32)
        r = OnnxDensityResult(
            density_map=dm,
            count_total=42.0,
            count_roi=38.0,
            tiles_processed=4,
            runtime_ms=120.0,
            model_path="m.onnx",
            execution_provider="CPUExecutionProvider",
            metadata={},
        )
        assert r.count_total == 42.0
        assert r.density_map.shape == (64, 64)

    def test_count_roi_optional(self):
        dm = np.zeros((32, 32), dtype=np.float32)
        r = OnnxDensityResult(
            density_map=dm,
            count_total=5.0,
            count_roi=None,
            tiles_processed=1,
            runtime_ms=10.0,
            model_path="m.onnx",
            execution_provider="CPUExecutionProvider",
        )
        assert r.count_roi is None


# ---------------------------------------------------------------------------
# is_onnxruntime_available / list_available_providers
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_available_when_ort_present(self):
        fake_ort, _ = _make_fake_ort()
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            assert is_onnxruntime_available() is True

    def test_unavailable_when_ort_none(self):
        with patch.object(onnx_mod, "ort", None), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", False):
            assert is_onnxruntime_available() is False

    def test_list_providers_returns_list(self):
        fake_ort, _ = _make_fake_ort()
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            providers = list_available_providers()
        assert isinstance(providers, list)
        assert "CPUExecutionProvider" in providers

    def test_list_providers_empty_when_unavailable(self):
        with patch.object(onnx_mod, "ort", None), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", False):
            providers = list_available_providers()
        assert providers == []


# ---------------------------------------------------------------------------
# resolve_execution_provider
# ---------------------------------------------------------------------------

class TestResolveExecutionProvider:
    def test_explicit_cpu_returned(self):
        fake_ort, _ = _make_fake_ort(providers=["CPUExecutionProvider"])
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = resolve_execution_provider("CPUExecutionProvider")
        assert result == "CPUExecutionProvider"

    def test_explicit_cuda_when_available(self):
        fake_ort, _ = _make_fake_ort()
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = resolve_execution_provider("CUDAExecutionProvider")
        assert result == "CUDAExecutionProvider"

    def test_auto_prefers_cuda(self):
        fake_ort, _ = _make_fake_ort()
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = resolve_execution_provider("auto")
        assert result == "CUDAExecutionProvider"

    def test_auto_falls_back_to_cpu(self):
        fake_ort, _ = _make_fake_ort(providers=["CPUExecutionProvider"])
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = resolve_execution_provider("auto")
        assert result == "CPUExecutionProvider"

    def test_unavailable_raises(self):
        with patch.object(onnx_mod, "ort", None), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="onnxruntime"):
                resolve_execution_provider("auto")


# ---------------------------------------------------------------------------
# get_model_metadata
# ---------------------------------------------------------------------------

class TestGetModelMetadata:
    def test_returns_inputs_and_outputs(self):
        _, sess = _make_fake_ort()
        meta = get_model_metadata(sess)
        assert "inputs" in meta
        assert "outputs" in meta
        assert isinstance(meta["inputs"], list)
        assert isinstance(meta["outputs"], list)

    def test_fields_present(self):
        _, sess = _make_fake_ort()
        meta = get_model_metadata(sess)
        for inp in meta["inputs"]:
            assert "name" in inp
            assert "shape" in inp


# ---------------------------------------------------------------------------
# run_onnx_density — mocked end-to-end
# ---------------------------------------------------------------------------

class TestRunOnnxDensity:
    def _sess_returning(self, tile_size, value=0.5):
        """Return a mock session whose run() gives a constant tile output."""
        fake_ort, sess = _make_fake_ort()
        sess.run.return_value = [
            np.ones((1, tile_size, tile_size), dtype=np.float32) * value
        ]
        return fake_ort, sess

    def test_returns_result_object(self):
        from phage_annotator.algorithms.onnx_infer import run_onnx_density
        fake_ort, sess = self._sess_returning(64)
        opts = OnnxDensityOptions(
            model_path="model.onnx",
            tile_size=64,
            overlap=8,
        )
        image = np.random.default_rng(0).uniform(0, 1, (128, 128)).astype(np.float32)
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = run_onnx_density(image, opts, session=sess)
        assert isinstance(result, OnnxDensityResult)
        assert result.density_map.shape == (128, 128)
        assert result.count_total >= 0.0
        assert result.tiles_processed > 0

    def test_raises_when_ort_unavailable(self):
        from phage_annotator.algorithms.onnx_infer import run_onnx_density
        opts = OnnxDensityOptions(model_path="model.onnx")
        image = np.zeros((64, 64), dtype=np.float32)
        with patch.object(onnx_mod, "ort", None), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="onnxruntime"):
                run_onnx_density(image, opts)

    def test_roi_mask_applied(self):
        from phage_annotator.algorithms.onnx_infer import run_onnx_density
        fake_ort, sess = self._sess_returning(64, value=1.0)
        opts = OnnxDensityOptions(
            model_path="model.onnx",
            tile_size=64,
            overlap=8,
            use_roi_only=True,
        )
        image = np.ones((128, 128), dtype=np.float32)
        roi = np.zeros((128, 128), dtype=bool)
        roi[32:96, 32:96] = True
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            result = run_onnx_density(image, opts, session=sess, roi_mask=roi)
        assert result.count_roi is not None
        assert result.count_roi <= result.count_total

    def test_progress_callback_called(self):
        from phage_annotator.algorithms.onnx_infer import run_onnx_density
        fake_ort, sess = self._sess_returning(64)
        calls = []
        opts = OnnxDensityOptions(model_path="model.onnx", tile_size=64, overlap=8)
        image = np.ones((128, 128), dtype=np.float32)
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            run_onnx_density(
                image, opts, session=sess,
                progress_cb=lambda pct, msg: calls.append(pct),
            )
        assert len(calls) > 0

    def test_2d_image_required(self):
        from phage_annotator.algorithms.onnx_infer import run_onnx_density
        fake_ort, sess = self._sess_returning(64)
        opts = OnnxDensityOptions(model_path="model.onnx")
        bad_image = np.ones((64, 64, 3), dtype=np.float32)
        with patch.object(onnx_mod, "ort", fake_ort), \
             patch.object(onnx_mod, "_ORT_AVAILABLE", True):
            with pytest.raises(ValueError, match="2-D"):
                run_onnx_density(bad_image, opts, session=sess)
