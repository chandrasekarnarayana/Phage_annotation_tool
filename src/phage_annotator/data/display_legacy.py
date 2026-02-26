"""Backward compatibility facade for display_mapping module.

Phase 2.5: This module has been moved to phage_annotator.data.display_mapping
This file re-exports symbols for backward compatibility.

New code should import from: phage_annotator.data.display_mapping
"""

from phage_annotator.data.display_mapping import (
    DisplayMapping,
    build_norm,
    mapping_from_dict,
    mapping_to_dict,
)

__all__ = ["DisplayMapping", "build_norm", "mapping_from_dict", "mapping_to_dict"]
