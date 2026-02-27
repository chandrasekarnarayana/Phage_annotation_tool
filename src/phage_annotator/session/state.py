"""Backward compatibility facade for session state models.

This module has been moved to phage_annotator.core.session_state.
"""

from phage_annotator.core.session_state import ImageState, RoiSpec, SessionState, ViewState

__all__ = ["ImageState", "RoiSpec", "SessionState", "ViewState"]
