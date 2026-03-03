"""Optional end-to-end integration tests for Fiji ThunderSTORM bridge."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from phage_annotator.algorithms.smlm_thunderstorm import SmlmParams
from phage_annotator.smlm.backends import ThunderstormBridgeConfig, run_thunderstorm_backend


pytestmark = pytest.mark.integration


def _synthetic_frames() -> list[tuple[int, np.ndarray]]:
    rng = np.random.default_rng(7)
    frames: list[tuple[int, np.ndarray]] = []
    for t in range(3):
        frame = rng.normal(10, 1.2, size=(64, 64)).astype(np.float32)
        frame[20 + t, 22 + t] += 70.0
        frame[40 - t, 40] += 60.0
        frames.append((t, frame))
    return frames


@pytest.mark.skipif(
    not os.environ.get("FIJI_APP_PATH"),
    reason="Set FIJI_APP_PATH and FIJI_EXE_PATH to run real Fiji integration test.",
)
def test_fiji_subprocess_bridge_end_to_end(tmp_path: Path) -> None:
    fiji_exe = os.environ.get("FIJI_EXE_PATH", "")
    if not fiji_exe:
        pytest.skip("FIJI_EXE_PATH not set")
    macro = os.environ.get("FIJI_THUNDERSTORM_MACRO", "")
    if not macro:
        macro = str(Path("external_plugins") / "thunderstorm_macro.ijm")
    config = ThunderstormBridgeConfig(
        backend="fiji_subprocess",
        fiji_executable=fiji_exe,
        macro_path=macro,
        plugin_id="thunder_storm",
        plugin_jar_path=str(Path("external_plugins") / "Thunder_STORM.jar"),
        timeout_sec=120,
        plugin_parameters={
            "sigma_px": 1.3,
            "fit_radius_px": 4,
            "detection_thr_sigma": 3.0,
        },
    )
    frames = _synthetic_frames()
    locs, _sr, meta = run_thunderstorm_backend(
        frames,
        total_frames=len(frames),
        roi_mask=np.ones((64, 64), dtype=bool),
        roi_rect=(0.0, 0.0, 64.0, 64.0),
        crop_offset=(0, 0),
        params=SmlmParams(),
        pixel_size_nm=100.0,
        config=config,
        progress_cb=None,
        is_cancelled=None,
    )
    assert "output_csv" in meta
    assert len(locs) >= 1
    assert all(0.0 <= loc.x_px <= 64.0 for loc in locs)
    assert all(0.0 <= loc.y_px <= 64.0 for loc in locs)
    assert all(loc.sigma_px > 0 for loc in locs)
    assert all(loc.photons >= 0 for loc in locs)
    # Deterministic-ish invariant: repeated run count should remain within a small tolerance.
    locs_repeat, _sr2, _meta2 = run_thunderstorm_backend(
        frames,
        total_frames=len(frames),
        roi_mask=np.ones((64, 64), dtype=bool),
        roi_rect=(0.0, 0.0, 64.0, 64.0),
        crop_offset=(0, 0),
        params=SmlmParams(),
        pixel_size_nm=100.0,
        config=config,
        progress_cb=None,
        is_cancelled=None,
    )
    assert abs(len(locs_repeat) - len(locs)) <= max(2, int(0.2 * max(1, len(locs))))
