"""Numeric blend kernels used by channel compositing."""

from __future__ import annotations

import numpy as np


def blend_normal(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Composite ``layer`` over ``base`` with standard opacity blending."""
    opacity = float(np.clip(opacity, 0.0, 1.0))
    return np.clip(base * (1.0 - opacity) + layer * opacity, 0, 1)


def blend_overlay(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Blend with overlay math that multiplies shadows and screens highlights."""
    result = np.where(
        base < 0.5,
        2 * base * layer,
        1 - 2 * (1 - base) * (1 - layer),
    )
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_screen(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Blend with screen math so brighter pixels dominate the composition."""
    result = 1 - (1 - base) * (1 - layer)
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_multiply(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Blend with multiply math so darker pixels dominate the composition."""
    result = base * layer
    return np.clip((1 - opacity) * base + opacity * result, 0, 1)


def blend_add(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Add channel values directly without clipping the result."""
    return base + layer * opacity


def blend_subtract(base: np.ndarray, layer: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Subtract channel values directly without clipping the result."""
    return base - layer * opacity
