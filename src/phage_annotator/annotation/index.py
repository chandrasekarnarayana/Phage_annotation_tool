"""Backward compatibility facade for annotation index helpers.

This module has been moved to phage_annotator.io.metadata.index.
"""

from phage_annotator.io.metadata.index import AnnotationIndexEntry, build_index, match

__all__ = ["AnnotationIndexEntry", "build_index", "match"]
