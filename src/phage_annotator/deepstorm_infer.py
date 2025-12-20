"""Deep-STORM style ROI-only super-resolution reconstruction.

This module runs a PyTorch model on tiled ROI patches and stitches the outputs
into a single super-resolution image. It operates on streamed frames and
keeps computations CPU/GPU friendly via patch inference and overlap blending.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from phage_annotator.analysis import local_maxima, mad_sigma


try:  # Optional dependency
    import torch
except Exception:  # pragma: no cover - optional import
    torch = None


@dataclass(frozen=True)
class DeepStormParams:
    """Parameters for Deep-STORM style inference."""

    model_path: str
    patch_size: int = 64
    overlap: int = 16
    upsample: int = 8
    sigma_px: float = 1.3
    normalize_mode: str = "per_patch"
    output_mode: str = "sr_image"
    window_size: int = 5
    aggregation_mode: str = "mean"


@dataclass(frozen=True)
class DeepLocalization:
    """Localization extracted from a Deep-STORM SR image."""

    x_px: float
    y_px: float
    score: float


def is_torch_available() -> bool:
    return torch is not None


def load_model(model_path: str, device: str):
    """Load a TorchScript or state-dict model from disk."""
    if torch is None:
        raise RuntimeError("PyTorch is not available.")
    try:
        model = torch.jit.load(model_path, map_location=device)
        model.eval()
        return model
    except Exception:
        obj = torch.load(model_path, map_location=device)
        if hasattr(obj, "eval"):
            model = obj
        elif isinstance(obj, dict) and "model" in obj:
            model = obj["model"]
        else:
            raise RuntimeError("Unsupported model format.")
        model.eval()
        return model


def run_deepstorm_stream(
    frames: Iterable[Tuple[int, np.ndarray]],
    total_frames: int,
    roi_rect: Tuple[float, float, float, float],
    params: DeepStormParams,
    device: str,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, List[DeepLocalization]]:
    """Run Deep-STORM inference over a streamed frame iterator."""
    model = load_model(params.model_path, device)
    if total_frames <= 0:
        return np.zeros((1, 1), dtype=np.float32), []

    patch_size = int(params.patch_size)
    overlap = int(params.overlap)
    upsample = int(params.upsample)
    step = max(1, patch_size - overlap)
    rx, ry, rw, rh = roi_rect
    roi_h = max(1, int(round(rh)))
    roi_w = max(1, int(round(rw)))
    sr_h = roi_h * upsample
    sr_w = roi_w * upsample
    sr_accum = np.zeros((sr_h, sr_w), dtype=np.float32)
    weight_accum = np.zeros((sr_h, sr_w), dtype=np.float32)

    tiles = _tile_starts(roi_h, roi_w, patch_size, step)
    total_tiles = len(tiles)

    frame_buffer: List[np.ndarray] = []
    for idx, frame in frames:
        if is_cancelled is not None and is_cancelled():
            break
        frame_buffer.append(frame.astype(np.float32, copy=False))
        if len(frame_buffer) < params.window_size:
            continue
        if len(frame_buffer) > params.window_size:
            frame_buffer.pop(0)
        agg = _aggregate_frames(frame_buffer, params.aggregation_mode)
        if params.normalize_mode == "global_roi":
            agg_norm = _normalize_global(agg)
        else:
            agg_norm = agg

        for tile_idx, (y0, x0) in enumerate(tiles, start=1):
            if is_cancelled is not None and is_cancelled():
                break
            patch = _extract_patch(agg_norm, y0, x0, patch_size)
            if params.normalize_mode == "per_patch":
                patch = _normalize_global(patch)
            sr_patch = _infer_patch(model, patch, device, upsample)
            _blend_patch(sr_accum, weight_accum, sr_patch, y0 * upsample, x0 * upsample)
            if progress_cb is not None:
                pct = int((idx * total_tiles + tile_idx) / max(1, total_frames * total_tiles) * 100)
                progress_cb(pct, f"Frame {idx + 1}/{total_frames} | Tile {tile_idx}/{total_tiles}")

    sr = _finalize_sr(sr_accum, weight_accum)
    locs = localizations_from_sr(sr, roi_rect, upsample)
    return sr, locs


def localizations_from_sr(
    sr: np.ndarray,
    roi_rect: Tuple[float, float, float, float],
    upsample: int,
    thr_sigma: float = 3.0,
) -> List[DeepLocalization]:
    """Extract approximate localizations from an SR image."""
    if sr.size == 0:
        return []
    med = np.median(sr)
    sigma = mad_sigma(sr)
    threshold = med + thr_sigma * sigma
    coords = local_maxima(sr, threshold, footprint=3)
    rx, ry, _, _ = roi_rect
    locs: List[DeepLocalization] = []
    for y, x in coords:
        locs.append(
            DeepLocalization(
                x_px=float(rx + x / max(1, upsample)),
                y_px=float(ry + y / max(1, upsample)),
                score=float(sr[y, x]),
            )
        )
    return locs


def _aggregate_frames(frames: Sequence[np.ndarray], mode: str) -> np.ndarray:
    if mode == "stack":
        return np.stack(frames, axis=0)
    return np.mean(frames, axis=0)


def _normalize_global(arr: np.ndarray) -> np.ndarray:
    data = arr.astype(np.float32, copy=False)
    mean = float(np.mean(data))
    std = float(np.std(data))
    if std <= 0:
        return data - mean
    return (data - mean) / std


def _tile_starts(h: int, w: int, patch: int, step: int) -> List[Tuple[int, int]]:
    ys = list(range(0, max(1, h - patch + 1), step))
    xs = list(range(0, max(1, w - patch + 1), step))
    if not ys or ys[-1] != h - patch:
        ys.append(max(0, h - patch))
    if not xs or xs[-1] != w - patch:
        xs.append(max(0, w - patch))
    return [(y, x) for y in ys for x in xs]


def _extract_patch(arr: np.ndarray, y0: int, x0: int, size: int) -> np.ndarray:
    if arr.ndim == 2:
        h, w = arr.shape
        patch = arr[y0:y0 + size, x0:x0 + size]
    else:
        _, h, w = arr.shape
        patch = arr[:, y0:y0 + size, x0:x0 + size]
    pad_h = max(0, size - patch.shape[-2])
    pad_w = max(0, size - patch.shape[-1])
    if pad_h or pad_w:
        pad_cfg = [(0, 0)] * patch.ndim
        pad_cfg[-2] = (0, pad_h)
        pad_cfg[-1] = (0, pad_w)
        patch = np.pad(patch, pad_cfg, mode="reflect")
    return patch


def _infer_patch(model, patch: np.ndarray, device: str, upsample: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("PyTorch is not available.")
    if patch.ndim == 2:
        inp = patch[None, None, :, :]
    else:
        inp = patch[None, :, :, :]
    tensor = torch.from_numpy(inp.astype(np.float32, copy=False)).to(device)
    with torch.no_grad():
        output = model(tensor)
    if isinstance(output, (list, tuple)):
        output = output[0]
    out = output.squeeze().detach().cpu().numpy()
    if out.ndim == 2:
        return out
    if out.ndim == 3:
        return out[0]
    return np.zeros((patch.shape[-2] * upsample, patch.shape[-1] * upsample), dtype=np.float32)


def _blend_patch(sr_accum: np.ndarray, weight_accum: np.ndarray, patch: np.ndarray, y0: int, x0: int) -> None:
    ph, pw = patch.shape
    y1 = min(sr_accum.shape[0], y0 + ph)
    x1 = min(sr_accum.shape[1], x0 + pw)
    patch = patch[: y1 - y0, : x1 - x0]
    weight = _weight_mask(patch.shape[0], patch.shape[1])
    sr_accum[y0:y1, x0:x1] += patch * weight
    weight_accum[y0:y1, x0:x1] += weight


def _weight_mask(h: int, w: int) -> np.ndarray:
    wy = np.hanning(h) if h > 1 else np.ones((1,), dtype=np.float32)
    wx = np.hanning(w) if w > 1 else np.ones((1,), dtype=np.float32)
    mask = np.outer(wy, wx).astype(np.float32, copy=False)
    if mask.max() <= 0:
        return np.ones((h, w), dtype=np.float32)
    return mask


def _finalize_sr(sr_accum: np.ndarray, weight_accum: np.ndarray) -> np.ndarray:
    out = sr_accum.copy()
    mask = weight_accum > 0
    out[mask] = sr_accum[mask] / weight_accum[mask]
    return out
