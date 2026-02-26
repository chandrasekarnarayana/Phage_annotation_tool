"""ROI (Region of Interest) management (P3 refactoring).

Manages user-defined regions for analysis:
- ROI shape/size management
- Interactive ROI editor (matplotlib)
- ROI-based filtering and analysis
- Automatic ROI detection
"""

from phage_annotator.roi.manager import RoiManager, Roi

__all__ = [
    "RoiManager",
    "Roi",
]
