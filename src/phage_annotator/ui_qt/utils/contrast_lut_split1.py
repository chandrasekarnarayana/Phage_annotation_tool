"""Split definitions from contrast_lut.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np


@dataclass
class ConverterSetup:
    """Core brightness/contrast mapping engine with LUT pre-computation.

    Uses a pre-computed Look-Up Table (LUT) for instant pixel value mapping.
    This avoids repeated floating-point calculations during rendering.

    Mathematical Formula
    --------------------
    For pixel intensity P with min/max thresholds:

        IF P < minInput:
            Output = minOutput (black)
        ELSE IF P > maxInput:
            Output = maxOutput (white)
        ELSE:
            Output = ((P - minInput) / (maxInput - minInput)) × (maxOutput - minOutput) + minOutput

    Example
    -------
    LUT range [1000, 5000] → [0, 255]:
        P=1000 → lut[1000] = 0 (black threshold)
        P=3000 → lut[3000] = 127 (mid-gray)
        P=5000 → lut[5000] = 255 (white threshold)

    Attributes
    ----------
    minInput : float
        Minimum intensity value to display (black threshold).
    maxInput : float
        Maximum intensity value to display (white threshold).
    minOutput : float
        Black point output value (usually 0).
    maxOutput : float
        White point output value (usually 255).
    lut : np.ndarray or None
        Pre-computed LUT array [0...65535] → [0...255].
        None until updateLUT() is called.
    listeners : List[Callable]
        Functions called when values change (updates needed).
    """

    minInput: float = 0.0
    maxInput: float = 255.0
    minOutput: float = 0.0
    maxOutput: float = 255.0
    lut: Optional[np.ndarray] = None
    listeners: List[Callable] = field(default_factory=list)

    def setMinMax(self, min_val: float, max_val: float) -> None:
        """Set input range and rebuild LUT.

        Parameters
        ----------
        min_val : float
            Minimum intensity threshold.
        max_val : float
            Maximum intensity threshold.

        Raises
        ------
        ValueError
            If min >= max.
        """
        if min_val >= max_val:
            raise ValueError(f"min ({min_val}) must be < max ({max_val})")

        self.minInput = min_val
        self.maxInput = max_val
        self.updateLUT()
        self.notifyListeners()

    def updateLUT(self) -> None:
        """Pre-compute Look-Up Table for all possible input values.

        Creates an array where lut[intensity] = mapped_output.
        This allows O(1) lookup during rendering instead of O(1) computation.

        Time Complexity: O(65536) - negligible (~1ms)
        Space: ~64KB for 65536-element uint8 array
        """
        # Allocate LUT for 16-bit range (0-65535)
        self.lut = np.zeros(65536, dtype=np.uint8)

        range_val = self.maxInput - self.minInput

        for i in range(65536):
            if i < self.minInput:
                # Below threshold → black
                self.lut[i] = int(self.minOutput)
            elif i > self.maxInput:
                # Above threshold → white
                self.lut[i] = int(self.maxOutput)
            else:
                # Within range → linear mapping
                normalized = (i - self.minInput) / range_val
                mapped = normalized * (self.maxOutput - self.minOutput) + self.minOutput
                self.lut[i] = int(np.clip(mapped, 0, 255))

    def convert(self, intensity: int) -> int:
        """Apply brightness mapping to single pixel value (O(1) lookup).

        Parameters
        ----------
        intensity : int
            Raw pixel intensity (0-65535 for 16-bit).

        Returns
        -------
        int
            Mapped brightness value (0-255 for output).
        """
        if self.lut is None:
            self.updateLUT()

        # Clamp intensity to valid range, then lookup
        clipped = int(np.clip(intensity, 0, 65535))
        return self.lut[clipped]

    def convertArray(self, data: np.ndarray) -> np.ndarray:
        """Apply brightness mapping to entire image array.

        Vectorized operation for efficient batch conversion.

        Parameters
        ----------
        data : np.ndarray
            Image array of any shape/dtype (converted to int).

        Returns
        -------
        np.ndarray
            Output array [0-255] in uint8 format.
        """
        if self.lut is None:
            self.updateLUT()

        # Flatten, lookup, reshape
        original_shape = data.shape
        data_flat = data.flatten().astype(np.int32)

        # Clamp to valid LUT range
        data_flat = np.clip(data_flat, 0, 65535)

        # Apply LUT vectorized
        output_flat = self.lut[data_flat]

        return output_flat.reshape(original_shape)

    def addListener(self, listener: Callable) -> None:
        """Register callback for brightness changes.

        Parameters
        ----------
        listener : Callable
            Function called when values change (e.g., to trigger render).
        """
        self.listeners.append(listener)

    def notifyListeners(self) -> None:
        """Notify all listeners that values changed."""
        for listener in self.listeners:
            try:
                listener()
            except Exception as e:
                # Don't let listener exceptions propagate
                print(f"Warning: Listener error: {e}")

    def toDict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "minInput": float(self.minInput),
            "maxInput": float(self.maxInput),
            "minOutput": float(self.minOutput),
            "maxOutput": float(self.maxOutput),
        }

    @classmethod
    def fromDict(cls, data: dict) -> ConverterSetup:
        """Deserialize from dictionary."""
        setup = cls(
            minInput=data.get("minInput", 0.0),
            maxInput=data.get("maxInput", 255.0),
            minOutput=data.get("minOutput", 0.0),
            maxOutput=data.get("maxOutput", 255.0),
        )
        setup.updateLUT()
        return setup
