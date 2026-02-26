"""I/O package for image, metadata, and project helpers."""

import tifffile as tif

from phage_annotator.io.readers.base import (
    ImageMeta,
    load_images,
    read_contiguous_block,
    read_contiguous_block_from_path,
    read_metadata_bundle,
    read_metadata_summary,
    standardize_axes,
)

__all__ = [
    "ImageMeta",
    "load_images",
    "read_contiguous_block",
    "read_contiguous_block_from_path",
    "read_metadata_bundle",
    "read_metadata_summary",
    "standardize_axes",
    "tif",
]
