"""Phage Annotator package (non-GUI surface)."""

from phage_annotator.annotations import (
    Keypoint,
    keypoints_from_csv,
    keypoints_from_json,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
)
from phage_annotator.config import AppConfig, DEFAULT_CONFIG
from phage_annotator.io import ImageMeta, load_images, standardize_axes

__version__ = "1.0.1"

__all__ = [
    "__version__",
    "Keypoint",
    "keypoints_from_csv",
    "keypoints_from_json",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "AppConfig",
    "DEFAULT_CONFIG",
    "ImageMeta",
    "load_images",
    "standardize_axes",
]
