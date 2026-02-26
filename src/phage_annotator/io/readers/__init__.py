"""Image and annotation readers."""

from phage_annotator.io.readers.base import (
    ImageMeta,
    load_images,
    read_contiguous_block,
    read_contiguous_block_from_path,
    read_metadata_bundle,
    read_metadata_summary,
    standardize_axes,
)
from phage_annotator.io.readers.annotations import (
    detect_format,
    parse_legacy_csv,
    parse_thunderstorm_csv,
)

__all__ = [
    "ImageMeta",
    "load_images",
    "read_contiguous_block",
    "read_contiguous_block_from_path",
    "read_metadata_bundle",
    "read_metadata_summary",
    "standardize_axes",
    "detect_format",
    "parse_legacy_csv",
    "parse_thunderstorm_csv",
]
