"""Configuration helpers for phage-annotator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

SUPPORTED_SUFFIXES: Tuple[str, ...] = (".tif", ".tiff", ".ome.tif", ".ome.tiff")


@dataclass
class AppConfig:
    """Runtime settings for microscopy keypoint annotation.

    Attributes:
        pixel_size_nm: Nominal pixel size (nm) for downstream measurements.
        supported_suffixes: Image filename suffixes accepted by the loader.
        config_dir: Directory for user-level config or cache.
        default_labels: Default label classes exposed in the GUI.
    """

    pixel_size_nm: float = 1.0
    supported_suffixes: Tuple[str, ...] = SUPPORTED_SUFFIXES
    config_dir: Path = field(default_factory=lambda: Path.home() / ".phage_annotator")
    default_labels: Tuple[str, ...] = ("phage", "artifact", "other")


DEFAULT_CONFIG = AppConfig()

__all__ = ["AppConfig", "DEFAULT_CONFIG", "SUPPORTED_SUFFIXES"]
