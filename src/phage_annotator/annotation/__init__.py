"""Annotation system (P3 refactoring).

This module handles keypoint annotations and metadata:
- Core annotation models (Keypoint)
- Annotation indexing and queries
- Annotation metadata and properties
"""

from phage_annotator.annotation.core import Keypoint

__all__ = [
    "Keypoint",
]
