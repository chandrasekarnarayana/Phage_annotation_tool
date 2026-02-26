"""Metadata indexing and parsing utilities."""

from phage_annotator.io.metadata.annotation import (
    format_tokens,
    merge_meta,
    parse_csv_header_meta,
    parse_filename_tokens,
    parse_json_meta,
)
from phage_annotator.io.metadata.index import AnnotationIndexEntry, build_index, match
from phage_annotator.io.metadata.reader import MetadataBundle, read_metadata, read_metadata_summary

__all__ = [
    "AnnotationIndexEntry",
    "build_index",
    "match",
    "format_tokens",
    "merge_meta",
    "parse_csv_header_meta",
    "parse_filename_tokens",
    "parse_json_meta",
    "MetadataBundle",
    "read_metadata",
    "read_metadata_summary",
]
