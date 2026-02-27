"""Backward compatibility facade for image_models module.

This module has been moved to phage_annotator.data.models
This file re-exports symbols for backward compatibility.

New code should import from: phage_annotator.data.models
"""

from phage_annotator.data.models import LazyImage

__all__ = ["LazyImage"]
