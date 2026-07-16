"""ONNX-runtime density inference for TensorFlow-exported models.

Loads an ONNX model produced by TensorFlow (via tf2onnx or the Keras/TF ONNX
export path) and runs tiled inference over a 2-D fluorescence image to
generate a particle-density map. The implementation mirrors the tiled-blending
strategy used in :mod:`phage_annotator.algorithms.density_infer` so that
PyTorch and ONNX backends can be used interchangeably.

Supported model contracts
-------------------------
Input:
    ``(batch, H, W, C)`` or ``(batch, C, H, W)`` float32 tensor. If the model
    expects a channel-last layout (TensorFlow default) the ``channel_format``
    option must be set to ``"NHWC"``; for channel-first PyTorch-exported ONNX
    models use ``"NCHW"``.
Output:
    ``(batch, H, W)`` or ``(batch, H, W, 1)`` float32 density map.

Usage example
-------------
>>> from phage_annotator.algorithms.onnx_infer import OnnxDensityOptions, run_onnx_density
>>> opts = OnnxDensityOptions(model_path="model.onnx", execution_provider="CUDAExecutionProvider")
>>> result = run_onnx_density(image, opts)
>>> print(f"Estimated count: {result.count_total:.1f}")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from phage_annotator.cache.array_pool import acquire_array, release_array

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except Exception:  # pragma: no cover
    ort = None  # type: ignore[assignment]
    _ORT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public API types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnnxDensityOptions:
    """Configuration for ONNX-based density inference.

    Parameters
    ----------
    model_path:
        Path to the ``.onnx`` model file exported from TensorFlow or PyTorch.
    execution_provider:
        ONNX Runtime execution provider.  Typical values are
        ``"CPUExecutionProvider"`` and ``"CUDAExecutionProvider"``.  Pass
        ``"auto"`` (default) to select CUDA if available, otherwise CPU.
    channel_format:
        Memory layout expected by the model — ``"NHWC"`` (TensorFlow default)
        or ``"NCHW"`` (PyTorch default).
    normalize_mode:
        Pre-processing normalisation applied per-tile before inference.
        ``"percentile"`` clips to *p_low*–*p_high* percentiles then rescales
        to [0, 1].  ``"zscore"`` applies zero-mean / unit-variance
        normalisation.  ``"minmax"`` rescales to [0, 1] using global
        min/max.  ``"none"`` skips normalisation.
    p_low / p_high:
        Percentile bounds used when *normalize_mode* is ``"percentile"``.
    invert:
        Invert intensity before inference (useful for bright-field images).
    tile_size:
        Side length of square tiles fed to the model (pixels).
    overlap:
        Overlap between adjacent tiles (pixels).  Blended via a raised-cosine
        weight window to avoid seam artefacts.
    batch_tiles:
        Number of tiles per inference batch.  Larger values increase GPU
        memory usage but reduce Python overhead.
    count_scale:
        Scalar multiplier applied to the summed density map to convert raw
        model output to an estimated particle count.  Calibrate this against
        a known-count image during model validation.
    threshold_clip_min:
        Minimum value below which density map pixels are zeroed.  Set to a
        small positive value to suppress background noise.
    use_roi_only:
        If *True*, inference is restricted to the bounding box of the active
        ROI, reducing computation on empty image regions.
    stitch_mode:
        Tile blending strategy: ``"weighted"`` (raised-cosine window,
        recommended) or ``"flat"`` (uniform weight, faster).
    inter_op_threads / intra_op_threads:
        ONNX Runtime threading parameters.  ``0`` uses the runtime default.
    """

    model_path: str = ""
    execution_provider: str = "auto"
    channel_format: str = "NHWC"
    normalize_mode: str = "percentile"
    p_low: float = 1.0
    p_high: float = 99.0
    invert: bool = False
    tile_size: int = 256
    overlap: int = 32
    batch_tiles: int = 8
    count_scale: float = 1.0
    threshold_clip_min: float = 0.0
    use_roi_only: bool = True
    stitch_mode: str = "weighted"
    inter_op_threads: int = 0
    intra_op_threads: int = 0


@dataclass
class OnnxDensityResult:
    """Result bundle returned by :func:`run_onnx_density`."""

    density_map: np.ndarray
    count_total: float
    count_roi: Optional[float]
    tiles_processed: int
    runtime_ms: float
    model_path: str
    execution_provider: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------------


def is_onnxruntime_available() -> bool:
    """Return *True* when ``onnxruntime`` is importable."""
    return _ORT_AVAILABLE


def list_available_providers() -> List[str]:
    """Return execution providers available in the current onnxruntime install."""
    if not _ORT_AVAILABLE:
        return []
    return list(ort.get_available_providers())


def resolve_execution_provider(requested: str) -> str:
    """Resolve ``"auto"`` to the best available provider.

    Returns
    -------
    str
        A concrete provider string suitable for :class:`onnxruntime.InferenceSession`.
    """
    if not _ORT_AVAILABLE:
        raise RuntimeError(
            "onnxruntime is not installed.  Install it with:\n"
            "  pip install onnxruntime          # CPU-only\n"
            "  pip install onnxruntime-gpu      # CUDA support"
        )
    available = ort.get_available_providers()
    if requested != "auto":
        if requested in available:
            return requested
        logger.warning(
            "Requested provider %r not available (have: %s); falling back to CPU.",
            requested,
            available,
        )
        return "CPUExecutionProvider"
    if "CUDAExecutionProvider" in available:
        logger.info("ONNX auto-provider: selected CUDAExecutionProvider.")
        return "CUDAExecutionProvider"
    if "CoreMLExecutionProvider" in available:
        logger.info("ONNX auto-provider: selected CoreMLExecutionProvider.")
        return "CoreMLExecutionProvider"
    return "CPUExecutionProvider"


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def load_onnx_session(
    model_path: str,
    execution_provider: str = "auto",
    inter_op_threads: int = 0,
    intra_op_threads: int = 0,
) -> "ort.InferenceSession":
    """Create an ONNX Runtime inference session.

    Parameters
    ----------
    model_path:
        Path to the ``.onnx`` model file.
    execution_provider:
        ``"auto"``, ``"CPUExecutionProvider"``, ``"CUDAExecutionProvider"``, etc.
    inter_op_threads / intra_op_threads:
        Threading controls.  ``0`` uses the runtime default.

    Raises
    ------
    RuntimeError
        If onnxruntime is not installed or the model cannot be loaded.
    """
    if not _ORT_AVAILABLE:
        raise RuntimeError("onnxruntime is not installed.")
    provider = resolve_execution_provider(execution_provider)
    so = ort.SessionOptions()
    if inter_op_threads > 0:
        so.inter_op_num_threads = inter_op_threads
    if intra_op_threads > 0:
        so.intra_op_num_threads = intra_op_threads
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        session = ort.InferenceSession(model_path, sess_options=so, providers=[provider])
    except Exception as exc:
        raise RuntimeError(f"Failed to load ONNX model from {model_path!r}: {exc}") from exc
    logger.info("ONNX session loaded: %s  provider=%s", model_path, provider)
    return session


def get_model_metadata(session: "ort.InferenceSession") -> Dict[str, Any]:
    """Extract input/output shape metadata from a loaded ONNX session."""
    inputs = [
        {"name": i.name, "shape": i.shape, "dtype": i.type} for i in session.get_inputs()
    ]
    outputs = [
        {"name": o.name, "shape": o.shape, "dtype": o.type} for o in session.get_outputs()
    ]
    return {"inputs": inputs, "outputs": outputs}


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------


def _normalize_tile(tile: np.ndarray, opts: OnnxDensityOptions) -> np.ndarray:
    """Apply per-tile normalisation according to *opts.normalize_mode*."""
    tile = tile.astype(np.float32, copy=False)
    if opts.invert:
        tile = tile.max() - tile
    mode = opts.normalize_mode
    if mode == "none":
        return tile
    if mode == "zscore":
        mu = float(np.mean(tile))
        sigma = float(np.std(tile))
        return (tile - mu) / max(sigma, 1e-8)
    if mode == "minmax":
        lo, hi = float(tile.min()), float(tile.max())
        return (tile - lo) / max(hi - lo, 1e-8)
    # percentile (default)
    lo = float(np.percentile(tile, opts.p_low))
    hi = float(np.percentile(tile, opts.p_high))
    clipped = np.clip(tile, lo, hi)
    return (clipped - lo) / max(hi - lo, 1e-8)


# ---------------------------------------------------------------------------
# Tiling helpers
# ---------------------------------------------------------------------------


def _tile_grid(h: int, w: int, tile: int, stride: int) -> List[Tuple[int, int]]:
    """Return (y0, x0) start positions for a tile grid covering (*h*, *w*)."""
    ys = list(range(0, max(1, h - tile + 1), stride))
    xs = list(range(0, max(1, w - tile + 1), stride))
    if not ys or ys[-1] < h - tile:
        ys.append(max(0, h - tile))
    if not xs or xs[-1] < w - tile:
        xs.append(max(0, w - tile))
    return [(y, x) for y in ys for x in xs]


_COSINE_WINDOW_CACHE: Dict[int, np.ndarray] = {}


def _cosine_window(size: int) -> np.ndarray:
    key = size
    cached = _COSINE_WINDOW_CACHE.get(key)
    if cached is not None:
        return cached
    if size <= 1:
        w = np.ones((1, 1), dtype=np.float32)
    else:
        x = np.linspace(0.0, np.pi, size)
        w1d = 0.5 - 0.5 * np.cos(x)
        w = np.outer(w1d, w1d).astype(np.float32)
    _COSINE_WINDOW_CACHE[key] = w
    return w


def _extract_tile(image: np.ndarray, y0: int, x0: int, size: int) -> np.ndarray:
    patch = image[y0 : y0 + size, x0 : x0 + size]
    ph, pw = patch.shape[:2]
    if ph < size or pw < size:
        pad_h = size - ph
        pad_w = size - pw
        patch = np.pad(patch, ((0, pad_h), (0, pad_w)), mode="reflect")
    return patch


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------


def _build_batch(
    tiles: Sequence[np.ndarray],
    channel_format: str,
) -> np.ndarray:
    """Stack normalised tiles into a batch tensor with correct channel layout."""
    stack = np.stack([t for t in tiles], axis=0)  # (B, H, W)
    if channel_format == "NHWC":
        return stack[:, :, :, np.newaxis].astype(np.float32)  # (B, H, W, 1)
    return stack[:, np.newaxis, :, :].astype(np.float32)  # (B, 1, H, W)


def _run_batch(
    session: "ort.InferenceSession",
    batch: np.ndarray,
) -> np.ndarray:
    """Run one batch through the ONNX session, returning ``(B, H, W)`` output."""
    input_name = session.get_inputs()[0].name
    raw = session.run(None, {input_name: batch})[0]
    out = np.asarray(raw, dtype=np.float32)
    # Normalise shape to (B, H, W)
    if out.ndim == 4 and out.shape[-1] == 1:
        out = out[:, :, :, 0]
    elif out.ndim == 4 and out.shape[1] == 1:
        out = out[:, 0, :, :]
    return out


def _blend_predictions(
    accum: np.ndarray,
    weight_accum: np.ndarray,
    preds: np.ndarray,
    positions: Sequence[Tuple[int, int]],
    tile_size: int,
    window: np.ndarray,
) -> None:
    for (y0, x0), pred in zip(positions, preds):
        ph, pw = pred.shape
        y1 = min(accum.shape[0], y0 + ph)
        x1 = min(accum.shape[1], x0 + pw)
        pred_clip = pred[: y1 - y0, : x1 - x0]
        w = window[: y1 - y0, : x1 - x0]
        accum[y0:y1, x0:x1] += pred_clip * w
        weight_accum[y0:y1, x0:x1] += w


# ---------------------------------------------------------------------------
# Main inference entry-point
# ---------------------------------------------------------------------------


def run_onnx_density(
    image2d: np.ndarray,
    opts: OnnxDensityOptions,
    session: Optional["ort.InferenceSession"] = None,
    roi_mask: Optional[np.ndarray] = None,
    progress_cb: Optional[Any] = None,
) -> OnnxDensityResult:
    """Run tiled ONNX density inference over a 2-D image.

    Parameters
    ----------
    image2d:
        Input fluorescence image, shape ``(H, W)``, dtype float32 or uint16.
    opts:
        Inference configuration; see :class:`OnnxDensityOptions`.
    session:
        Optional pre-loaded :class:`onnxruntime.InferenceSession`.  If
        *None* the session is created from ``opts.model_path``.
    roi_mask:
        Optional boolean array of shape ``(H, W)`` defining the region of
        interest.  Density values outside the ROI are zeroed after inference.
    progress_cb:
        Optional callable ``(percent: int, message: str) -> None`` invoked
        after each tile batch.

    Returns
    -------
    OnnxDensityResult
        Density map, estimated counts, and diagnostics.
    """
    if not _ORT_AVAILABLE:
        raise RuntimeError(
            "onnxruntime is required for ONNX inference.  Install with:\n"
            "  pip install onnxruntime      # CPU\n"
            "  pip install onnxruntime-gpu  # GPU/CUDA"
        )

    t0 = time.perf_counter()
    image = np.asarray(image2d, dtype=np.float32)
    if image.ndim != 2:
        raise ValueError(f"Expected 2-D image, got shape {image.shape}.")

    if session is None:
        session = load_onnx_session(
            opts.model_path,
            execution_provider=opts.execution_provider,
            inter_op_threads=opts.inter_op_threads,
            intra_op_threads=opts.intra_op_threads,
        )

    provider = session.get_providers()[0] if session.get_providers() else "unknown"
    h, w = image.shape
    tile = int(opts.tile_size)
    overlap = int(opts.overlap)
    stride = max(1, tile - overlap)
    positions = _tile_grid(h, w, tile, stride)
    n_tiles = len(positions)
    window = _cosine_window(tile) if opts.stitch_mode == "weighted" else np.ones((tile, tile), dtype=np.float32)

    accum = acquire_array((h, w), np.float32, fill=0.0)
    weight_accum = acquire_array((h, w), np.float32, fill=0.0)
    tiles_processed = 0

    try:
        batch_tiles: List[np.ndarray] = []
        batch_pos: List[Tuple[int, int]] = []

        for i, (y0, x0) in enumerate(positions):
            raw_tile = _extract_tile(image, y0, x0, tile)
            norm_tile = _normalize_tile(raw_tile, opts)
            batch_tiles.append(norm_tile)
            batch_pos.append((y0, x0))

            if len(batch_tiles) >= opts.batch_tiles or i == n_tiles - 1:
                batch_arr = _build_batch(batch_tiles, opts.channel_format)
                preds = _run_batch(session, batch_arr)
                _blend_predictions(accum, weight_accum, preds, batch_pos, tile, window)
                tiles_processed += len(batch_tiles)
                if progress_cb is not None:
                    pct = int(tiles_processed / max(1, n_tiles) * 100)
                    progress_cb(pct, f"Tile {tiles_processed}/{n_tiles}")
                batch_tiles = []
                batch_pos = []

        # Normalise accumulator
        np.maximum(weight_accum, 1e-8, out=weight_accum)
        density = accum / weight_accum

        # Apply minimum threshold to suppress background
        if opts.threshold_clip_min > 0.0:
            np.maximum(density, opts.threshold_clip_min, out=density)
            density -= opts.threshold_clip_min

        # Apply ROI mask
        density_roi: Optional[float] = None
        if roi_mask is not None:
            density_roi = float(density[roi_mask].sum() * opts.count_scale)
            density_out = density.copy()
            density_out[~roi_mask] = 0.0
        else:
            density_out = density.copy()

        count_total = float(density_out.sum() * opts.count_scale)
        runtime_ms = (time.perf_counter() - t0) * 1000.0

        return OnnxDensityResult(
            density_map=density_out,
            count_total=count_total,
            count_roi=density_roi,
            tiles_processed=tiles_processed,
            runtime_ms=runtime_ms,
            model_path=opts.model_path,
            execution_provider=provider,
            metadata={
                "tile_size": tile,
                "overlap": overlap,
                "normalize_mode": opts.normalize_mode,
                "channel_format": opts.channel_format,
                "stitch_mode": opts.stitch_mode,
                "image_shape": (h, w),
            },
        )
    finally:
        release_array(accum)
        release_array(weight_accum)
