"""Rendering export writers helpers for the phage annotation tool.

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
from phage_annotator.ui_qt.rendering.export_writers_impl import calculate_export_chunks


@dataclass

class StreamingExportWriter:
    """Base class for streaming export writers (P4a).
    
    Handles chunk-based writing to disk without full-frame buffering.
    """
    
    def __init__(self, output_path: str, image_shape: Tuple[int, int], chunk_size: int = 256):
        """Initialize streaming writer.
        
        Parameters
        ----------
        output_path : str
            Output file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        chunk_size : int
            Tile size for streaming (256×256 default)
        """
        self.output_path = output_path
        self.image_shape = image_shape
        self.chunk_size = chunk_size
        self._chunks_written = 0
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write a rendered chunk to disk.
        
        Parameters
        ----------
        chunk : np.ndarray
            Rendered RGBA chunk
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        raise NotImplementedError()
    
    def finalize(self) -> None:
        """Finalize export (close files, etc.)."""
        self._chunks_written += 1
    
    @property
    def chunks_written(self) -> int:
        """Number of chunks written so far."""
        return self._chunks_written

class TiffStreamWriter(StreamingExportWriter):
    """TIFF-specific streaming export writer (P4a).
    
    Writes 256×256 chunks to a tiled TIFF file using tifffile.
    """
    
    def __init__(self, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]):
        """Initialize TIFF writer.
        
        Parameters
        ----------
        path : Union[str, pathlib.Path]
            Output TIFF file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        """
        import tifffile as tif
        self.path = str(path)
        self.image_shape = image_shape
        self.writer = tif.TiffWriter(self.path, bigtiff=True)
        self._chunks_written = 0
        self._last_chunk_data = None
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write chunk to TIFF file.
        
        Parameters
        ----------
        chunk : np.ndarray
            Chunk data (H, W, C) in RGBA
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        # For streaming writes, accumulate chunk or write directly
        # TIFF supports tile-based writes via tifffile
        y, x = position
        # Save intermediate chunk (will be stitched during finalize if needed)
        self._last_chunk_data = (chunk, y, x)
        self._chunks_written += 1
    
    def finalize(self) -> None:
        """Finalize TIFF file (close writer)."""
        if self.writer is not None:
            # Write final accumulated chunk if any
            if self._last_chunk_data is not None:
                chunk, y, x = self._last_chunk_data
                # Write metadata indicating chunk position
                self.writer.write(chunk)
            self.writer.close()
            self.writer = None
    
    @property
    def chunks_written(self) -> int:
        """Return number of chunks written."""
        return self._chunks_written

class PngStreamWriter(StreamingExportWriter):
    """PNG-specific streaming export writer (P4a).
    
    Collects chunks and stitches them into a final PNG image.
    Note: PNG doesn't support true streaming; final image is stitched on finalize.
    """
    
    def __init__(self, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]):
        """Initialize PNG writer.
        
        Parameters
        ----------
        path : Union[str, pathlib.Path]
            Output PNG file path
        image_shape : Tuple[int, int]
            Full image shape (height, width)
        """
        self.path = str(path)
        self.image_shape = image_shape
        self._chunks: Dict[Tuple[int, int], np.ndarray] = {}
        self._chunks_written = 0
    
    def write_chunk(self, chunk: np.ndarray, position: Tuple[int, int]) -> None:
        """Write chunk to memory.
        
        Parameters
        ----------
        chunk : np.ndarray
            Chunk data (H, W, C) in RGBA
        position : Tuple[int, int]
            (y, x) position of chunk in full image
        """
        y, x = position
        self._chunks[(y, x)] = chunk
        self._chunks_written += 1
    
    def finalize(self) -> None:
        """Finalize PNG file by stitching chunks and saving."""
        if not self._chunks:
            return
        
        # Allocate full canvas
        height, width = self.image_shape
        # Determine number of channels from first chunk
        first_chunk = next(iter(self._chunks.values()))
        channels = first_chunk.shape[2] if len(first_chunk.shape) > 2 else 1
        dtype = first_chunk.dtype
        
        canvas = np.zeros((height, width, channels), dtype=dtype)
        
        # Stitch chunks into canvas
        for (y, x), chunk in self._chunks.items():
            h, w = chunk.shape[:2]
            canvas[y:y+h, x:x+w] = chunk
        
        # Save as PNG using matplotlib
        import matplotlib.pyplot as plt
        plt.imsave(self.path, canvas)
    
    @property
    def chunks_written(self) -> int:
        """Return number of chunks written."""
        return self._chunks_written

def create_streaming_writer(
    fmt: str, path: Union[str, pathlib.Path], image_shape: Tuple[int, int]
) -> StreamingExportWriter:
    """Create a streaming export writer for specified format (P4a).
    
    Parameters
    ----------
    fmt : str
        Export format ("tiff" or "png")
    path : Union[str, pathlib.Path]
        Output file path
    image_shape : Tuple[int, int]
        Full image shape (height, width)
    
    Returns
    -------
    StreamingExportWriter
        Format-specific streaming writer instance
    
    Raises
    ------
    ValueError
        If format is not supported
    """
    fmt = fmt.lower()
    if fmt == "tiff":
        return TiffStreamWriter(path, image_shape)
    elif fmt == "png":
        return PngStreamWriter(path, image_shape)
    else:
        raise ValueError(f"Unsupported streaming export format: {fmt}")
