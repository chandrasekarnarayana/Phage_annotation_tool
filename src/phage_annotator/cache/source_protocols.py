"""Cache source protocols helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple, TYPE_CHECKING

import numpy as np

from phage_annotator.cache.projection_cache_core import ProjectionCache

if TYPE_CHECKING:
    from phage_annotator.cache.disk_cache import CompressedBuffer, DiskCache
    from phage_annotator.config.settings import ComponentMemoryBudget

logger = logging.getLogger(__name__)

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int, int]




__all__ = ["ProjectionCache"]
