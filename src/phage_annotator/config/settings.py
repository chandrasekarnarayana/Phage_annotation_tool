"""Configuration helpers for phage-annotator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

from phage_annotator.core.rollout import DEFAULT_FEATURE_FLAGS

SUPPORTED_SUFFIXES: Tuple[str, ...] = (".tif", ".tiff", ".ome.tif", ".ome.tiff")


@dataclass
class ComponentMemoryBudget:
    """Per-component memory budget (P7e).
    
    Allows fine-grained control over different data components:
    - projection_cache: Computed mean/std/LOD projections
    - overlay_cache: Rendered overlay buffers
    - display_cache: Cached display/canvas buffers
    - inference_cache: Model inference results
    - disk_cache: Compressed evicted tiles on disk
    """
    
    projection_cache_mb: int = 512    # Projection arrays (primary budget)
    overlay_cache_mb: int = 256       # Overlay rendering buffers
    display_cache_mb: int = 128       # Canvas display caches
    inference_cache_mb: int = 256     # Model output caches
    disk_cache_mb: int = 500          # Disk cache for on-demand reloading
    
    def total_memory_mb(self) -> int:
        """Get total memory budget across all components."""
        return (self.projection_cache_mb + self.overlay_cache_mb +
                self.display_cache_mb + self.inference_cache_mb)
    
    def get_component_budget(self, component: str) -> int:
        """Get memory budget for specific component in MB.
        
        Args:
            component: One of 'projection', 'overlay', 'display', 'inference'
        
        Returns:
            Memory budget in MB for that component.
        """
        mapping = {
            'projection': self.projection_cache_mb,
            'overlay': self.overlay_cache_mb,
            'display': self.display_cache_mb,
            'inference': self.inference_cache_mb,
        }
        return mapping.get(component, 0)


@dataclass
class AppConfig:
    """Runtime settings for microscopy keypoint annotation."""

    pixel_size_nm: float = 1.0
    supported_suffixes: Tuple[str, ...] = SUPPORTED_SUFFIXES
    config_dir: Path = field(default_factory=lambda: Path.home() / ".phage_annotator")
    # P3.5: Default label classes for empty projects
    default_labels: Tuple[str, ...] = ("Point", "Region")
    # P3b: Adaptive tile sizing for memory pressure response
    adaptive_tile_size: int = 256  # Default inference tile size (512 normal, 256 pressure, 128 critical)
    # P6a: Disk cache for evicted tiles (fast re-browsing of distant FOVs)
    disk_cache_enabled: bool = True  # Enable/disable disk cache with Zstd compression
    disk_cache_size_mb: int = 500  # Max disk cache size in MB
    # P7c: FOV grid metadata for predictive prefetch
    fov_grid_cols: int = 0  # 0 = unknown/single image; >0 = FOV grid columns
    fov_grid_rows: int = 0  # 0 = unknown; >0 = FOV grid rows
    enable_fov_prefetch: bool = True  # Enable adjacent FOV prefetch (P7c)
    # P7e: Component-based memory budgeting
    component_budgets: ComponentMemoryBudget = field(default_factory=ComponentMemoryBudget)
    # Controlled rollout toggles for phased workflow/data migrations.
    feature_flags: Dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_FEATURE_FLAGS)
    )


DEFAULT_CONFIG = AppConfig()

__all__ = ["AppConfig", "DEFAULT_CONFIG", "SUPPORTED_SUFFIXES"]
