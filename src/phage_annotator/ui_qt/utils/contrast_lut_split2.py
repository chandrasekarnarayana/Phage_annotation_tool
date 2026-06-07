"""Split definitions from contrast_lut.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np


@dataclass
class MinMaxGroup:
    """Coupled min/max value pair with validation.

    Ensures min < max invariant is always maintained, and broadcasts
    changes to listeners (e.g., to trigger LUT rebuild).

    Parameters
    ----------
    minVal : float
        Minimum threshold value.
    maxVal : float
        Maximum threshold value.
    listeners : List[Callable]
        Callbacks for value changes.
    """

    minVal: float = 0.0
    maxVal: float = 255.0
    listeners: List[Callable] = field(default_factory=list)

    def __post_init__(self):
        """Validate that min < max after initialization."""
        if self.minVal >= self.maxVal:
            raise ValueError(f"min ({self.minVal}) must be < max ({self.maxVal})")

    @property
    def min(self) -> float:
        """Get minimum value."""
        return self.minVal

    @min.setter
    def min(self, value: float) -> None:
        """Set minimum value with validation."""
        if value >= self.maxVal:
            raise ValueError(f"min ({value}) must be < max ({self.maxVal})")
        self.minVal = value
        self._notifyMinChanged()

    @property
    def max(self) -> float:
        """Get maximum value."""
        return self.maxVal

    @max.setter
    def max(self, value: float) -> None:
        """Set maximum value with validation."""
        if value <= self.minVal:
            raise ValueError(f"max ({value}) must be > min ({self.minVal})")
        self.maxVal = value
        self._notifyMaxChanged()

    def setValues(self, min_val: float, max_val: float) -> None:
        """Set both synchronously (avoids intermediate invalid state).

        Parameters
        ----------
        min_val : float
            New minimum value.
        max_val : float
            New maximum value.

        Raises
        ------
        ValueError
            If min >= max.
        """
        if min_val >= max_val:
            raise ValueError(f"min ({min_val}) must be < max ({max_val})")
        self.minVal = min_val
        self.maxVal = max_val
        self._notifyBothChanged()

    def addListener(self, listener: Callable) -> None:
        """Register callback for changes."""
        self.listeners.append(listener)

    def _notifyMinChanged(self) -> None:
        """Notify listeners that min changed."""
        for listener in self.listeners:
            try:
                listener("min", self.minVal)
            except Exception as e:
                print(f"Warning: Listener error: {e}")

    def _notifyMaxChanged(self) -> None:
        """Notify listeners that max  changed."""
        for listener in self.listeners:
            try:
                listener("max", self.maxVal)
            except Exception as e:
                print(f"Warning: Listener error: {e}")

    def _notifyBothChanged(self) -> None:
        """Notify listeners that both changed."""
        for listener in self.listeners:
            try:
                listener("range", (self.minVal, self.maxVal))
            except Exception as e:
                print(f"Warning: Listener error: {e}")

def computeHistogram(data: np.ndarray, bins: int = 256) -> tuple:
    """Compute histogram from image data.

    Used for visualization and auto-brightness calculation.

    Parameters
    ----------
    data : np.ndarray
        Image array of any shape/dtype.
    bins : int
        Number of histogram bins (default 256 for 8-bit display).

    Returns
    -------
    tuple
        (histogram_counts, bin_edges) from np.histogram
    """
    data_flat = data.flatten().astype(np.float32)

    # Determine data range for binning
    data_min = np.min(data_flat)
    data_max = np.max(data_flat)

    # Compute histogram
    hist, edges = np.histogram(data_flat, bins=bins, range=(data_min, data_max))

    return hist, edges

def autoScaleHistogram(data: np.ndarray, method: str = "percentile") -> tuple:
    """Automatically determine optimal min/max range from data.

    Parameters
    ----------
    data : np.ndarray
        Image array.
    method : str
        Auto-scaling method:
        - "percentile": 2%-98% percentile (removes outliers)
        - "minmax": Actual min/max (stretches full range)
        - "std": Mean ± 2σ (statistical range)

    Returns
    -------
    tuple
        (min_val, max_val) optimal range.
    """
    data_flat = data.flatten().astype(np.float32)

    if method == "minmax":
        return (np.min(data_flat), np.max(data_flat))
    elif method == "percentile":
        return (np.percentile(data_flat, 2), np.percentile(data_flat, 98))
    elif method == "std":
        mean = np.mean(data_flat)
        std = np.std(data_flat)
        return (mean - 2*std, mean + 2*std)
    else:
        return (np.min(data_flat), np.max(data_flat))
