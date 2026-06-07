"""Extracted method group 1 for LocalPeakSuggestionModel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter, gaussian_laplace, sobel

try:
    from skimage.feature import graycomatrix, graycoprops, structure_tensor, hessian_matrix, hessian_matrix_eigvals
except ImportError:
    # Fallback if skimage not available
    graycomatrix = None
    graycoprops = None
    structure_tensor = None
    hessian_matrix = None
    hessian_matrix_eigvals = None

from phage_annotator.core.annotation import PointSuggestion


@dataclass


class SuggestionModelBaseMixin:
    """Method group 1 extracted from LocalPeakSuggestionModel."""

    @staticmethod
    def _gaussian_fit_features(arr: np.ndarray, y: int, x: int) -> tuple[float, float, float]:
        """Estimate Gaussian-like spot features from a local patch.

        Returns
        -------
        amplitude_fit : float
            Estimated amplitude above local background.
        sigma_fit : float
            Isotropic sigma estimate from second moments.
        residual_fit : float
            RMSE between normalized patch and normalized Gaussian model.
        """
        h, w = arr.shape
        r = 3
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        patch = np.asarray(arr[y0:y1, x0:x1], dtype=np.float64)
        if patch.size == 0:
            return 0.0, 1.0, 1.0

        background = float(np.nanmedian(patch))
        signal = patch - background
        signal[~np.isfinite(signal)] = 0.0
        signal = np.maximum(signal, 0.0)
        amplitude = float(np.max(signal)) if signal.size else 0.0
        if amplitude <= 1e-8:
            return 0.0, 1.0, 1.0

        yy, xx = np.mgrid[0 : signal.shape[0], 0 : signal.shape[1]]
        cx = float(x - x0)
        cy = float(y - y0)
        total = float(np.sum(signal)) + 1e-8
        var_x = float(np.sum(signal * (xx - cx) ** 2) / total)
        var_y = float(np.sum(signal * (yy - cy) ** 2) / total)
        sigma = float(max(0.3, np.sqrt(max(1e-8, 0.5 * (var_x + var_y)))))

        gauss = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma))
        gauss = amplitude * gauss
        # Compare normalized shapes to make residual scale-robust.
        obs = signal / (amplitude + 1e-8)
        mod = gauss / (amplitude + 1e-8)
        residual = float(np.sqrt(np.mean((obs - mod) ** 2)))
        return amplitude, sigma, residual
    def _corrected_image(self, arr: np.ndarray) -> np.ndarray:
        """Simple illumination correction proxy: subtract local mean."""
        padded = np.pad(arr, ((1, 1), (1, 1)), mode="reflect")
        local_mean = (
            padded[:-2, :-2]
            + padded[:-2, 1:-1]
            + padded[:-2, 2:]
            + padded[1:-1, :-2]
            + padded[1:-1, 1:-1]
            + padded[1:-1, 2:]
            + padded[2:, :-2]
            + padded[2:, 1:-1]
            + padded[2:, 2:]
        ) / 9.0
        corrected = arr - local_mean
        corrected -= float(np.nanmin(corrected))
        return corrected
    @staticmethod
    def _point_in_roi(
        y: float, x: float, roi_shape: str, roi_rect: tuple[float, float, float, float]
    ) -> bool:
        """Check if point (y, x) is within ROI bounds.
        
        Parameters
        ----------
        y : float
            Y coordinate.
        x : float
            X coordinate.
        roi_shape : str
            ROI type: "none", "box", or "circle".
        roi_rect : tuple
            For box: (x0, y0, w, h). For circle: (cx, cy, r, _).
        
        Returns
        -------
        bool
            True if point is within ROI (or no ROI active).
        """
        if roi_shape == "none":
            return True
        
        if roi_shape == "box":
            x0, y0, w, h = roi_rect
            return x0 <= x <= (x0 + w) and y0 <= y <= (y0 + h)
        
        if roi_shape == "circle":
            cx, cy, r, _ = roi_rect
            dx = x - cx
            dy = y - cy
            return (dx * dx + dy * dy) <= (r * r)
        
        return True
    def _estimate_image_statistics(self, arr: np.ndarray) -> dict:
        """Estimate image-wide statistics for adaptive thresholding.
        
        Returns dictionary with:
        - baseline: robust background level
        - noise_std: estimated noise standard deviation
        - dynamic_range: max - min intensity
        - is_uniform: whether image appears uniform/featureless
        """
        finite = np.isfinite(arr)
        if not finite.any():
            return {
                "baseline": 0.0,
                "noise_std": 1.0,
                "dynamic_range": 0.0,
                "is_uniform": True,
                "snr_threshold": 3.0,
            }
        
        values = arr[finite]
        
        # Use robust statistics
        baseline = float(np.nanmedian(values))
        mad = float(np.nanmedian(np.abs(values - baseline)))
        noise_std = float(1.4826 * mad)  # Robust std estimate
        
        # Dynamic range
        p5 = float(np.percentile(values, 5))
        p95 = float(np.percentile(values, 95))
        dynamic_range = p95 - p5
        
        # Check if image is uniform (very low dynamic range or low variation)
        # Be more lenient - only flag as uniform if truly featureless
        is_uniform = dynamic_range < (1.5 * noise_std) or noise_std < 1e-6
        
        # Adaptive SNR threshold: More realistic for microscopy data
        # Lower thresholds allow detection of real but subtle features
        if is_uniform:
            snr_threshold = 2.5  # Stricter for uniform images
        elif dynamic_range > 20 * noise_std:
            snr_threshold = 1.2  # Very lenient for high-contrast images
        elif dynamic_range > 5 * noise_std:
            snr_threshold = 1.3  # Lenient for moderate contrast
        else:
            snr_threshold = 1.5  # Default - allows subtle but real features
        
        return {
            "baseline": baseline,
            "noise_std": max(1e-8, noise_std),
            "dynamic_range": dynamic_range,
            "is_uniform": is_uniform,
            "snr_threshold": snr_threshold,
        }
    def _check_spot_quality(self, arr: np.ndarray, y: int, x: int, radius: int = 3) -> dict:
        """Check quality metrics for a potential spot.
        
        Returns:
        - symmetry: measure of radial symmetry (0-1)
        - sharpness: measure of peak sharpness
        - circularity: how circular the spot is
        - is_valid: whether spot passes quality checks
        """
        h, w = arr.shape
        y0 = max(0, y - radius)
        y1 = min(h, y + radius + 1)
        x0 = max(0, x - radius)
        x1 = min(w, x + radius + 1)
        
        patch = arr[y0:y1, x0:x1]
        if patch.size < 9:
            return {"symmetry": 0.0, "sharpness": 0.0, "circularity": 0.0, "is_valid": False}
        
        center_val = float(arr[y, x])
        patch_mean = float(np.nanmean(patch))
        patch_std = float(np.nanstd(patch)) + 1e-8
        
        # Sharpness: how much the center stands out
        sharpness = (center_val - patch_mean) / patch_std
        
        # Check radial symmetry
        cy_local = y - y0
        cx_local = x - x0
        ph, pw = patch.shape
        
        # Compute mean values at different radii
        distances = np.zeros((ph, pw))
        for dy in range(ph):
            for dx in range(pw):
                distances[dy, dx] = np.sqrt((dy - cy_local)**2 + (dx - cx_local)**2)
        
        # Compare intensities at similar distances
        r1 = int(radius * 0.5)
        r2 = int(radius * 1.0)
        
        mask_inner = (distances <= r1) & (distances > 0)
        mask_outer = (distances > r1) & (distances <= r2)
        
        if mask_inner.sum() > 0 and mask_outer.sum() > 0:
            inner_mean = float(np.nanmean(patch[mask_inner]))
            outer_mean = float(np.nanmean(patch[mask_outer]))
            inner_std = float(np.nanstd(patch[mask_inner])) + 1e-8
            
            # Good spots have higher intensity in center/inner region
            symmetry = max(0.0, min(1.0, (inner_mean - outer_mean) / (center_val - outer_mean + 1e-8)))
            circularity = max(0.0, min(1.0, 1.0 - inner_std / (inner_mean + 1e-8)))
        else:
            symmetry = 0.5
            circularity = 0.5
        
        # Quality checks - balanced to filter noise while keeping real features
        is_valid = (
            sharpness > 1.2 and      # Center brighter than surroundings (relaxed)
            symmetry > 0.2 and       # Some radial symmetry (relaxed)
            circularity > 0.1        # Somewhat circular (relaxed)
        )
        
        return {
            "symmetry": float(symmetry),
            "sharpness": float(sharpness),
            "circularity": float(circularity),
            "is_valid": bool(is_valid),
        }
