"""Rendering export writers impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from phage_annotator.rendering.scalebar import ScaleBarSpec, compute_scalebar



def calculate_export_chunks(
    image_shape: Tuple[int, int], chunk_size: int = 256
) -> list[Tuple[int, int, int, int]]:
    """Calculate chunk boundaries for streaming export (P4a).
    
    Parameters
    ----------
    image_shape : Tuple[int, int]
        Full image shape (height, width)
    chunk_size : int
        Chunk size in pixels (default 256×256)
    
    Returns
    -------
    list[Tuple[int, int, int, int]]
        List of (x0, y0, x1, y1) crop boxes for each chunk
    """
    chunks = []
    height, width = image_shape
    
    for y in range(0, height, chunk_size):
        for x in range(0, width, chunk_size):
            x0, y0 = x, y
            x1 = min(x + chunk_size, width)
            y1 = min(y + chunk_size, height)
            chunks.append((x0, y0, x1, y1))
    
    return chunks
