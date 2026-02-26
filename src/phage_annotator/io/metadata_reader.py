"""Backward compatibility facade for metadata reader helpers.

Phase 4: This module has been moved to phage_annotator.io.metadata.reader.
"""

from phage_annotator.io.metadata.reader import MetadataBundle, read_metadata, read_metadata_summary

__all__ = ["MetadataBundle", "read_metadata", "read_metadata_summary"]
