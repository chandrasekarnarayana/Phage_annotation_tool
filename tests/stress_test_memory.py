"""
Headless stress test for memory + responsiveness.

Example:
    python -m tests.stress_test_memory --data-dir ./examples --num-fovs 2 --loop 2

Metrics reported:
  - Max RSS during run
  - First-load time per FOV
  - Average T/Z slider step timings
  - FOV switch timings
  - Clear-cache timing and RSS delta
"""

from __future__ import annotations

import argparse
import os
import pathlib
import statistics
import time
from typing import Iterable, List

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import psutil
except ImportError:
    psutil = None

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.gui_mpl import KeypointAnnotator, create_app


def _rss_mb() -> float:
    if psutil:
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    try:
        import resource

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # On Linux ru_maxrss is KiB; on macOS it is bytes.
        if rss_kb > 1e8:  # likely bytes
            return rss_kb / (1024 * 1024)
        return rss_kb / 1024
    except Exception:
        return -1.0


def _files_from_dir(folder: pathlib.Path, num: int) -> List[pathlib.Path]:
    candidates = sorted(
        [
            p
            for p in folder.iterdir()
            if p.suffix.lower() in SUPPORTED_SUFFIXES or p.name.lower().endswith(".ome.tif")
        ]
    )
    if not candidates:
        raise FileNotFoundError(f"No TIFFs found in {folder}")
    return candidates[:num]


def _measure_first_loads(win: KeypointAnnotator) -> List[float]:
    for img in win.images:
        win._evict_image_cache(img)
    times = []
    for idx, _ in enumerate(win.images):
        t0 = time.perf_counter()
        win._ensure_loaded(idx)
        times.append(time.perf_counter() - t0)
    return times


def _measure_slider(win: KeypointAnnotator, slider: QtWidgets.QSlider, loops: int) -> List[float]:
    if slider.maximum() <= slider.minimum():
        return []
    times: List[float] = []
    for _ in range(max(1, loops)):
        for val in range(slider.minimum(), slider.maximum() + 1):
            t0 = time.perf_counter()
            slider.setValue(val)
            QtWidgets.QApplication.processEvents()
            times.append(time.perf_counter() - t0)
    return times


def _measure_fov_switch(win: KeypointAnnotator, loops: int) -> List[float]:
    times: List[float] = []
    for _ in range(max(1, loops)):
        for idx in range(len(win.images)):
            t0 = time.perf_counter()
            win._set_fov(idx)
            QtWidgets.QApplication.processEvents()
            times.append(time.perf_counter() - t0)
    return times


def _measure_playback_read(win: KeypointAnnotator, loops: int) -> float:
    """Synthetic playback read: iterate frames sequentially to estimate disk-limited FPS."""
    win._ensure_loaded(win.current_image_idx)
    img = win.primary_image
    if img.array is None:
        return 0.0
    z_idx = win._slice_indices(img)[1]
    times: List[float] = []
    for _ in range(max(1, loops)):
        for t in range(img.array.shape[0]):
            t0 = time.perf_counter()
            frame = img.array[t, z_idx, :, :]
            # Touch a pixel to force read
            _ = frame.flat[0]
            times.append(time.perf_counter() - t0)
    if not times:
        return 0.0
    avg_dt = statistics.mean(times)
    return 1.0 / avg_dt if avg_dt > 0 else 0.0


def _run(args: argparse.Namespace) -> None:
    paths = _files_from_dir(args.data_dir, args.num_fovs)
    # create_app will run Qt in offscreen mode due to the env var above.
    win = create_app(paths)
    win.hide()

    rss_samples = [_rss_mb()]
    first_loads = _measure_first_loads(win)
    rss_samples.append(_rss_mb())

    fov_switch = _measure_fov_switch(win, args.loop)
    rss_samples.append(_rss_mb())

    t_times = _measure_slider(win, win.t_slider, args.loop)
    rss_samples.append(_rss_mb())
    z_times = _measure_slider(win, win.z_slider, args.loop)
    rss_samples.append(_rss_mb())

    rss_before_clear = _rss_mb()
    t0 = time.perf_counter()
    win._clear_cache()
    QtWidgets.QApplication.processEvents()
    clear_time = time.perf_counter() - t0
    rss_after_clear = _rss_mb()
    rss_samples.append(rss_after_clear)

    playback_fps = None
    if args.playback_test:
        playback_fps = _measure_playback_read(win, args.loop)

    def _avg(vals: Iterable[float]) -> float:
        vals = list(vals)
        return statistics.mean(vals) if vals else 0.0

    print("=== Stress Test Summary ===")
    print(f"Files tested: {[p.name for p in paths]}")
    print(f"Max RSS: {max(rss_samples):.1f} MB")
    print(f"First-load time per FOV: {[f'{t:.3f}s' for t in first_loads]}")
    print(f"Avg FOV switch: {_avg(fov_switch):.4f}s over {len(fov_switch)} switches")
    print(f"Avg T-step: {_avg(t_times):.4f}s over {len(t_times)} steps")
    print(f"Avg Z-step: {_avg(z_times):.4f}s over {len(z_times)} steps")
    print(
        f"Clear cache: {clear_time:.4f}s | RSS {rss_before_clear:.1f} -> {rss_after_clear:.1f} MB"
    )
    if playback_fps is not None:
        print(f"Theoretical disk-limited playback FPS (no GUI): {playback_fps:.1f}")
        if args.fps:
            print(f"Target GUI FPS: {args.fps}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stress test memory + navigation without showing the full GUI."
    )
    parser.add_argument(
        "--data-dir",
        type=pathlib.Path,
        required=True,
        help="Folder containing TIFF/OME-TIFF stacks",
    )
    parser.add_argument("--num-fovs", type=int, default=2, help="Number of fields of view to test")
    parser.add_argument(
        "--loop", type=int, default=1, help="How many times to iterate slider sweeps"
    )
    parser.add_argument(
        "--playback-test",
        action="store_true",
        help="Measure sequential playback read FPS (headless)",
    )
    parser.add_argument(
        "--fps", type=int, default=30, help="Target GUI playback FPS for comparison"
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    _run(args)
