"""QC thresholds and sensitivity configuration.

Centralizes all quality control parameter tuning with sensible defaults
and logical grouping by validation type.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from typing import Dict, Any, Optional


@dataclass
class QCThresholds:
    """
    Centralized QC parameter configuration.
    
    Organized into logical groups:
    1. Annotation Spatial Constraints
    2. Image Quality (Artifacts)
    3. Statistical (Stochasticity)
    """
    
    # ==================== ANNOTATION SPATIAL CONSTRAINTS ====================
    
    # Duplicate Detection
    duplicate_distance_px: float = 2.0
    """Maximum distance (pixels) below which annotations are duplicates."""
    
    # Boundary Constraints
    border_safety_margin_px: float = 0.0
    """Minimum distance from image edge (pixels). Warns if annotation closer."""
    
    # Density Clustering
    density_grid_size_px: float = 50.0
    """Grid cell size (pixels) for density analysis. Smaller = finer granularity."""
    
    density_min_annotations: int = 5
    """Minimum annotations in grid cell to flag as high-density cluster."""
    
    # ==================== IMAGE QUALITY (ARTIFACTS) ====================
    
    # Illumination
    illumination_ratio_min: float = 0.80
    """Minimum allowed center/border intensity ratio. Below = dark edges."""
    
    illumination_ratio_max: float = 1.25
    """Maximum allowed center/border intensity ratio. Above = bright center."""
    
    # Photobleaching
    photobleaching_drop_percent: float = 15.0
    """Maximum allowed intensity drop (%) over frames. Above = suspicious."""
    
    # Dust/Lens Artifacts
    dust_min_pixels: int = 20
    """Minimum persistent artifact pixels to flag. Fewer = no detection."""
    
    dust_percent_image: float = 0.05
    """Percent of image size for dynamic dust detection (0.05 = 0.05%)."""
    
    # Patterned Intensity (Banding)
    patterned_band_strength: float = 0.18
    """Maximum normalized band strength (row/col std / frame std). Above = warning."""
    
    # Clustered Bright Signal
    clustered_signal_peak_count: int = 50
    """Minimum bright pixel count in dominant cell. Below = no detection."""
    
    clustered_signal_ratio: float = 4.0
    """Multiplier for peak vs mean bright cell count. Above = clustered."""
    
    # ==================== STATISTICAL (STOCHASTICITY) ====================
    
    # Image Signal Fano-factor (variance/mean)
    image_fano_min: float = 0.6
    """Minimum allowed Fano-factor for image signal. Below = non-Poisson."""
    
    image_fano_max: float = 1.8
    """Maximum allowed Fano-factor for image signal. Above = non-Poisson."""
    
    image_fano_warning_threshold: float = 3.0
    """Fano-factor above this is WARNING (Info if below this)."""
    
    # Annotation Spatial Fano-factor
    annotation_fano_min: float = 0.5
    """Minimum allowed Fano-factor for annotation density. Below = clustered."""
    
    annotation_fano_max: float = 2.5
    """Maximum allowed Fano-factor for annotation density. Above = dispersed."""
    
    annotation_fano_warning_threshold: float = 2.5
    """Fano-factor above/below thresholds is WARNING severity."""
    
    # ==================== ENABLE/DISABLE CHECKS ====================
    
    enabled_duplicate_check: bool = True
    """Enable duplicate annotation detection."""
    
    enabled_bounds_check: bool = True
    """Enable out-of-bounds detection."""
    
    enabled_label_check: bool = True
    """Enable missing/invalid label detection."""
    
    enabled_density_check: bool = True
    """Enable high-density cluster detection."""
    
    enabled_illumination_check: bool = True
    """Enable uneven illumination detection."""
    
    enabled_photobleaching_check: bool = True
    """Enable photobleaching detection."""
    
    enabled_dust_check: bool = True
    """Enable dust/lens artifact detection."""
    
    enabled_patterned_check: bool = True
    """Enable patterned intensity detection."""
    
    enabled_clustered_signal_check: bool = True
    """Enable clustered signal detection."""
    
    enabled_image_fano_check: bool = True
    """Enable image signal stochasticity check."""
    
    enabled_annotation_fano_check: bool = True
    """Enable annotation stochasticity check."""
    
    # ==================== SENSITIVITY PROFILES ====================
    
    @classmethod
    def strict_profile(cls) -> QCThresholds:
        """Strict validation profile - flags more issues."""
        config = cls()
        # Tighter thresholds
        config.duplicate_distance_px = 3.0
        config.border_safety_margin_px = 5.0
        config.density_min_annotations = 3
        config.illumination_ratio_min = 0.90
        config.illumination_ratio_max = 1.15
        config.photobleaching_drop_percent = 10.0
        config.patterned_band_strength = 0.10
        return config
    
    @classmethod
    def relaxed_profile(cls) -> QCThresholds:
        """Relaxed validation profile - flags fewer issues."""
        config = cls()
        # Looser thresholds
        config.duplicate_distance_px = 1.0
        config.border_safety_margin_px = 0.0
        config.density_min_annotations = 8
        config.illumination_ratio_min = 0.70
        config.illumination_ratio_max = 1.40
        config.photobleaching_drop_percent = 25.0
        config.patterned_band_strength = 0.25
        return config
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QCThresholds:
        """Create config from dictionary (e.g., from settings)."""
        # Filter to only known fields
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return asdict(self)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get parameters for a specific section.
        
        Parameters
        ----------
        section : str
            One of: 'spatial', 'artifacts', 'stochasticity', 'enable'
        
        Returns
        -------
        dict
            Parameters in that section.
        """
        all_params = self.to_dict()
        
        if section == 'spatial':
            return {k: v for k, v in all_params.items() 
                    if k.startswith(('duplicate_', 'border_', 'density_'))}
        elif section == 'artifacts':
            return {k: v for k, v in all_params.items()
                    if k.startswith(('illumination_', 'photobleaching_', 
                                     'dust_', 'patterned_', 'clustered_'))}
        elif section == 'stochasticity':
            return {k: v for k, v in all_params.items()
                    if k.startswith(('image_fano_', 'annotation_fano_'))}
        elif section == 'enable':
            return {k: v for k, v in all_params.items()
                    if k.startswith('enabled_')}
        else:
            return {}
    
    @property
    def summary(self) -> str:
        """Human-readable summary of key thresholds."""
        return (
            f"QC Thresholds:\n"
            f"  Duplicates: {self.duplicate_distance_px}px\n"
            f"  Border margin: {self.border_safety_margin_px}px\n"
            f"  Density cluster: {self.density_min_annotations} in {self.density_grid_size_px}px grid\n"
            f"  Illumination ratio: {self.illumination_ratio_min:.2f}-{self.illumination_ratio_max:.2f}\n"
            f"  Photobleaching drop: >{self.photobleaching_drop_percent}%\n"
            f"  Patterned band: >{self.patterned_band_strength:.2f}\n"
            f"  Image Fano factor: [{self.image_fano_min:.2f}, {self.image_fano_max:.2f}]\n"
            f"  Annotation Fano factor: [{self.annotation_fano_min:.2f}, {self.annotation_fano_max:.2f}]"
        )


# Singleton default instance
_default_thresholds: Optional[QCThresholds] = None


def get_default_thresholds() -> QCThresholds:
    """Get or create default thresholds instance."""
    global _default_thresholds
    if _default_thresholds is None:
        _default_thresholds = QCThresholds()
    return _default_thresholds


def set_default_thresholds(config: QCThresholds) -> None:
    """Set global default thresholds."""
    global _default_thresholds
    _default_thresholds = config
