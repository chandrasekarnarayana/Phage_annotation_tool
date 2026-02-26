"""Configuration helpers for phage-annotator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

SUPPORTED_SUFFIXES: Tuple[str, ...] = (".tif", ".tiff", ".ome.tif", ".ome.tiff")


@dataclass
class AppConfig:
    """Runtime settings for microscopy keypoint annotation."""

    pixel_size_nm: float = 1.0
    supported_suffixes: Tuple[str, ...] = SUPPORTED_SUFFIXES
    config_dir: Path = field(default_factory=lambda: Path.home() / ".phage_annotator")
    # P3.5: Default label classes for empty projects
    default_labels: Tuple[str, ...] = ("Point", "Region")
    # P3b: Adaptive tile sizing for memory pressure response
    adaptive_tile_size: int = 256  # Default inference tile size (512 normal, 256 pressure, 128 critical)


DEFAULT_CONFIG = AppConfig()

__all__ = ["AppConfig", "DEFAULT_CONFIG", "SUPPORTED_SUFFIXES"]
