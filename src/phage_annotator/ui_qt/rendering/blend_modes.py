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


class BlendMode(Enum):
    """Blend modes for channel compositing."""
    NORMAL = "normal"
    OVERLAY = "overlay"
    SCREEN = "screen"
    MULTIPLY = "multiply"
    ADD = "add"
    SUBTRACT = "subtract"


def blend_normal(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Standard alpha blending.
    
    Composites layer onto base using opacity.
    
    Parameters
    ----------
    base : np.ndarray
        Base image (any shape, float [0-1] or uint8).
    layer : np.ndarray
        Layer to composite (same shape as base).
    opacity : float
        Opacity of layer (0-1).
    
    Returns
    -------
    np.ndarray
        Composited result with same dtype as input.
    """
    opacity = float(np.clip(opacity, 0.0, 1.0))
    return np.clip(base * (1.0 - opacity) + layer * opacity, 0, 1)


def blend_overlay(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Overlay blend mode (Photoshop-style).
    
    Multiplies dark colors and screens bright colors.
    
    Parameters
    ----------
    base : np.ndarray
        Base image (float [0-1]).
    layer : np.ndarray
        Layer to composite.
    opacity : float
        Opacity/strength of overlay effect.
    
    Returns
    -------
    np.ndarray
        Blended result [0-1].
    """
    # Overlay formula: 
    # if base < 0.5: result = 2 * base * layer
    # else: result = 1 - 2 * (1 - base) * (1 - layer)
    result = np.where(
        base < 0.5,
        2 * base * layer,
        1 - 2 * (1 - base) * (1 - layer),
    )
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_screen(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Screen blend mode (additive).
    
    Inverts, multiplies, and inverts again. Bright colors dominate.
    
    Parameters
    ----------
    base : np.ndarray
        Base image (float [0-1]).
    layer : np.ndarray
        Layer to composite.
    opacity : float
        Opacity of effect.
    
    Returns
    -------
    np.ndarray
        Blended result [0-1].
    """
    # Screen formula: 1 - (1 - base) * (1 - layer)
    result = 1 - (1 - base) * (1 - layer)
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_multiply(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Multiply blend mode (subtractive).
    
    Multiplies channels. Dark colors dominate.
    
    Parameters
    ----------
    base : np.ndarray
        Base image (float [0-1]).
    layer : np.ndarray
        Layer to composite.
    opacity : float
        Opacity of effect.
    
    Returns
    -------
    np.ndarray
        Blended result [0-1].
    """
    # Multiply formula: base * layer
    result = base * layer
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_add(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Add blend mode (direct addition).
    
    Adds channel values directly. Can exceed [0, 1].
    
    Parameters
    ----------
    base : np.ndarray
        Base image (float).
    layer : np.ndarray
        Layer to add.
    opacity : float
        Opacity of layer.
    
    Returns
    -------
    np.ndarray
        Sum (may exceed 1.0).
    """
    return base + layer * opacity


def blend_subtract(
    base: np.ndarray,
    layer: np.ndarray,
    opacity: float = 1.0,
) -> np.ndarray:
    """Subtract blend mode (direct subtraction).
    
    Subtracts layer from base. Can go negative.
    
    Parameters
    ----------
    base : np.ndarray
        Base image (float).
    layer : np.ndarray
        Layer to subtract.
    opacity : float
        Opacity of effect.
    
    Returns
    -------
    np.ndarray
        Difference (may be negative).
    """
    return base - layer * opacity


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
