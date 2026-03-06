"""Model-in-the-loop point suggestion adapters."""

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


class SuggestionModel(Protocol):
    """Interface for proposal models used by assisted annotation."""

    model_name: str

    def predict(
        self,
        image_slice: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
    ) -> List[PointSuggestion]:
        """Generate candidate point suggestions for one 2D slice."""


@dataclass
class LocalPeakSuggestionModel:
    """Fast baseline model using local maxima as candidate points.
    
    This is the first-level assist for coarse detection. Features extracted here
    can be used by downstream ML models (e.g., LightGBM) for fine-tuning.
    """

    min_distance_px: int = 6
    max_points: int | None = None  # None = use quality/spatial filtering only
    threshold_quantile: float = 0.995
    anisotropic_radius_x: float | None = None
    anisotropic_radius_y: float | None = None
    scale_sigma: float = 1.0
    model_name: str = "local_peaks"
    
    # Spatial filtering parameters (tunable per experiment)
    enable_spatial_filtering: bool = True
    spatial_density_penalty: float = 0.6  # Penalty multiplier for dense clusters (0.6 = 40% penalty)
    spatial_isolation_penalty: float = 0.9  # Penalty for isolated spots (0.9 = 10% penalty)
    spatial_typical_bonus: float = 1.15  # Bonus for well-spaced spots (1.15 = 15% bonus)
    spatial_nn_isolation_factor: float = 2.5  # Factor above median NN to consider isolated
    spatial_density_cluster_factor: float = 3.0  # Factor above expected density for clustering
    
    # Adaptive thresholding parameters
    score_drop_percentile: float = 0.10  # Percentile of score drops to consider significant (0.10 = top 10%)
    min_relative_score_drop: float = 0.03  # Minimum relative score drop to consider (3%)
    expected_count_hint: int | None = 100  # Optional: expected spot count for guidance (None = purely adaptive, 100 = typical phage)
    expected_count_tolerance: float = 0.5  # Tolerance around hint (50% = ±50%)
    
    # Performance
    nms_intermediate_limit: int = 300  # Intermediate limit for NMS performance (reduced from 1000)

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

    def _collect_candidates(
        self,
        arr: np.ndarray,
        *,
        threshold_quantile: float,
        source_modality: str,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        roi_id: str | None,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> list[PointSuggestion]:
        finite = np.isfinite(arr)
        if not finite.any():
            return []
        values = arr[finite]
        threshold = float(np.quantile(values, threshold_quantile))
        
        # Get image-aware statistics
        img_stats = self._estimate_image_statistics(arr)
        baseline = img_stats["baseline"]
        noise_std = img_stats["noise_std"]
        snr_threshold = img_stats["snr_threshold"]
        is_uniform = img_stats["is_uniform"]
        
        # If image is too uniform, be very strict or return no candidates
        if is_uniform and img_stats["dynamic_range"] < 3.0:
            # Image appears to be pure noise or nearly flat, skip detection
            return []
        h, w = arr.shape
        rows: list[tuple[float, PointSuggestion]] = []
        
        for y in range(3, h - 3):  # Increased margin for quality checks
            for x in range(3, w - 3):
                # Skip points outside ROI
                if not self._point_in_roi(float(y), float(x), roi_shape, roi_rect):
                    continue
                
                center = float(arr[y, x])
                if not np.isfinite(center) or center < threshold:
                    continue
                    
                # Local maxima check
                window = arr[y - 1 : y + 2, x - 1 : x + 2]
                if center < float(np.nanmax(window)):
                    continue
                
                # Calculate local statistics
                local_mean = float(np.nanmean(window))
                local_std = float(np.nanstd(window)) + 1e-8
                local_contrast = center - local_mean
                
                # Calculate SNR (signal-to-noise ratio)
                snr = (center - baseline) / noise_std
                
                # **Image-aware filtering: Use SNR for scoring, not hard filtering**
                # Only reject candidates with extremely low SNR (likely pure noise)
                # More aggressive filtering for images detected as uniform
                min_snr = snr_threshold if is_uniform else 1.0
                if snr < min_snr:
                    continue
                
                # **Quality check: Assess spot shape and symmetry**
                # Use for scoring, not hard filtering (allows real but imperfect spots)
                quality = self._check_spot_quality(arr, y, x, radius=3)
                
                # Define local window bounds for additional features
                r = 3  # radius for local operations
                r_y0, r_y1 = max(0, y - r), min(h, y + r + 1)
                r_x0, r_x1 = max(0, x - r), min(w, x + r + 1)
                
                # Gaussian fitting
                peak_score = center
                amplitude_fit, sigma_fit, residual_fit = self._gaussian_fit_features(arr, y, x)
                
                # **Very lenient Gaussian fit requirement - only reject obviously bad fits**
                # This catches edge artifacts and extreme outliers
                if residual_fit > 0.9 or sigma_fit < 0.1 or sigma_fit > 30.0:
                    continue
                
                # **Comprehensive ML Features**
                # Extract rich feature set for interactive learning
                
                # Get local patch for feature extraction
                if r_y0 >= 0 and r_y1 <= h and r_x0 >= 0 and r_x1 <= w:
                    patch = arr[r_y0:r_y1, r_x0:r_x1]
                    patch_flat = patch.flatten()
                else:
                    patch = np.array([[center]])
                    patch_flat = np.array([center])
                
                # === Basic Statistics ===
                patch_mean = float(np.mean(patch))
                patch_median = float(np.median(patch))
                patch_variance = float(np.var(patch))
                patch_min = float(np.min(patch))
                patch_max = float(np.max(patch))
                
                # === Gradient & Edge Features ===
                # Simple gradient magnitude (already computed)
                if y > 0 and y < h - 1 and x > 0 and x < w - 1:
                    grad_y = float(arr[y + 1, x]) - float(arr[y - 1, x])
                    grad_x = float(arr[y, x + 1]) - float(arr[y, x - 1])
                    gradient_magnitude = np.sqrt(grad_y**2 + grad_x**2)
                else:
                    gradient_magnitude = 0.0
                
                # Sobel filter (x and y)
                try:
                    if patch.shape[0] >= 3 and patch.shape[1] >= 3:
                        sobel_x = float(np.abs(sobel(patch, axis=1)[patch.shape[0]//2, patch.shape[1]//2]))
                        sobel_y = float(np.abs(sobel(patch, axis=0)[patch.shape[0]//2, patch.shape[1]//2]))
                        sobel_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
                    else:
                        sobel_x = sobel_y = sobel_magnitude = 0.0
                except Exception:
                    sobel_x = sobel_y = sobel_magnitude = 0.0
                
                # === Hessian Features (blob detection) ===
                try:
                    if hessian_matrix_eigvals is not None and patch.shape[0] >= 5 and patch.shape[1] >= 5:
                        # Compute Hessian eigenvalues for blob detection
                        H_elems = hessian_matrix(patch.astype(float), sigma=1.0, order='rc')
                        eigvals = hessian_matrix_eigvals(H_elems)
                        hessian_eig1 = float(eigvals[0][patch.shape[0]//2, patch.shape[1]//2])
                        hessian_eig2 = float(eigvals[1][patch.shape[0]//2, patch.shape[1]//2])
                    else:
                        hessian_eig1 = hessian_eig2 = 0.0
                except Exception:
                    hessian_eig1 = hessian_eig2 = 0.0
                
                # === Structure Tensor (orientation/anisotropy) ===
                try:
                    if structure_tensor is not None and patch.shape[0] >= 5 and patch.shape[1] >= 5:
                        A_elems = structure_tensor(patch.astype(float), sigma=1.0)
                        # Get eigenvalues of structure tensor
                        Axx, Axy, Ayy = A_elems
                        cy, cx = patch.shape[0]//2, patch.shape[1]//2
                        # Compute eigenvalues manually
                        a, b, c = Axx[cy, cx], Axy[cy, cx], Ayy[cy, cx]
                        trace = a + c
                        det = a * c - b * b
                        discriminant = trace**2 - 4*det
                        if discriminant >= 0:
                            struct_eig1 = float((trace + np.sqrt(discriminant)) / 2)
                            struct_eig2 = float((trace - np.sqrt(discriminant)) / 2)
                        else:
                            struct_eig1 = struct_eig2 = float(trace / 2)
                    else:
                        struct_eig1 = struct_eig2 = 0.0
                except Exception:
                    struct_eig1 = struct_eig2 = 0.0
                
                # === Texture Features (GLCM Haralick) ===
                try:
                    if graycomatrix is not None and patch.shape[0] >= 5 and patch.shape[1] >= 5:
                        # Normalize patch to 0-255 for GLCM
                        patch_norm = ((patch - patch.min()) / (patch.max() - patch.min() + 1e-10) * 255).astype(np.uint8)
                        # Compute GLCM
                        glcm = graycomatrix(patch_norm, distances=[1], angles=[0], levels=256, symmetric=True, normed=True)
                        # Extract Haralick features
                        haralick_contrast = float(graycoprops(glcm, 'contrast')[0, 0])
                        haralick_homogeneity = float(graycoprops(glcm, 'homogeneity')[0, 0])
                        haralick_correlation = float(graycoprops(glcm, 'correlation')[0, 0])
                        haralick_energy = float(graycoprops(glcm, 'energy')[0, 0])
                    else:
                        haralick_contrast = haralick_homogeneity = haralick_correlation = haralick_energy = 0.0
                except Exception:
                    haralick_contrast = haralick_homogeneity = haralick_correlation = haralick_energy = 0.0
                
                # === Smoothing & Multi-scale Features ===
                try:
                    if patch.shape[0] >= 5 and patch.shape[1] >= 5:
                        # Gaussian blur at center
                        patch_blur = gaussian_filter(patch.astype(float), sigma=1.0)
                        gaussian_blur_val = float(patch_blur[patch.shape[0]//2, patch.shape[1]//2])
                        
                        # Difference of Gaussian (DoG) - blob detector
                        patch_blur_small = gaussian_filter(patch.astype(float), sigma=0.5)
                        patch_blur_large = gaussian_filter(patch.astype(float), sigma=2.0)
                        dog_val = float(patch_blur_small[patch.shape[0]//2, patch.shape[1]//2] - 
                                       patch_blur_large[patch.shape[0]//2, patch.shape[1]//2])
                        
                        # Gaussian derivatives (edge detection)
                        # First derivatives
                        gaussian_grad_y = float(ndi.gaussian_filter(patch.astype(float), sigma=1.0, order=(1, 0))[patch.shape[0]//2, patch.shape[1]//2])
                        gaussian_grad_x = float(ndi.gaussian_filter(patch.astype(float), sigma=1.0, order=(0, 1))[patch.shape[0]//2, patch.shape[1]//2])
                        gaussian_grad_magnitude = np.sqrt(gaussian_grad_x**2 + gaussian_grad_y**2)
                        
                        # Second derivatives (Laplacian of Gaussian)
                        log_val = float(gaussian_laplace(patch.astype(float), sigma=1.0)[patch.shape[0]//2, patch.shape[1]//2])
                    else:
                        gaussian_blur_val = float(center)
                        dog_val = 0.0
                        gaussian_grad_x = gaussian_grad_y = gaussian_grad_magnitude = 0.0
                        log_val = 0.0
                except Exception:
                    gaussian_blur_val = float(center)
                    dog_val = 0.0
                    gaussian_grad_x = gaussian_grad_y = gaussian_grad_magnitude = 0.0
                    log_val = 0.0
                
                # Distance to image borders (detect edge artifacts)
                dist_to_border = float(min(x, y, w - x - 1, h - y - 1))
                
                # Local entropy (texture complexity measure)
                try:
                    if len(patch_flat) > 0:
                        # Compute histogram-based entropy
                        hist, _ = np.histogram(patch_flat, bins=16, range=(patch_flat.min(), patch_flat.max() + 1e-8))
                        hist_norm = hist / (hist.sum() + 1e-10)
                        local_entropy = -np.sum(hist_norm * np.log2(hist_norm + 1e-10))
                    else:
                        local_entropy = 0.0
                except Exception:
                    local_entropy = 0.0
                
                # Radial profile variance (spot quality)
                try:
                    if patch.shape[0] >= 3 and patch.shape[1] >= 3:
                        py, px = patch.shape
                        cy, cx = py // 2, px // 2
                        yy, xx = np.ogrid[:py, :px]
                        radii = np.sqrt((yy - cy)**2 + (xx - cx)**2)
                        radial_bins = np.linspace(0, np.max(radii), 5)
                        radial_variances = []
                        for i in range(len(radial_bins) - 1):
                            mask = (radii >= radial_bins[i]) & (radii < radial_bins[i + 1])
                            if np.sum(mask) > 0:
                                radial_variances.append(np.var(patch[mask]))
                        radial_profile_variance = np.mean(radial_variances) if radial_variances else 0.0
                    else:
                        radial_profile_variance = 0.0
                except Exception:
                    radial_profile_variance = 0.0
                
                # Laplacian (for edge/blob detection)
                laplace = (
                    float(arr[y - 1, x]) + float(arr[y + 1, x]) + float(arr[y, x - 1]) + float(arr[y, x + 1]) - 4.0 * center
                )
                rows.append(
                    (
                        peak_score,
                        PointSuggestion(
                            image_id=int(image_id),
                            image_name=str(image_name),
                            t=int(t),
                            z=int(z),
                            y=float(y),
                            x=float(x),
                            score=0.0,
                            label=str(label),
                            source_model=self.model_name,
                            source_modality=source_modality,
                            scale_sigma=float(self.scale_sigma),
                            psf_radius=float(self.min_distance_px),
                            roi_id=roi_id,
                            score_components={
                                # **Core intensity features (6)**
                                "peak": float(peak_score),
                                "snr": float(snr),
                                "local_contrast": float(local_contrast),
                                "local_std": float(local_std),
                                "local_background": float(local_mean),
                                "log_response": float(-laplace),
                                
                                # **Basic statistics (5)**
                                "patch_mean": patch_mean,
                                "patch_median": patch_median,
                                "patch_variance": patch_variance,
                                "patch_min": patch_min,
                                "patch_max": patch_max,
                                
                                # **Gaussian fit features (3)**
                                "amplitude_fit": float(amplitude_fit),
                                "sigma_fit": float(sigma_fit),
                                "residual_fit": float(residual_fit),
                                
                                # **Image-aware quality metrics (5)**
                                "symmetry": quality["symmetry"],
                                "sharpness": quality["sharpness"],
                                "circularity": quality["circularity"],
                                "image_snr_threshold": float(snr_threshold),
                                "noise_std": float(noise_std),
                                
                                # **Gradient & Edge features (6)**
                                "gradient_magnitude": float(gradient_magnitude),
                                "sobel_x": sobel_x,
                                "sobel_y": sobel_y,
                                "sobel_magnitude": sobel_magnitude,
                                "gaussian_grad_magnitude": gaussian_grad_magnitude,
                                "dist_to_border": float(dist_to_border),
                                
                                # **Hessian features (2 - blob detection)**
                                "hessian_eig1": hessian_eig1,
                                "hessian_eig2": hessian_eig2,
                                
                                # **Structure tensor features (2 - orientation)**
                                "struct_eig1": struct_eig1,
                                "struct_eig2": struct_eig2,
                                
                                # **Texture features GLCM Haralick (4)**
                                "haralick_contrast": haralick_contrast,
                                "haralick_homogeneity": haralick_homogeneity,
                                "haralick_correlation": haralick_correlation,
                                "haralick_energy": haralick_energy,
                                
                                # **Multi-scale smoothing (4)**
                                "gaussian_blur": gaussian_blur_val,
                                "dog": dog_val,  # Difference of Gaussian
                                "log": log_val,  # Laplacian of Gaussian
                                "radial_profile_variance": float(radial_profile_variance),
                                
                                # **Entropy (1)**
                                "local_entropy": float(local_entropy),
                            },
                            meta={
                                "raw_peak": float(center),
                                "image_aware": True,
                                "is_uniform_image": bool(is_uniform),
                            },
                        ),
                    )
                )
        if not rows:
            return []
        rows.sort(key=lambda r: r[0], reverse=True)
        max_peak = max(1e-8, float(rows[0][0]))
        
        # **Image-aware scoring with quality metrics**
        for peak, suggestion in rows:
            comp = suggestion.score_components
            peak_norm = float(peak / max_peak)
            snr_norm = float(max(0.0, min(1.0, comp["snr"] / 5.0)))  # Adjusted for subtle features
            contrast_norm = float(max(0.0, min(1.0, abs(comp["local_contrast"]) / (abs(max_peak) + 1e-8))))
            residual_penalty = float(max(0.0, min(1.0, 1.0 - comp.get("residual_fit", 1.0))))
            
            # **Quality-based components**
            symmetry_score = float(comp.get("symmetry", 0.5))
            sharpness_norm = float(max(0.0, min(1.0, comp.get("sharpness", 2.0) / 5.0)))
            circularity_score = float(comp.get("circularity", 0.5))
            
            # **Weighted scoring that balances detection and quality**
            # Emphasize SNR and quality over raw peak intensity
            base_score = (
                0.20 * peak_norm +           # Raw peak intensity
                0.30 * snr_norm +            # Signal-to-noise (key for real vs noise)
                0.15 * contrast_norm +       # Local contrast
                0.10 * residual_penalty +    # Gaussian fit quality
                0.12 * symmetry_score +      # Radial symmetry (important!)
                0.08 * sharpness_norm +      # Peak sharpness
                0.05 * circularity_score     # Circularity
            )
            
            # **Bonus for high-quality spots that pass stricter criteria**
            snr_thresh = comp.get("image_snr_threshold", 2.0)
            if comp["snr"] > snr_thresh and symmetry_score > 0.5 and residual_penalty > 0.5:
                base_score = min(1.0, base_score * 1.2)  # 20% bonus for high-quality
            
            # **Penalty for poor quality (reduces false positives)**
            if symmetry_score < 0.2 or sharpness_norm < 0.15:
                base_score *= 0.8  # 20% penalty for low quality
            
            suggestion.score = float(base_score)
        
        return [row[1] for row in rows]

    def _spatial_filtering(self, candidates: list[PointSuggestion], arr_shape: tuple[int, int]) -> list[PointSuggestion]:
        """Filter candidates using spatial statistics to reduce false positives.
        
        This is experiment-agnostic and adapts to image properties:
        - Nearest neighbor distance analysis (1st, 2nd, 3rd neighbors)
        - Local density checks
        - Spatial uniformity assessment
        - Adaptive score-based thresholding (NO hardcoded spot count assumptions)
        
        Features added to candidates for downstream ML:
        - nn_dist_1, nn_dist_2, nn_dist_3: Distances to nearest 3 neighbors
        - local_density: Number of neighbors within search radius
        - spatial_quality: Quality score based on spatial distribution
        """
        if not candidates or not self.enable_spatial_filtering:
            return candidates
        
        n = len(candidates)
        if n < 3:
            return candidates  # Too few to apply spatial stats
        
        # Extract coordinates and scores
        coords = np.array([[float(c.x), float(c.y)] for c in candidates])
        scores = np.array([float(c.score) for c in candidates])
        
        # 1. Calculate multi-neighbor distances (1st, 2nd, 3rd nearest neighbors)
        nn_distances_1 = np.full(n, np.inf)
        nn_distances_2 = np.full(n, np.inf)
        nn_distances_3 = np.full(n, np.inf)
        
        for i in range(n):
            dists = np.sqrt(np.sum((coords - coords[i:i+1]) ** 2, axis=1))
            dists[i] = np.inf  # Exclude self
            sorted_dists = np.sort(dists)
            nn_distances_1[i] = sorted_dists[0] if len(sorted_dists) > 0 else np.inf
            nn_distances_2[i] = sorted_dists[1] if len(sorted_dists) > 1 else np.inf
            nn_distances_3[i] = sorted_dists[2] if len(sorted_dists) > 2 else np.inf
        
        # 2. Identify expected spot spacing from median 1st NN distance
        median_nn = np.median(nn_distances_1[np.isfinite(nn_distances_1)])
        
        # 3. Calculate local density for each point (neighbors within 3x median distance)
        search_radius = max(median_nn * 3.0, float(self.min_distance_px) * 2.0)
        local_density = np.zeros(n)
        for i in range(n):
            dists = np.sqrt(np.sum((coords - coords[i:i+1]) ** 2, axis=1))
            local_density[i] = np.sum(dists < search_radius) - 1  # Exclude self
        
        # 4. Calculate spatial quality score for each point (tunable parameters)
        # Expected density based on image area and spot count
        h, w = arr_shape
        area = h * w
        expected_density = n / area * (np.pi * search_radius ** 2)
        
        spatial_quality = np.ones(n)
        
        # Penalize overly dense regions (likely artifacts/noise clusters)
        overdense_mask = local_density > expected_density * self.spatial_density_cluster_factor
        spatial_quality[overdense_mask] *= self.spatial_density_penalty
        
        # Penalty for isolated points (might be noise)
        isolated_mask = nn_distances_1 > median_nn * self.spatial_nn_isolation_factor
        spatial_quality[isolated_mask] *= self.spatial_isolation_penalty
        
        # Bonus for points with typical spacing (within 70-150% of median)
        typical_mask = (nn_distances_1 >= median_nn * 0.7) & (nn_distances_1 <= median_nn * 1.5)
        spatial_quality[typical_mask] *= self.spatial_typical_bonus
        
        # 5. Update scores with spatial quality and add features for ML
        adjusted_scores = scores * spatial_quality
        
        # Add spatial features to candidates for downstream ML models
        for i, candidate in enumerate(candidates):
            candidate.score_components['nn_dist_1'] = float(nn_distances_1[i])
            candidate.score_components['nn_dist_2'] = float(nn_distances_2[i])
            candidate.score_components['nn_dist_3'] = float(nn_distances_3[i])
            candidate.score_components['local_density'] = float(local_density[i])
            candidate.score_components['spatial_quality'] = float(spatial_quality[i])
            candidate.score_components['expected_density'] = float(expected_density)
            candidate.score_components['median_nn'] = float(median_nn)
        
        # 6. TRULY adaptive thresholding with optional expected count hint
        # Strategy: Find natural break in score distribution, optionally guided by expected count
        sorted_idx = np.argsort(adjusted_scores)[::-1]
        sorted_scores = adjusted_scores[sorted_idx]
        
        if len(sorted_scores) > 20:
            # Calculate relative score drops (gradient)
            diffs = np.abs(np.diff(sorted_scores))
            relative_drops = diffs / (sorted_scores[:-1] + 1e-10)
            
            # Find significant drops (top percentile of all drops)
            drop_threshold = np.percentile(relative_drops, (1.0 - self.score_drop_percentile) * 100)
            significant_drops = np.where(relative_drops > max(drop_threshold, self.min_relative_score_drop))[0]
            
            # If expected_count_hint provided, search near that range first
            if self.expected_count_hint is not None and self.expected_count_hint > 0:
                hint_min = int(self.expected_count_hint * (1.0 - self.expected_count_tolerance))
                hint_max = int(self.expected_count_hint * (1.0 + self.expected_count_tolerance))
                
                # Find drops within the hinted range
                drops_in_range = significant_drops[(significant_drops >= hint_min) & (significant_drops <= hint_max)]
                
                if len(drops_in_range) > 0:
                    # Use first significant drop within expected range
                    cutoff_idx = drops_in_range[0]
                elif len(significant_drops) > 0:
                    # No drop in range: use closest drop to hint
                    closest_drop = significant_drops[np.argmin(np.abs(significant_drops - self.expected_count_hint))]
                    cutoff_idx = closest_drop
                else:
                    # No drops at all: use hint directly
                    cutoff_idx = min(self.expected_count_hint, len(sorted_scores) - 1)
                
                cutoff_idx = min(cutoff_idx + 2, len(sorted_scores) - 1)
                adaptive_threshold = sorted_scores[cutoff_idx]
                
            elif len(significant_drops) > 0:
                # No hint: use FIRST significant drop (purely adaptive)
                cutoff_idx = significant_drops[0]
                cutoff_idx = min(cutoff_idx + 2, len(sorted_scores) - 1)
                adaptive_threshold = sorted_scores[cutoff_idx]
            else:
                # No clear break and no hint: use robust statistical filtering
                score_median = np.median(sorted_scores)
                mad = np.median(np.abs(sorted_scores - score_median))
                adaptive_threshold = max(
                    score_median - 2.0 * 1.4826 * mad,  # Robust outlier detection
                    np.percentile(sorted_scores, 40)  # Or keep top 60%
                )
        else:
            # Few candidates: keep top 70%
            adaptive_threshold = np.percentile(sorted_scores, 30)
        
        # 7. Filter: keep high-quality spatial points
        filtered = []
        for i, candidate in enumerate(candidates):
            if adjusted_scores[i] >= adaptive_threshold:
                # Update score with spatial quality
                candidate.score = float(adjusted_scores[i])
                filtered.append(candidate)
        
        return filtered

    def _nms(self, candidates: list[PointSuggestion]) -> list[PointSuggestion]:
        """Non-maximum suppression with intermediate limit for performance."""
        radius_x = float(self.anisotropic_radius_x or self.min_distance_px)
        radius_y = float(self.anisotropic_radius_y or self.min_distance_px)
        if radius_x <= 0 or radius_y <= 0:
            return list(candidates)
        picked: list[PointSuggestion] = []
        for suggestion in sorted(candidates, key=lambda s: float(s.score), reverse=True):
            keep = True
            for prev in picked:
                dx = (float(prev.x) - float(suggestion.x)) / radius_x
                dy = (float(prev.y) - float(suggestion.y)) / radius_y
                if dx * dx + dy * dy < 1.0:
                    keep = False
                    break
            if keep:
                picked.append(suggestion)
            # Intermediate limit for performance (spatial filtering will refine further)
            if len(picked) >= self.nms_intermediate_limit:
                break
        return picked

    @staticmethod
    def _consensus(raw: list[PointSuggestion], corrected: list[PointSuggestion], radius: float) -> list[PointSuggestion]:
        if not raw or not corrected:
            return []
        out: list[PointSuggestion] = []
        radius2 = float(max(1.0, radius) ** 2)
        for a in raw:
            for b in corrected:
                dx = float(a.x) - float(b.x)
                dy = float(a.y) - float(b.y)
                if dx * dx + dy * dy > radius2:
                    continue
                merged = PointSuggestion(
                    image_id=a.image_id,
                    image_name=a.image_name,
                    t=a.t,
                    z=a.z,
                    y=float((a.y + b.y) / 2.0),
                    x=float((a.x + b.x) / 2.0),
                    score=float((a.score + b.score) / 2.0),
                    label=a.label,
                    source_model=a.source_model,
                    source_modality="consensus",
                    scale_sigma=a.scale_sigma,
                    psf_radius=a.psf_radius,
                    roi_id=a.roi_id,
                    score_components={
                        "raw_score": float(a.score),
                        "corrected_score": float(b.score),
                    },
                    meta={"consensus": True},
                )
                out.append(merged)
                break
        return out

    def _extract_stack_features(
        self,
        stack: np.ndarray,
        y: float,
        x: float,
    ) -> tuple[float, float, float, float]:
        """Extract enhanced features using full stack at a given (y, x) location.
        
        Computes SNR and other statistics by looking at intensity across all frames
        at a single xy position, providing more robust feature estimation.
        
        Parameters
        ----------
        stack : np.ndarray
            3D array of shape (T, H, W) or (Z, H, W)
        y : float
            Y coordinate
        x : float
            X coordinate
            
        Returns
        -------
        amplitude : float
            Mean peak value across frames
        snr : float
            Signal-to-noise ratio from stack statistics
        stack_contrast : float
            Contrast relative to background across stack
        stack_std : float
            Standard deviation of peak values across frames
        """
        y_int, x_int = int(round(y)), int(round(x))
        h, w = stack.shape[1], stack.shape[2]
        
        # Clamp to valid range
        if y_int < 0 or y_int >= h or x_int < 0 or x_int >= w:
            return 0.0, 0.0, 0.0, 0.0
        
        # Extract values at (y, x) across all frames
        values = stack[:, y_int, x_int].astype(np.float64)
        
        if not np.isfinite(values).any():
            return 0.0, 0.0, 0.0, 0.0
        
        # Compute statistics
        peak_mean = float(np.nanmean(values))
        peak_std = float(np.nanstd(values))
        
        # Estimate background from local neighborhood median (across stack mean)
        stack_mean = np.nanmean(stack.astype(np.float64), axis=0)
        r = 5
        y0, y1 = max(0, y_int - r), min(h, y_int + r + 1)
        x0, x1 = max(0, x_int - r), min(w, x_int + r + 1)
        
        patch = stack_mean[y0:y1, x0:x1]
        if patch.size > 0:
            baseline = float(np.nanmedian(patch))
        else:
            baseline = float(np.nanmedian(stack_mean))
        
        baseline_std = float(np.nanstd(stack_mean[stack_mean != baseline]))
        if baseline_std < 1e-8:
            baseline_std = 1e-8
        
        # SNR: (signal - baseline) / noise
        snr = (peak_mean - baseline) / baseline_std if baseline_std > 0 else 0.0
        snr = float(max(0.0, snr))
        
        # Contrast: relative height above background
        contrast = (peak_mean - baseline) / (abs(baseline) + 1e-8)
        contrast = float(max(0.0, contrast))
        
        return peak_mean, snr, contrast, peak_std

    def predict_from_stack(
        self,
        image_stack: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        label: str,
        z_frame: int = 0,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
        refine_from_stack: bool = True,
    ) -> List[PointSuggestion]:
        """Detect candidates on mean projection, refine using full stack.
        
        Strategy:
        1. Compute mean projection across time dimension (or z if no time)
        2. Detect local maxima on clean mean image (reduced noise)
        3. For each candidate, extract features from full stack (better SNR)
        4. Return enhanced suggestions with stack-computed properties
        
        Parameters
        ----------
        image_stack : np.ndarray
            3D array of shape (T, H, W) or (Z, H, W)
        image_id : int
            Image identifier
        image_name : str
            Image name for metadata
        label : str
            Point label/class
        z_frame : int
            Z slice to use (if 3D is Z, H, W instead of T, H, W)
        strategy : str
            Detection strategy ("raw", "corrected", "consensus")
        threshold_min_score : float
            Minimum score threshold
        roi_id : str | None
            ROI identifier
        roi_shape : str
            ROI shape type
        roi_rect : tuple
            ROI rectangle coordinates
        refine_from_stack : bool
            Whether to refine features using stack (True) or single frame (False)
            
        Returns
        -------
        List[PointSuggestion]
            Scored suggestions sorted by score (descending)
        """
        stack = np.asarray(image_stack)
        if stack.ndim != 3 or stack.size == 0:
            return []
        
        # Compute mean projection (average across time or z)
        mean_projection = np.nanmean(stack.astype(np.float64), axis=0)
        
        if mean_projection.size == 0:
            return []
        
        # Detect candidates on the cleaner mean image
        # Use slightly lower threshold since noise is reduced by averaging
        lower_quantile = max(0.99, self.threshold_quantile - 0.005)
        
        raw_candidates = self._collect_candidates(
            mean_projection,
            threshold_quantile=lower_quantile,
            source_modality="mean_stack",
            image_id=image_id,
            image_name=image_name,
            t=0,
            z=z_frame,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        
        if not raw_candidates:
            return raw_candidates
        
        # OPTIMIZATION: Disabled slow per-candidate refinement (O(N_candidates × N_frames))
        # Old approach read stack[t,y,x] for each of 280 candidates across 20 frames = 5,600 reads
        # This caused 30-120s slowdown with NO quality improvement (F1 0.67 vs 0.73 for mean)
        # 
        # New approach: Return mean-projection detections (already optimal)
        # If stack refinement needed in future, process per Z-slice not per-candidate
        # See STACK_DETECTION_OPTIMIZATION.md for detailed analysis
        
        # Apply spatial filtering to remove false positives
        spatial_filtered = self._spatial_filtering(raw_candidates, mean_projection.shape)
        
        # Sort by refined score
        ranked = sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=lambda s: float(s.score),
            reverse=True,
        )
        
        # Apply max_points limit only if specified (backward compatibility)
        if self.max_points is not None and self.max_points > 0:
            return ranked[: int(self.max_points)]
        return ranked

    def predict(
        self,
        image_slice: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
        roi_shape: str = "none",
        roi_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> List[PointSuggestion]:
        arr = np.asarray(image_slice)
        if arr.ndim != 2 or arr.size == 0:
            return []
        strategy_key = str(strategy or "raw").strip().lower()
        raw_candidates = self._collect_candidates(
            arr,
            threshold_quantile=self.threshold_quantile,
            source_modality="raw",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        corrected = self._corrected_image(arr)
        corrected_candidates = self._collect_candidates(
            corrected,
            threshold_quantile=self.threshold_quantile,
            source_modality="corrected",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
            roi_shape=roi_shape,
            roi_rect=roi_rect,
        )
        if strategy_key in ("corrected",):
            selected = corrected_candidates
        elif strategy_key in ("consensus",):
            selected = self._consensus(raw_candidates, corrected_candidates, float(self.min_distance_px))
        else:
            selected = raw_candidates
        nms_selected = self._nms(selected)
        
        # Apply spatial filtering to remove false positives
        spatial_filtered = self._spatial_filtering(nms_selected, arr.shape)
        
        ranked = sorted(
            [s for s in spatial_filtered if float(s.score) >= float(threshold_min_score)],
            key=lambda s: float(s.score),
            reverse=True,
        )
        # Apply max_points limit only if specified
        if self.max_points is not None and self.max_points > 0:
            return ranked[: int(self.max_points)]
        return ranked


def summarize_suggestion_feedback(
    suggestions: Iterable[PointSuggestion],
    accepted_ids: set[str],
) -> dict:
    """Compute simple acceptance summary for reporting."""
    ids = [s.suggestion_id for s in suggestions]
    accepted = sum(1 for sid in ids if sid in accepted_ids)
    total = len(ids)
    return {
        "total": total,
        "accepted": accepted,
        "rejected": max(0, total - accepted),
        "accept_rate": (accepted / total) if total else 0.0,
    }
