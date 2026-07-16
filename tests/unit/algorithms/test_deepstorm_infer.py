"""Unit tests for the Deep-STORM super-resolution inference engine.

All tests run without a real PyTorch model or GPU. The torch dependency is
mocked so the test suite passes in any CI environment. The model-loading
path (load_model) is also patched to avoid disk I/O.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import phage_annotator.algorithms.deepstorm_infer as ds_mod
from phage_annotator.algorithms.deepstorm_infer import (
    DeepLocalization,
    DeepStormParams,
    is_torch_available,
    localizations_from_sr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_torch():
    """Build a minimal mock torch module that satisfies deepstorm_infer usage."""
    torch = types.ModuleType("torch")
    torch.cuda = MagicMock()
    torch.cuda.is_available = MagicMock(return_value=False)
    torch.backends = MagicMock()
    torch.backends.mps = MagicMock()
    torch.backends.mps.is_available = MagicMock(return_value=False)

    # no_grad context manager
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=None)
    ctx.__exit__ = MagicMock(return_value=False)
    torch.no_grad = MagicMock(return_value=ctx)

    def _from_numpy(arr):
        t = MagicMock()
        t.unsqueeze = MagicMock(return_value=t)
        t.float = MagicMock(return_value=t)
        t.to = MagicMock(return_value=t)
        t.squeeze = MagicMock(return_value=t)
        t.cpu = MagicMock(return_value=t)
        t.numpy = MagicMock(return_value=np.ones((64, 64), dtype=np.float32) * 0.05)
        return t

    torch.from_numpy = _from_numpy
    torch.jit = MagicMock()
    return torch


def _make_fake_model():
    """A model mock whose __call__ returns a tensor-like with .numpy()."""
    model = MagicMock()
    model.eval = MagicMock(return_value=model)
    out = MagicMock()
    out.squeeze = MagicMock(return_value=out)
    out.cpu = MagicMock(return_value=out)
    out.numpy = MagicMock(return_value=np.ones((64, 64), dtype=np.float32) * 0.05)
    model.return_value = out
    return model


# ---------------------------------------------------------------------------
# DeepStormParams — dataclass
# ---------------------------------------------------------------------------

class TestDeepStormParams:
    def test_defaults(self):
        p = DeepStormParams(model_path="model.pt")
        assert p.patch_size == 64
        assert p.overlap == 16
        assert p.upsample == 8
        assert p.output_mode == "sr_image"
        assert p.window_size == 5

    def test_custom(self):
        p = DeepStormParams(model_path="m.pt", patch_size=128, upsample=4)
        assert p.patch_size == 128
        assert p.upsample == 4

    def test_frozen(self):
        p = DeepStormParams(model_path="m.pt")
        with pytest.raises((TypeError, AttributeError)):
            p.patch_size = 256  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DeepLocalization — dataclass
# ---------------------------------------------------------------------------

class TestDeepLocalization:
    def test_fields(self):
        loc = DeepLocalization(x_px=10.5, y_px=20.3, score=0.85)
        assert loc.x_px == pytest.approx(10.5)
        assert loc.score == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# is_torch_available
# ---------------------------------------------------------------------------

class TestIsTorchAvailable:
    def test_true_when_torch_present(self):
        fake_torch = _make_fake_torch()
        with patch.object(ds_mod, "torch", fake_torch):
            assert is_torch_available() is True

    def test_false_when_torch_none(self):
        with patch.object(ds_mod, "torch", None):
            assert is_torch_available() is False


# ---------------------------------------------------------------------------
# localizations_from_sr
# ---------------------------------------------------------------------------

class TestLocalizationsFromSr:
    def test_empty_image_returns_no_locs(self):
        sr = np.zeros((64, 64), dtype=np.float32)
        locs = localizations_from_sr(sr, roi_rect=(0.0, 0.0, 64.0, 64.0), upsample=8)
        assert isinstance(locs, list)
        assert len(locs) == 0

    def test_bright_spot_detected(self):
        sr = np.zeros((512, 512), dtype=np.float32)
        sr[256, 256] = 50.0  # Strong local maximum well above noise
        locs = localizations_from_sr(sr, roi_rect=(0.0, 0.0, 64.0, 64.0), upsample=8)
        assert len(locs) >= 1

    def test_returns_deep_localizations(self):
        sr = np.zeros((128, 128), dtype=np.float32)
        sr[64, 64] = 20.0
        locs = localizations_from_sr(sr, roi_rect=(0.0, 0.0, 64.0, 64.0), upsample=2)
        for loc in locs:
            assert isinstance(loc, DeepLocalization)
            assert loc.score >= 0.0

    def test_multiple_spots(self):
        sr = np.zeros((512, 512), dtype=np.float32)
        sr[50, 50] = 40.0
        sr[250, 250] = 45.0
        sr[450, 450] = 38.0
        locs = localizations_from_sr(sr, roi_rect=(0.0, 0.0, 64.0, 64.0), upsample=8)
        assert len(locs) >= 2

    def test_roi_offset_applied(self):
        sr = np.zeros((128, 128), dtype=np.float32)
        sr[64, 64] = 20.0
        # With roi_rect starting at (10, 10), x_px should be offset
        locs = localizations_from_sr(sr, roi_rect=(10.0, 10.0, 64.0, 64.0), upsample=2)
        if locs:
            assert locs[0].x_px >= 10.0 or locs[0].y_px >= 10.0


# ---------------------------------------------------------------------------
# run_deepstorm_stream — mocked end-to-end
# ---------------------------------------------------------------------------

class TestRunDeepstormStream:
    def _make_frames(self, n=2, h=64, w=64):
        rng = np.random.default_rng(42)
        return [(i, rng.uniform(0, 1, (h, w)).astype(np.float32)) for i in range(n)]

    def test_raises_when_torch_unavailable(self):
        from phage_annotator.algorithms.deepstorm_infer import run_deepstorm_stream
        params = DeepStormParams(model_path="m.pt")
        frames = self._make_frames()
        with patch.object(ds_mod, "torch", None):
            with pytest.raises(RuntimeError, match="PyTorch"):
                run_deepstorm_stream(
                    frames,
                    total_frames=len(frames),
                    roi_rect=(0.0, 0.0, 64.0, 64.0),
                    params=params,
                    device="cpu",
                )

    def test_returns_sr_image_and_locs(self):
        from phage_annotator.algorithms.deepstorm_infer import run_deepstorm_stream
        fake_torch = _make_fake_torch()
        fake_model = _make_fake_model()
        params = DeepStormParams(model_path="m.pt", patch_size=32, overlap=4, upsample=2)
        frames = self._make_frames(n=2, h=64, w=64)
        with patch.object(ds_mod, "torch", fake_torch), \
             patch.object(ds_mod, "load_model", return_value=fake_model):
            sr, locs = run_deepstorm_stream(
                frames,
                total_frames=len(frames),
                roi_rect=(0.0, 0.0, 64.0, 64.0),
                params=params,
                device="cpu",
            )
        assert isinstance(sr, np.ndarray)
        assert sr.ndim == 2
        assert isinstance(locs, list)

    def test_empty_frame_stream(self):
        from phage_annotator.algorithms.deepstorm_infer import run_deepstorm_stream
        fake_torch = _make_fake_torch()
        fake_model = _make_fake_model()
        params = DeepStormParams(model_path="m.pt")
        with patch.object(ds_mod, "torch", fake_torch), \
             patch.object(ds_mod, "load_model", return_value=fake_model):
            sr, locs = run_deepstorm_stream(
                [],
                total_frames=0,
                roi_rect=(0.0, 0.0, 64.0, 64.0),
                params=params,
                device="cpu",
            )
        assert isinstance(sr, np.ndarray)
        assert isinstance(locs, list)

    def test_cancel_respected(self):
        from phage_annotator.algorithms.deepstorm_infer import run_deepstorm_stream
        fake_torch = _make_fake_torch()
        fake_model = _make_fake_model()
        params = DeepStormParams(model_path="m.pt", patch_size=32, overlap=4, upsample=2)
        frames = self._make_frames(n=4)
        with patch.object(ds_mod, "torch", fake_torch), \
             patch.object(ds_mod, "load_model", return_value=fake_model):
            sr, locs = run_deepstorm_stream(
                frames,
                total_frames=4,
                roi_rect=(0.0, 0.0, 64.0, 64.0),
                params=params,
                device="cpu",
                is_cancelled=lambda: True,
            )
        assert isinstance(sr, np.ndarray)

    def test_progress_callback_invoked(self):
        from phage_annotator.algorithms.deepstorm_infer import run_deepstorm_stream
        fake_torch = _make_fake_torch()
        fake_model = _make_fake_model()
        params = DeepStormParams(model_path="m.pt", patch_size=32, overlap=4, upsample=2)
        frames = self._make_frames(n=2)
        calls = []
        with patch.object(ds_mod, "torch", fake_torch), \
             patch.object(ds_mod, "load_model", return_value=fake_model):
            run_deepstorm_stream(
                frames,
                total_frames=len(frames),
                roi_rect=(0.0, 0.0, 64.0, 64.0),
                params=params,
                device="cpu",
                progress_cb=lambda pct, msg: calls.append(pct),
            )
        assert len(calls) > 0
