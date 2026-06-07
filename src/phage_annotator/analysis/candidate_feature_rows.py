"""Shared local-peak candidate row assembly and scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import sobel

from phage_annotator.analysis.candidate_texture_features import (
    entropy_feature,
    radial_profile_variance,
    smooth_features,
    tensor_features,
    texture_features,
)
from phage_annotator.core.annotation import PointSuggestion


@dataclass(frozen=True)
class CandidateScanContext:
    """Immutable metadata needed while converting image peaks into suggestions."""

    threshold_quantile: float
    source_modality: str
    image_id: int
    image_name: str
    t: int
    z: int
    label: str
    roi_id: str | None
    roi_shape: str = "none"
    roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


def collect_feature_rows(model: object, arr: np.ndarray, ctx: CandidateScanContext) -> list[tuple[float, PointSuggestion]]:
    """Scan an image and return scored-input rows before final normalization."""
    finite = np.isfinite(arr)
    if not finite.any():
        return []
    values = arr[finite]
    threshold = float(np.quantile(values, ctx.threshold_quantile))
    img_stats = model._estimate_image_statistics(arr)
    if img_stats["is_uniform"] and img_stats["dynamic_range"] < 3.0:
        return []

    rows: list[tuple[float, PointSuggestion]] = []
    baseline = img_stats["baseline"]
    noise_std = img_stats["noise_std"]
    snr_threshold = img_stats["snr_threshold"]
    is_uniform = img_stats["is_uniform"]
    height, width = arr.shape
    for y in range(3, height - 3):
        for x in range(3, width - 3):
            row = _candidate_at(model, arr, ctx, y, x, threshold, baseline, noise_std, snr_threshold, is_uniform)
            if row is not None:
                rows.append(row)
    return rows


def finalize_feature_rows(model: object, rows: list[tuple[float, PointSuggestion]]) -> list[PointSuggestion]:
    """Normalize candidate rows, attach uncertainty, and return suggestions."""
    if not rows:
        return []
    rows.sort(key=lambda row: row[0], reverse=True)
    max_peak = max(1e-8, float(rows[0][0]))
    for peak, suggestion in rows:
        comp = suggestion.score_components
        peak_norm = float(peak / max_peak)
        snr_norm = float(max(0.0, min(1.0, comp["snr"] / 5.0)))
        contrast_norm = float(max(0.0, min(1.0, abs(comp["local_contrast"]) / (abs(max_peak) + 1e-8))))
        residual_penalty = float(max(0.0, min(1.0, 1.0 - comp.get("residual_fit", 1.0))))
        symmetry_score = float(comp.get("symmetry", 0.5))
        sharpness_norm = float(max(0.0, min(1.0, comp.get("sharpness", 2.0) / 5.0)))
        circularity_score = float(comp.get("circularity", 0.5))

        # Balance raw intensity against SNR and shape quality to reduce false positives.
        base_score = (
            0.20 * peak_norm + 0.30 * snr_norm + 0.15 * contrast_norm
            + 0.10 * residual_penalty + 0.12 * symmetry_score
            + 0.08 * sharpness_norm + 0.05 * circularity_score
        )
        if comp["snr"] > comp.get("image_snr_threshold", 2.0) and symmetry_score > 0.5 and residual_penalty > 0.5:
            base_score = min(1.0, base_score * 1.2)
        if symmetry_score < 0.2 or sharpness_norm < 0.15:
            base_score *= 0.8
        suggestion.score = float(base_score)
        uncertainty_score, uncertainty_reason = model._uncertainty_from_components(comp)
        suggestion.uncertainty_score = float(uncertainty_score)
        suggestion.uncertainty_reason = str(uncertainty_reason)
        suggestion.meta["uncertainty_score"] = float(uncertainty_score)
        suggestion.meta["uncertainty_reason"] = str(uncertainty_reason)
    return [row[1] for row in rows]


def _candidate_at(
    model: object,
    arr: np.ndarray,
    ctx: CandidateScanContext,
    y: int,
    x: int,
    threshold: float,
    baseline: float,
    noise_std: float,
    snr_threshold: float,
    is_uniform: bool,
) -> tuple[float, PointSuggestion] | None:
    """Build one candidate row when a pixel passes all local checks."""
    if not model._point_in_roi(float(y), float(x), ctx.roi_shape, ctx.roi_rect):
        return None
    center = float(arr[y, x])
    if not np.isfinite(center) or center < threshold:
        return None
    window = arr[y - 1 : y + 2, x - 1 : x + 2]
    if center < float(np.nanmax(window)):
        return None
    snr = (center - baseline) / noise_std
    if snr < (snr_threshold if is_uniform else 1.0):
        return None
    amplitude_fit, sigma_fit, residual_fit = model._gaussian_fit_features(arr, y, x)
    if residual_fit > 0.9 or sigma_fit < 0.1 or sigma_fit > 30.0:
        return None

    quality = model._check_spot_quality(arr, y, x, radius=3)
    patch = _patch_for(arr, y, x, center)
    local_mean = float(np.nanmean(window))
    components = _score_components(
        arr,
        patch,
        y,
        x,
        center,
        local_mean,
        float(np.nanstd(window)) + 1e-8,
        snr,
        quality,
        amplitude_fit,
        sigma_fit,
        residual_fit,
        snr_threshold,
        noise_std,
    )
    suggestion = PointSuggestion(
        image_id=int(ctx.image_id),
        image_name=str(ctx.image_name),
        t=int(ctx.t),
        z=int(ctx.z),
        y=float(y),
        x=float(x),
        score=0.0,
        label=str(ctx.label),
        source_model=model.model_name,
        source_modality=ctx.source_modality,
        supporting_modalities=[],
        cross_modality_consistency_score=1.0,
        control_contradiction_score=0.0,
        scale_sigma=float(model.scale_sigma),
        psf_radius=float(model.min_distance_px),
        roi_id=ctx.roi_id,
        uncertainty_score=None,
        uncertainty_reason="",
        density_context={},
        score_components=components,
        meta={"raw_peak": float(center), "image_aware": True, "is_uniform_image": bool(is_uniform)},
    )
    return center, suggestion


def _patch_for(arr: np.ndarray, y: int, x: int, center: float) -> np.ndarray:
    """Return the local feature patch around a candidate pixel."""
    height, width = arr.shape
    y0, y1 = max(0, y - 3), min(height, y + 4)
    x0, x1 = max(0, x - 3), min(width, x + 4)
    patch = arr[y0:y1, x0:x1]
    return patch if patch.size else np.array([[center]])


def _score_components(
    arr: np.ndarray,
    patch: np.ndarray,
    y: int,
    x: int,
    center: float,
    local_mean: float,
    local_std: float,
    snr: float,
    quality: dict[str, float],
    amplitude_fit: float,
    sigma_fit: float,
    residual_fit: float,
    snr_threshold: float,
    noise_std: float,
) -> dict[str, float]:
    """Compute the feature dictionary stored with each point suggestion."""
    height, width = arr.shape
    edge = _edge_features(arr, patch, y, x)
    tensor = tensor_features(patch)
    texture = texture_features(patch)
    smooth = smooth_features(patch, center)
    entropy = entropy_feature(patch)
    radial = radial_profile_variance(patch)
    laplace = float(arr[y - 1, x]) + float(arr[y + 1, x]) + float(arr[y, x - 1]) + float(arr[y, x + 1]) - 4.0 * center
    return {
        "peak": float(center), "snr": float(snr), "local_contrast": float(center - local_mean),
        "local_std": float(local_std), "local_background": float(local_mean), "log_response": float(-laplace),
        "patch_mean": float(np.mean(patch)), "patch_median": float(np.median(patch)),
        "patch_variance": float(np.var(patch)), "patch_min": float(np.min(patch)), "patch_max": float(np.max(patch)),
        "amplitude_fit": float(amplitude_fit), "sigma_fit": float(sigma_fit), "residual_fit": float(residual_fit),
        "symmetry": float(quality["symmetry"]), "sharpness": float(quality["sharpness"]),
        "circularity": float(quality["circularity"]), "image_snr_threshold": float(snr_threshold),
        "noise_std": float(noise_std), "gradient_magnitude": float(edge["gradient_magnitude"]),
        "sobel_x": float(edge["sobel_x"]), "sobel_y": float(edge["sobel_y"]),
        "sobel_magnitude": float(edge["sobel_magnitude"]), "gaussian_grad_magnitude": float(smooth["gaussian_grad_magnitude"]),
        "dist_to_border": float(min(x, y, width - x - 1, height - y - 1)),
        "hessian_eig1": float(tensor["hessian_eig1"]), "hessian_eig2": float(tensor["hessian_eig2"]),
        "struct_eig1": float(tensor["struct_eig1"]), "struct_eig2": float(tensor["struct_eig2"]),
        "haralick_contrast": float(texture["haralick_contrast"]), "haralick_homogeneity": float(texture["haralick_homogeneity"]),
        "haralick_correlation": float(texture["haralick_correlation"]), "haralick_energy": float(texture["haralick_energy"]),
        "gaussian_blur": float(smooth["gaussian_blur"]), "dog": float(smooth["dog"]),
        "log": float(smooth["log"]), "radial_profile_variance": float(radial),
        "local_entropy": float(entropy), "cross_modality_consistency_score": 1.0,
        "control_contradiction_score": 0.0,
    }


def _edge_features(arr: np.ndarray, patch: np.ndarray, y: int, x: int) -> dict[str, float]:
    """Calculate first-order edge and gradient features."""
    height, width = arr.shape
    gradient_magnitude = 0.0
    if 0 < y < height - 1 and 0 < x < width - 1:
        grad_y = float(arr[y + 1, x]) - float(arr[y - 1, x])
        grad_x = float(arr[y, x + 1]) - float(arr[y, x - 1])
        gradient_magnitude = float(np.sqrt(grad_y**2 + grad_x**2))
    try:
        if patch.shape[0] >= 3 and patch.shape[1] >= 3:
            cy, cx = patch.shape[0] // 2, patch.shape[1] // 2
            sobel_x = float(np.abs(sobel(patch, axis=1)[cy, cx]))
            sobel_y = float(np.abs(sobel(patch, axis=0)[cy, cx]))
            return {"gradient_magnitude": gradient_magnitude, "sobel_x": sobel_x, "sobel_y": sobel_y, "sobel_magnitude": float(np.sqrt(sobel_x**2 + sobel_y**2))}
    except Exception:
        pass
    return {"gradient_magnitude": gradient_magnitude, "sobel_x": 0.0, "sobel_y": 0.0, "sobel_magnitude": 0.0}
