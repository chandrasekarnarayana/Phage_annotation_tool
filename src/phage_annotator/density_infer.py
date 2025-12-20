"""Tiled inference utilities for density prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import time

import numpy as np

from phage_annotator.density_config import DensityConfig
from phage_annotator.density_model import DensityPredictor
from phage_annotator.analysis import roi_mask_for_shape


@dataclass(frozen=True)
class DensityInferOptions:
    """Options for tiled density inference."""

    tile_size: int = 256
    overlap: int = 32
    batch_tiles: int = 8
    use_roi_only: bool = True
    stitch_mode: str = "weighted"
    return_full_frame: bool = False


@dataclass(frozen=True)
class DensityResult:
    """Result bundle for density inference."""

    density_map: np.ndarray
    count_total: float
    count_roi: Optional[float]
    bbox_used: Optional[Tuple[int, int, int, int]]
    crop_offset: Tuple[int, int]
    tiles_processed: int
    runtime_ms: float
    metadata: Dict[str, Any]


def run_density_inference(
    image2d: np.ndarray,
    predictor: DensityPredictor,
    config: DensityConfig,
    roi_spec: Optional[object] = None,
    crop_rect: Optional[Tuple[float, float, float, float]] = None,
    options: Optional[DensityInferOptions] = None,
) -> DensityResult:
    """Run tiled density inference over an image with optional ROI/crop."""
    if options is None:
        options = DensityInferOptions()
    start = time.perf_counter()
    crop, offset = _apply_crop(image2d, crop_rect)
    roi_shape, roi_rect = _parse_roi_spec(roi_spec)
    roi_mask = None
    bbox = None
    infer_img = crop
    if roi_rect is not None and options.use_roi_only:
        roi_rect_crop = _shift_rect(roi_rect, offset)
        roi_mask = roi_mask_for_shape(crop.shape, roi_rect_crop, roi_shape)
        bbox = _mask_bbox(roi_mask)
        if bbox is not None:
            x0, y0, x1, y1 = bbox
            infer_img = crop[y0:y1, x0:x1]
        else:
            infer_img = crop[:0, :0]
    density_crop = np.zeros_like(crop, dtype=np.float32)
    if infer_img.size > 0:
        density_sub, tiles_processed = _infer_tiled(infer_img, predictor, config, options)
    else:
        density_sub = infer_img.astype(np.float32, copy=False)
        tiles_processed = 0
    if bbox is not None:
        x0, y0, x1, y1 = bbox
        density_crop[y0:y1, x0:x1] = density_sub
    else:
        density_crop = density_sub
    if roi_mask is not None:
        density_crop = np.where(roi_mask, density_crop, 0.0)
    density_map = density_crop
    if options.return_full_frame and (offset != (0, 0) or density_crop.shape != image2d.shape):
        full = np.zeros(image2d.shape, dtype=np.float32)
        x0, y0 = offset
        full[y0 : y0 + density_crop.shape[0], x0 : x0 + density_crop.shape[1]] = density_crop
        density_map = full
    count_total = float(density_crop.sum() * config.count_scale)
    count_roi = float(density_crop[roi_mask].sum() * config.count_scale) if roi_mask is not None else None
    runtime_ms = (time.perf_counter() - start) * 1000.0
    meta = {"roi_rect": roi_rect, "crop_rect": crop_rect}
    return DensityResult(
        density_map=density_map,
        count_total=count_total,
        count_roi=count_roi,
        bbox_used=bbox,
        crop_offset=offset,
        tiles_processed=tiles_processed,
        runtime_ms=runtime_ms,
        metadata=meta,
    )


def _infer_tiled(
    image2d: np.ndarray,
    predictor: DensityPredictor,
    config: DensityConfig,
    options: DensityInferOptions,
) -> Tuple[np.ndarray, int]:
    tile = int(options.tile_size)
    overlap = int(options.overlap)
    stride = max(1, tile - overlap)
    padded, pad = _pad_to_grid(image2d, tile, stride)
    weight = _weight_window(tile, mode=options.stitch_mode)
    accum = np.zeros_like(padded, dtype=np.float32)
    weights = np.zeros_like(padded, dtype=np.float32)
    tiles = []
    positions = []
    tiles_processed = 0
    for y in range(0, padded.shape[0] - tile + 1, stride):
        for x in range(0, padded.shape[1] - tile + 1, stride):
            tiles.append(padded[y : y + tile, x : x + tile])
            positions.append((y, x))
            if len(tiles) >= options.batch_tiles:
                tiles_processed += _flush_tiles(tiles, positions, accum, weights, predictor, config, weight)
                tiles = []
                positions = []
    if tiles:
        tiles_processed += _flush_tiles(tiles, positions, accum, weights, predictor, config, weight)
    weights = np.maximum(weights, 1e-6)
    out = accum / weights
    ypad, xpad = pad
    return out[: image2d.shape[0], : image2d.shape[1]], tiles_processed


def _flush_tiles(tiles, positions, accum, weights, predictor, config, weight) -> int:
    preds = _predict_batch(predictor, np.stack(tiles, axis=0), config)
    for (y, x), pred in zip(positions, preds):
        accum[y : y + weight.shape[0], x : x + weight.shape[1]] += pred * weight
        weights[y : y + weight.shape[0], x : x + weight.shape[1]] += weight
    return len(tiles)


def _predict_batch(predictor: DensityPredictor, tiles: np.ndarray, config: DensityConfig) -> np.ndarray:
    if hasattr(predictor, "predict_batch"):
        return predictor.predict_batch(tiles, config=config)
    outputs = []
    for tile in tiles:
        outputs.append(predictor.predict(tile, config=config))
    return np.stack(outputs, axis=0)


def _pad_to_grid(image: np.ndarray, tile: int, stride: int) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = image.shape
    n_tiles_y = int(np.ceil(max(1, (h - tile)) / stride)) + 1
    n_tiles_x = int(np.ceil(max(1, (w - tile)) / stride)) + 1
    pad_h = max(0, (n_tiles_y - 1) * stride + tile - h)
    pad_w = max(0, (n_tiles_x - 1) * stride + tile - w)
    padded = np.pad(image, ((0, pad_h), (0, pad_w)), mode="reflect")
    return padded, (pad_h, pad_w)


def _weight_window(tile: int, mode: str) -> np.ndarray:
    if mode != "weighted" or tile <= 1:
        return np.ones((tile, tile), dtype=np.float32)
    x = np.linspace(0, np.pi, tile)
    w = 0.5 - 0.5 * np.cos(x)
    w2d = np.outer(w, w).astype(np.float32)
    return w2d


def _apply_crop(image: np.ndarray, crop_rect: Optional[Tuple[float, float, float, float]]) -> Tuple[np.ndarray, Tuple[int, int]]:
    if crop_rect is None:
        return image, (0, 0)
    x, y, w, h = crop_rect
    if w <= 0 or h <= 0:
        return image, (0, 0)
    x0 = int(max(0, x))
    y0 = int(max(0, y))
    x1 = int(min(image.shape[1], x + w))
    y1 = int(min(image.shape[0], y + h))
    return image[y0:y1, x0:x1], (x0, y0)


def _parse_roi_spec(roi_spec: Optional[object]) -> Tuple[Optional[str], Optional[Tuple[float, float, float, float]]]:
    if roi_spec is None:
        return None, None
    if hasattr(roi_spec, "shape") and hasattr(roi_spec, "rect"):
        return str(roi_spec.shape), tuple(roi_spec.rect)
    if isinstance(roi_spec, dict):
        shape = roi_spec.get("shape") or roi_spec.get("type")
        rect = roi_spec.get("rect")
        if rect:
            return str(shape), tuple(rect)
    if isinstance(roi_spec, tuple) and len(roi_spec) == 2:
        shape, rect = roi_spec
        return str(shape), tuple(rect)
    return None, None


def _mask_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    return (x0, y0, x1, y1)


def _shift_rect(rect: Tuple[float, float, float, float], offset: Tuple[int, int]) -> Tuple[float, float, float, float]:
    x, y, w, h = rect
    return (x - offset[0], y - offset[1], w, h)
