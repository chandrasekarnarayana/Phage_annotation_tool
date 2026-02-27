"""Backward compatibility facade for annotations module.

This module has been moved to phage_annotator.core.annotation
This file re-exports symbols for backward compatibility.

New code should import from: phage_annotator.core.annotation
Old code importing from: phage_annotator.annotations (still works)
"""

# Re-export from new location for backward compatibility
from phage_annotator.core.annotation import (
    ANNOTATION_META_DEFAULTS,
    Keypoint,
    PointSuggestion,
    normalize_annotation_meta,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
    keypoints_from_csv,
    keypoints_from_json,
)

__all__ = [
    "ANNOTATION_META_DEFAULTS",
    "Keypoint",
    "PointSuggestion",
    "normalize_annotation_meta",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]
