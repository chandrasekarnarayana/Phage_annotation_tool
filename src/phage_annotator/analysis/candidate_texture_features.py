"""Secondary texture, tensor, smoothing, entropy, and radial peak features."""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter, gaussian_laplace

try:
    from skimage.feature import graycomatrix, graycoprops, hessian_matrix, hessian_matrix_eigvals, structure_tensor
except ImportError:
    graycomatrix = None
    graycoprops = None
    hessian_matrix = None
    hessian_matrix_eigvals = None
    structure_tensor = None


def tensor_features(patch: np.ndarray) -> dict[str, float]:
    """Calculate Hessian and structure-tensor blob features."""
    values = {"hessian_eig1": 0.0, "hessian_eig2": 0.0, "struct_eig1": 0.0, "struct_eig2": 0.0}
    if patch.shape[0] < 5 or patch.shape[1] < 5:
        return values
    cy, cx = patch.shape[0] // 2, patch.shape[1] // 2
    try:
        if hessian_matrix_eigvals is not None:
            eigvals = hessian_matrix_eigvals(hessian_matrix(patch.astype(float), sigma=1.0, order="rc"))
            values["hessian_eig1"] = float(eigvals[0][cy, cx])
            values["hessian_eig2"] = float(eigvals[1][cy, cx])
    except Exception:
        pass
    try:
        if structure_tensor is not None:
            a_xx, a_xy, a_yy = structure_tensor(patch.astype(float), sigma=1.0)
            a, b, c = a_xx[cy, cx], a_xy[cy, cx], a_yy[cy, cx]
            disc = (a + c) ** 2 - 4 * (a * c - b * b)
            root = np.sqrt(disc) if disc >= 0 else 0.0
            values["struct_eig1"] = float((a + c + root) / 2)
            values["struct_eig2"] = float((a + c - root) / 2)
    except Exception:
        pass
    return values


def texture_features(patch: np.ndarray) -> dict[str, float]:
    """Calculate GLCM texture features with dependency fallbacks."""
    empty = {"haralick_contrast": 0.0, "haralick_homogeneity": 0.0, "haralick_correlation": 0.0, "haralick_energy": 0.0}
    try:
        if graycomatrix is None or patch.shape[0] < 5 or patch.shape[1] < 5:
            return empty
        patch_norm = ((patch - patch.min()) / (patch.max() - patch.min() + 1e-10) * 255).astype(np.uint8)
        glcm = graycomatrix(patch_norm, distances=[1], angles=[0], levels=256, symmetric=True, normed=True)
        return {f"haralick_{name}": float(graycoprops(glcm, name)[0, 0]) for name in ("contrast", "homogeneity", "correlation", "energy")}
    except Exception:
        return empty


def smooth_features(patch: np.ndarray, center: float) -> dict[str, float]:
    """Calculate Gaussian, DoG, derivative, and LoG multi-scale features."""
    values = {"gaussian_blur": float(center), "dog": 0.0, "gaussian_grad_magnitude": 0.0, "log": 0.0}
    try:
        if patch.shape[0] < 5 or patch.shape[1] < 5:
            return values
        patch_f = patch.astype(float)
        cy, cx = patch.shape[0] // 2, patch.shape[1] // 2
        small = gaussian_filter(patch_f, sigma=0.5)
        large = gaussian_filter(patch_f, sigma=2.0)
        grad_y = ndi.gaussian_filter(patch_f, sigma=1.0, order=(1, 0))[cy, cx]
        grad_x = ndi.gaussian_filter(patch_f, sigma=1.0, order=(0, 1))[cy, cx]
        values["gaussian_blur"] = float(gaussian_filter(patch_f, sigma=1.0)[cy, cx])
        values["dog"] = float(small[cy, cx] - large[cy, cx])
        values["gaussian_grad_magnitude"] = float(np.sqrt(float(grad_x) ** 2 + float(grad_y) ** 2))
        values["log"] = float(gaussian_laplace(patch_f, sigma=1.0)[cy, cx])
    except Exception:
        pass
    return values


def entropy_feature(patch: np.ndarray) -> float:
    """Estimate local entropy from a compact histogram."""
    try:
        flat = patch.flatten()
        if len(flat) == 0:
            return 0.0
        hist, _ = np.histogram(flat, bins=16, range=(flat.min(), flat.max() + 1e-8))
        hist_norm = hist / (hist.sum() + 1e-10)
        return float(-np.sum(hist_norm * np.log2(hist_norm + 1e-10)))
    except Exception:
        return 0.0


def radial_profile_variance(patch: np.ndarray) -> float:
    """Measure radial variance around the local patch center."""
    try:
        if patch.shape[0] < 3 or patch.shape[1] < 3:
            return 0.0
        py, px = patch.shape
        cy, cx = py // 2, px // 2
        yy, xx = np.ogrid[:py, :px]
        radii = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        radial_bins = np.linspace(0, np.max(radii), 5)
        variances = []
        for i in range(len(radial_bins) - 1):
            mask = (radii >= radial_bins[i]) & (radii < radial_bins[i + 1])
            if np.sum(mask) > 0:
                variances.append(np.var(patch[mask]))
        return float(np.mean(variances)) if variances else 0.0
    except Exception:
        return 0.0
