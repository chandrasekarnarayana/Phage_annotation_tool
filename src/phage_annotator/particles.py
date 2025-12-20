"""Particle analysis helpers for threshold masks (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

try:  # Optional dependencies
    from skimage import measure as sk_measure
except Exception:  # pragma: no cover - optional import
    sk_measure = None

try:  # Optional dependency
    from scipy import ndimage as ndi
except Exception:  # pragma: no cover - optional import
    ndi = None


@dataclass(frozen=True)
class Particle:
    """Particle measurement for a single connected component."""

    frame_index: int
    area_px: int
    perimeter_px: float
    circularity: float
    centroid_x: float
    centroid_y: float
    bbox: Tuple[int, int, int, int]
    eq_diameter: float
    outline: Optional[List[Tuple[float, float]]] = None


@dataclass(frozen=True)
class ParticleOptions:
    """Filter options for Analyze Particles."""

    min_area_px: int = 5
    max_area_px: Optional[int] = None
    min_circularity: float = 0.0
    max_circularity: float = 1.0
    exclude_edges: bool = True
    include_holes: bool = False
    watershed_split: bool = False


def analyze_particles(mask: np.ndarray, frame_index: int, opts: ParticleOptions) -> List[Particle]:
    """Analyze connected components in a binary mask."""
    if mask.size == 0:
        return []
    if opts.watershed_split:
        mask = _watershed_split(mask)
    labeled, num = _label_components(mask)
    if num == 0:
        return []
    particles: List[Particle] = []
    for label in range(1, num + 1):
        component = labeled == label
        area = int(component.sum())
        if area == 0:
            continue
        if opts.min_area_px and area < opts.min_area_px:
            continue
        if opts.max_area_px and area > opts.max_area_px:
            continue
        perimeter = _perimeter(component, include_holes=opts.include_holes)
        circularity = 0.0 if perimeter <= 0 else float(4 * np.pi * area / (perimeter**2))
        if circularity < opts.min_circularity or circularity > opts.max_circularity:
            continue
        if opts.exclude_edges and _touches_edge(component):
            continue
        ys, xs = np.nonzero(component)
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        centroid_y = float(ys.mean())
        centroid_x = float(xs.mean())
        eq_diameter = float(2.0 * np.sqrt(area / np.pi))
        outline = _outline(component)
        particles.append(
            Particle(
                frame_index=frame_index,
                area_px=area,
                perimeter_px=float(perimeter),
                circularity=float(circularity),
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                bbox=(x0, y0, x1 - x0 + 1, y1 - y0 + 1),
                eq_diameter=eq_diameter,
                outline=outline,
            )
        )
    return particles


def _label_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    if sk_measure is not None:
        labeled = sk_measure.label(mask, connectivity=2)
        return labeled, int(labeled.max())
    if ndi is None:
        return np.zeros_like(mask, dtype=int), 0
    structure = np.ones((3, 3), dtype=int)
    labeled, num = ndi.label(mask, structure=structure)
    return labeled, int(num)


def _perimeter(component: np.ndarray, include_holes: bool) -> float:
    if sk_measure is not None:
        return float(sk_measure.perimeter(component, neighbourhood=8))
    if ndi is None:
        return float(component.sum())
    eroded = ndi.binary_erosion(component)
    boundary = component & ~eroded
    if include_holes:
        filled = ndi.binary_fill_holes(component)
        inner = filled & ~component
        inner_eroded = ndi.binary_erosion(inner)
        boundary |= inner & ~inner_eroded
    return float(boundary.sum())


def _touches_edge(component: np.ndarray) -> bool:
    return bool(
        component[0, :].any()
        or component[-1, :].any()
        or component[:, 0].any()
        or component[:, -1].any()
    )


def _outline(component: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    if sk_measure is None:
        return None
    contours = sk_measure.find_contours(component.astype(float), 0.5)
    if not contours:
        return None
    contour = max(contours, key=lambda arr: arr.shape[0])
    return [(float(x), float(y)) for y, x in contour]


def _watershed_split(mask: np.ndarray) -> np.ndarray:
    if sk_measure is None:
        return mask
    try:
        from skimage import morphology as sk_morph
        from skimage.segmentation import watershed
    except Exception:
        return mask
    dist = sk_morph.distance_transform_edt(mask)
    if dist.max() <= 0:
        return mask
    markers = sk_morph.label(dist > np.percentile(dist[dist > 0], 70))
    if markers.max() == 0:
        return mask
    labels = watershed(-dist, markers, mask=mask)
    return labels > 0
