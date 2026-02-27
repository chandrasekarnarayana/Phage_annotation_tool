"""Backward compatibility facade for annotation metadata helpers.

This module has been moved to phage_annotator.io.metadata.annotation.
"""

from phage_annotator.io.metadata.annotation import (
    format_tokens,
    merge_meta,
    parse_csv_header_meta,
    parse_filename_tokens,
    parse_json_meta,
)

__all__ = [
    "format_tokens",
    "merge_meta",
    "parse_csv_header_meta",
    "parse_filename_tokens",
    "parse_json_meta",
]
