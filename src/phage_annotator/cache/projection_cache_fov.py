"""FOV adjacency and component budget methods for ProjectionCache."""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phage_annotator.cache.disk_cache import CompressedBuffer, DiskCache
    from phage_annotator.config.settings import ComponentMemoryBudget

logger = logging.getLogger(__name__)

CacheKey = Tuple[int, str, Tuple[float, float, float, float], int, int, int]
PyramidKey = Tuple[int, str, int, int, Tuple[float, float, float, float], int, int]

class ProjectionCacheFovMixin:
    def get_adjacent_fov_ids(self, current_image_id: int, fov_grid_cols: int,
                            fov_grid_rows: int) -> list[int]:
        """Detect adjacent FOVs in grid for predictive prefetch (P7c).
        
        Given a current FOV index in a grid layout, returns indices of adjacent
        FOVs (up, down, left, right) that are candidates for low-priority prefetch.
        
        Args:
            current_image_id: Index of current FOV (0-indexed)
            fov_grid_cols: Number of columns in FOV grid
            fov_grid_rows: Number of rows in FOV grid
        
        Returns:
            List of adjacent FOV indices (max 4 for cardinal directions).
        """
        if fov_grid_cols <= 0 or fov_grid_rows <= 0:
            return []  # Grid not configured
        
        total_fovs = fov_grid_cols * fov_grid_rows
        if current_image_id < 0 or current_image_id >= total_fovs:
            return []  # Invalid FOV index
        
        # Convert linear index to (row, col)
        row = current_image_id // fov_grid_cols
        col = current_image_id % fov_grid_cols
        
        adjacent = []
        
        # Check all 4 cardinal directions
        directions = [
            (row - 1, col, "up"),      # Up
            (row + 1, col, "down"),    # Down
            (row, col - 1, "left"),    # Left
            (row, col + 1, "right"),   # Right
        ]
        
        for adj_row, adj_col, direction in directions:
            if 0 <= adj_row < fov_grid_rows and 0 <= adj_col < fov_grid_cols:
                adj_id = adj_row * fov_grid_cols + adj_col
                adjacent.append(adj_id)
                logger.debug(f"Adjacent FOV {direction}: {adj_id}")
        
        return adjacent
    
    def should_prefetch_adjacent(self, current_image_id: int) -> bool:
        """Check if we should prefetch adjacent FOVs (P7c).
        
        Prefetch is enabled if:
        - Current cache usage is below 70% of budget (has room)
        - Not in memory pressure situation
        
        Args:
            current_image_id: Index of current FOV  
        
        Returns:
            True if prefetch is recommended, False if budget constrained.
        """
        cache_usage = self._total_bytes / self._max_bytes if self._max_bytes > 0 else 0.0
        
        # Disable prefetch if cache near capacity
        if cache_usage > 0.70:
            logger.debug(f"Prefetch disabled: cache at {cache_usage * 100:.1f}%")
            return False
        
        # Disable if currently thrashing
        if self._telemetry.is_thrashing():
            logger.debug("Prefetch disabled: cache thrashing detected")
            return False
        
        return True

    def should_compute(self, modality_idx: int | None = None) -> bool:
        """Return whether a new projection should be computed now.

        Computation is paused when the cache is full or thrashing so the UI can
        stay responsive instead of spending cycles on projections that would be
        immediately evicted.
        """
        if self._telemetry.is_thrashing():
            logger.debug("Projection compute blocked: cache thrashing detected")
            return False
        if self._max_bytes <= 0:
            return True
        if self._total_bytes >= self._max_bytes:
            logger.debug("Projection compute blocked: cache budget exhausted")
            return False
        if modality_idx is None or self._modality_count <= 1:
            return True
        per_modality_budget = self._max_bytes // max(1, self._modality_count)
        modality_bytes, _ = self.get_modality_usage(int(modality_idx))
        return modality_bytes < per_modality_budget
    
    def get_component_usage(self, component: str) -> Tuple[int, int]:
        """Get memory usage for specific component (P7e).
        
        Args:
            component: One of 'projection_main', 'projection_pyramid'
        
        Returns:
            Tuple of (bytes_used, mb_used)
        """
        bytes_used = self._component_bytes.get(component, 0)
        mb_used = bytes_used // (1024 * 1024)
        return bytes_used, mb_used
    
    def get_component_budget_mb(self, component: str) -> int:
        """Get allocated memory budget for component (P7e).
        
        Args:
            component: One of 'projection_main', 'projection_pyramid'
        
        Returns:
            Memory budget in MB, or total cache budget if not configured per-component.
        """
        if self._component_budget is None:
            return int(self._max_bytes // (1024 * 1024))
        
        if component == 'projection_main':
            return self._component_budget.projection_cache_mb
        elif component == 'projection_pyramid':
            # Pyramid uses part of main budget (default 1/4)
            return self._component_budget.projection_cache_mb // 4
        
        return 0

    def get_modality_usage(self, modality_idx: int) -> Tuple[int, int]:
        """Get total memory usage for a modality.

        Returns:
            Tuple of (bytes_used, mb_used)
        """
        total_bytes = self._modality_bytes_main.get(modality_idx, 0) + self._modality_bytes_pyramid.get(
            modality_idx, 0
        )
        return total_bytes, total_bytes // (1024 * 1024)
