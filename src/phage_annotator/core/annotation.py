"""Keypoint models and serialization helpers for microscopy annotations.

This module defines the serialized schema for annotation data and provides
CSV/JSON helpers used by the GUI and project I/O. The schema is stable and
backward compatible with legacy x/y CSVs.

Conventions
-----------
- Coordinates are stored in full-resolution image coordinates.
- t/z are integers; -1 indicates "all frames" when applicable.
"""

from __future__ import annotations

from phage_annotator.core.annotation_types import (
    ANNOTATION_META_DEFAULTS,
    PROVENANCE_DATAFRAME_COLUMNS,
    normalize_annotation_meta,
    Keypoint,
    PointSuggestion,
)
from phage_annotator.core.annotation_serialization import (
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
    keypoints_from_csv,
    keypoints_from_json,
)

__all__ = [
    "Keypoint",
    "PointSuggestion",
    "ANNOTATION_META_DEFAULTS",
    "PROVENANCE_DATAFRAME_COLUMNS",
    "normalize_annotation_meta",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]
