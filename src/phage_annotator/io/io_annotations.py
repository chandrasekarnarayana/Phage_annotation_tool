"""Backward compatibility facade for annotation CSV readers.

Phase 4: This module has been moved to phage_annotator.io.readers.annotations.
"""

from phage_annotator.io.readers.annotations import (
    detect_format,
    parse_legacy_csv,
    parse_thunderstorm_csv,
)

__all__ = ["detect_format", "parse_legacy_csv", "parse_thunderstorm_csv"]
