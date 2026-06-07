"""Blend mode implementations for multi-channel compositing.

This module provides implementations of common blend modes for compositing
multiple image channels. Blend modes operate on normalized float images
in the range [0, 1].

Supported Modes:
- NORMAL: Standard alpha blending with per-channel opacity
- OVERLAY: Photoshop-like overlay blending
- SCREEN: Additive screen blending (inverse multiply)
- MULTIPLY: Subtractive multiply blending
- ADD: Direct addition (may exceed 1.0)
- SUBTRACT: Direct subtraction (may go below 0.0)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Tuple

import numpy as np

from phage_annotator.ui_qt.rendering.blend_kernels import (
    blend_add,
    blend_multiply,
    blend_normal,
    blend_overlay,
    blend_screen,
    blend_subtract,
)


class BlendMode(Enum):
    """Blend modes for channel compositing."""
    NORMAL = "normal"
    OVERLAY = "overlay"
    SCREEN = "screen"
    MULTIPLY = "multiply"
    ADD = "add"
    SUBTRACT = "subtract"


# Blend mode function registry
BLEND_FUNCTIONS = {
    BlendMode.NORMAL: blend_normal,
    BlendMode.OVERLAY: blend_overlay,
    BlendMode.SCREEN: blend_screen,
    BlendMode.MULTIPLY: blend_multiply,
    BlendMode.ADD: blend_add,
    BlendMode.SUBTRACT: blend_subtract,
}


def _resolve_blend_mode(blend_mode: object) -> BlendMode:
    """Resolve blend mode from local enum, foreign enum, or string value.

    This accepts ``BlendMode`` from this module, enum-like objects with a
    string ``value`` attribute, or raw string mode names.
    """
    if isinstance(blend_mode, BlendMode):
        return blend_mode
    if isinstance(blend_mode, str):
        mode_str = blend_mode
    else:
        mode_str = getattr(blend_mode, "value", "")
    try:
        return BlendMode(str(mode_str).lower())
    except ValueError:
        return BlendMode.NORMAL


def composite_channels(
    channels: List[Tuple[np.ndarray, float]],
    blend_mode: object = BlendMode.NORMAL,
    normalize_output: bool = True,
) -> np.ndarray:
    """Composite multiple channels with specified blend mode.
    
    Parameters
    ----------
    channels : List[Tuple[np.ndarray, float]]
        List of (image, opacity) tuples. Images should be float [0-1].
    blend_mode : object
        Blend mode to use for compositing. Accepts local ``BlendMode``,
        enum-like objects with ``value`` (for cross-module compatibility),
        or raw strings.
    normalize_output : bool
        If True, clip output to [0, 1] after compositing.
    
    Returns
    -------
    np.ndarray
        Composited image with same shape as first channel.
    
    Examples
    --------
    >>> ch1 = np.random.rand(256, 256)
    >>> ch2 = np.random.rand(256, 256)
    >>> result = composite_channels(
    ...     [(ch1, 1.0), (ch2, 0.5)],
    ...     blend_mode=BlendMode.SCREEN
    ... )
    """
    if not channels:
        return np.zeros((0, 0), dtype=np.float32)
    
    if len(channels) == 1:
        img, opacity = channels[0]
        if opacity == 1.0:
            return img.copy()
        return np.clip(img * opacity, 0, 1) if normalize_output else img * opacity
    
    # Start with first channel as base
    result, first_opacity = channels[0]
    if first_opacity != 1.0:
        result = result * first_opacity
    result = result.astype(np.float32)
    
    # Composite remaining channels
    resolved_mode = _resolve_blend_mode(blend_mode)
    blend_fn = BLEND_FUNCTIONS.get(resolved_mode, blend_normal)
    for img, opacity in channels[1:]:
        if opacity > 0:
            result = blend_fn(result, img.astype(np.float32), opacity)
    
    if normalize_output:
        result = np.clip(result, 0, 1)
    
    return result


def apply_per_channel_opacity(
    channels: List[np.ndarray],
    opacities: List[float],
) -> List[np.ndarray]:
    """Apply per-channel opacity values.
    
    Parameters
    ----------
    channels : List[np.ndarray]
        List of channel images (float [0-1]).
    opacities : List[float]
        List of opacity values (0-1).
    
    Returns
    -------
    List[np.ndarray]
        Channels with opacity applied.
    """
    if len(channels) != len(opacities):
        raise ValueError(
            f"Opacity count {len(opacities)} != channel count {len(channels)}"
        )
    
    return [
        ch * op if op != 1.0 else ch
        for ch, op in zip(channels, opacities)
    ]
