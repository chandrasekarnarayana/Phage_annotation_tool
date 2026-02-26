"""Backward compatibility facade for GPU helpers.

Phase 4: This module has been moved to phage_annotator.tools.utils.gpu_utils.
"""

from phage_annotator.tools.utils.gpu_utils import check_cuda_available, get_recommended_device

__all__ = ["check_cuda_available", "get_recommended_device"]
