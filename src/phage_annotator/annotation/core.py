"""Backward compatibility facade for annotations module.

Phase 2.5: This module has been moved to phage_annotator.core.annotation
This file re-exports symbols for backward compatibility.

New code should import from: phage_annotator.core.annotation
Old code importing from: phage_annotator.annotations (still works)
"""

# Re-export from new location for backward compatibility
from phage_annotator.core.annotation import (
    Keypoint,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
    keypoints_from_csv,
    keypoints_from_json,
)

__all__ = [
    "Keypoint",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]
