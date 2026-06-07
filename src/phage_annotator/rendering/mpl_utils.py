"""Low-level matplotlib artist helpers: create/update images, clear overlays."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import matplotlib
import matplotlib.image
import numpy as np


def _update_or_create(
    ax: matplotlib.axes.Axes,
    artist: Optional[matplotlib.image.AxesImage],
    data: Optional[np.ndarray],
    cmap: str,
    vmin: float,
    vmax: float,
    extent: Optional[Tuple[float, float, float, float]] = None,
    norm: Optional[matplotlib.colors.Normalize] = None,
) -> Optional[matplotlib.image.AxesImage]:
    """Update or create for the current workflow."""
    if data is None:
        return artist
    # MATPLOTLIB API FIX: Cannot pass both norm and vmin/vmax to imshow()
    # If norm is provided, it should contain the vmin/vmax. Otherwise use vmin/vmax directly.
    if artist is None:
        if norm is not None:
            artist = ax.imshow(data, cmap=cmap, extent=extent, norm=norm)
        else:
            artist = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent)
    else:
        artist.set_data(data)
        artist.set_cmap(cmap)
        if norm is not None:
            artist.set_norm(norm)
        else:
            artist.set_clim(vmin, vmax)
        if extent is None:
            extent = (0, data.shape[1], data.shape[0], 0)
        artist.set_extent(extent)
    return artist


def _normalize_overlay_to_uint8(data: np.ndarray) -> np.ndarray:
    """Normalize overlay array to uint8 (P1b: dtype enforcement).

    Converts float overlays to uint8 with min/max normalization.
    Preserves bool and uint8 as-is.
    """
    if data.dtype == np.uint8:
        return data
    if data.dtype == bool:
        return data.astype(np.uint8) * 255
    # Float: normalize to [0, 255]
    data_min = float(np.min(data))
    data_max = float(np.max(data))
    if data_max <= data_min:
        return np.zeros_like(data, dtype=np.uint8)
    normalized = (data - data_min) / (data_max - data_min)
    return (normalized * 255).astype(np.uint8)


def _clear_overlays(
    axes: Dict[str, matplotlib.axes.Axes],
    image_artists: Dict[str, Optional[matplotlib.image.AxesImage]],
) -> None:
    """Clear overlays for the current workflow."""
    for ax in axes.values():
        for artist in list(ax.patches):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.lines):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.texts):
            if artist.get_gid() in ("scalebar", "roi_interactor"):
                continue
            artist.remove()
        for artist in list(ax.collections):
            if artist in image_artists.values() or artist.get_gid() == "roi_interactor":
                continue
            artist.remove()
