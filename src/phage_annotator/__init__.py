"""Phage Annotator package."""

from phage_annotator.annotations import (
    Keypoint,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
)
from phage_annotator.config import AppConfig, DEFAULT_CONFIG
from phage_annotator.gui_mpl import run_gui

__all__ = [
    "__version__",
    "Keypoint",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "AppConfig",
    "DEFAULT_CONFIG",
    "run_gui",
]

__version__ = "1.0.0"
