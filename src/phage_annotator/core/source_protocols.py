"""Core source protocols helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

__all__ = [
    "Keypoint",
    "PointSuggestion",
    "ANNOTATION_META_DEFAULTS",
    "PROVENANCE_DATAFRAME_COLUMNS",
    "",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "",
    "keypoints_from_json",
]


ANNOTATION_META_DEFAULTS = {
    "confidence": None,
    "status": "active",
    "roi": "",
    "notes": "",
    "annotator": "",
    "timestamp": None,
    "comment": "",
    "uncertain": False,
    "review_state": "new",
    "assignee": "",
    "reviewer": "",
    "reviewed_at": None,
}

PROVENANCE_DATAFRAME_COLUMNS = ["source", "status", "confidence", "roi", "notes"]
