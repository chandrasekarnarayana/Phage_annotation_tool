"""Utils dock panel init helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.

Compatibility imports for split chunk modules.
"""

from phage_annotator.ui_qt.utils.dock_panel_init_chunk1 import init_panels, get_panel_spec, get_dock
from phage_annotator.ui_qt.utils.dock_panel_init_chunk2 import _apply_panel_constraints, _canonical_area_for_panel, _tabify_group_for_panel
