"""Eviction internals for ProjectionCache."""

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

class ProjectionCacheEvictionMixin:
    def _modality_overages(self) -> dict[int, int]:
        """Document the modality_overages flow."""
        per_modality_budget = self._max_bytes // self._modality_count
        overages: dict[int, int] = {}
        for modality_idx in set(self._modality_bytes_main) | set(self._modality_bytes_pyramid):
            bytes_used = self._modality_bytes_main.get(modality_idx, 0) + self._modality_bytes_pyramid.get(
                modality_idx, 0
            )
            over = bytes_used - per_modality_budget
            if over > 0:
                overages[modality_idx] = over
        return overages

    def _pop_lru_for_modality(self, items: OrderedDict, modality_idx: int) -> Optional[Tuple[tuple, CacheItem]]:
        """Document the pop_lru_for_modality flow."""
        for key in list(items.keys()):
            if int(key[-1]) == modality_idx:
                item = items.pop(key)
                return key, item
        return None

    def _evict_if_needed(self) -> None:
        """Evict least-recently-used items until within budget.
        
        P6: Save evicted items to disk cache before discarding.
        """
        # Check for 90% budget threshold and warn
        if not self._telemetry.warning_at_90_percent_issued:
            percent = (self._total_bytes / self._max_bytes * 100) if self._max_bytes > 0 else 0
            if percent >= 90:
                self._telemetry.warning_at_90_percent_issued = True
                mb_used = int(math.ceil(self._total_bytes / (1024 * 1024)))
                mb_budget = int(self._max_bytes / (1024 * 1024))
                
                msg = f"Cache at {percent:.1f}% of budget ({mb_used}/{mb_budget} MB)"
                logger.warning(f"Cache eviction telemetry: {msg}")
                
                # Trigger toast notification if callback is set
                if self._warning_callback:
                    try:
                        self._warning_callback(msg)
                    except Exception as e:
                        logger.debug(f"Warning callback error: {e}")
        
        # Evict until within budget, tracking per-cycle evictions
        while (self._total_bytes > self._max_bytes or self._modality_overages()) and (
            self._pyramid_items or self._items
        ):
            overages = self._modality_overages()
            modality_idx = max(overages, key=lambda idx: overages[idx]) if overages else None

            # Evict from pyramid first, but prefer the most over-budget modality if available.
            if self._pyramid_items:
                if modality_idx is not None:
                    popped = self._pop_lru_for_modality(self._pyramid_items, modality_idx)
                else:
                    popped = None
                if popped is None:
                    popped = self._pyramid_items.popitem(last=False)
                key, item = popped
                self._total_bytes -= item.nbytes
                self._component_bytes['projection_pyramid'] -= item.nbytes
                modality_key = int(key[-1])
                self._modality_bytes_pyramid[modality_key] = (
                    self._modality_bytes_pyramid.get(modality_key, 0) - item.nbytes
                )
                self._telemetry.pyramid_evictions += 1
                self._telemetry.evictions_this_cycle += 1
                self._telemetry.bytes_evicted += item.nbytes
                if self._disk_cache:
                    self._disk_cache.save(key, item.data)
                continue

            if self._items:
                if modality_idx is not None:
                    popped = self._pop_lru_for_modality(self._items, modality_idx)
                else:
                    popped = None
                if popped is None:
                    popped = self._items.popitem(last=False)
                key, item = popped
                self._total_bytes -= item.nbytes
                self._component_bytes['projection_main'] -= item.nbytes
                modality_key = int(key[-1])
                self._modality_bytes_main[modality_key] = (
                    self._modality_bytes_main.get(modality_key, 0) - item.nbytes
                )
                self._telemetry.evictions += 1
                self._telemetry.evictions_this_cycle += 1
                self._telemetry.bytes_evicted += item.nbytes
                if self._disk_cache:
                    self._disk_cache.save(key, item.data)
                continue
        
        # Log eviction summary if needed
        if self._telemetry.evictions > 0 or self._telemetry.pyramid_evictions > 0:
            mb_reclaimed = int(math.ceil(self._telemetry.bytes_evicted / (1024 * 1024)))
            logger.debug(
                f"Cache evicted {self._telemetry.evictions} items + "
                f"{self._telemetry.pyramid_evictions} pyramid levels, "
                f"reclaimed {mb_reclaimed} MB"
            )
