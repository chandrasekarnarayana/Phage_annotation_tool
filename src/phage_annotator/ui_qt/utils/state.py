"""View state mixin - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.utils.playback_controls import PlaybackControlsMixin
from phage_annotator.ui_qt.utils.state_cache import StateCacheMixin
from phage_annotator.ui_qt.utils.state_projection import StateProjectionMixin
from phage_annotator.ui_qt.utils.state_coords import StateCoordsMixin
from phage_annotator.ui_qt.utils.state_mixin_display import StateMixinDisplayMixin


class StateMixin(
    PlaybackControlsMixin,
    StateCacheMixin,
    StateProjectionMixin,
    StateCoordsMixin,
    StateMixinDisplayMixin,
):
    """Aggregated mixin for view state: properties, cache, projection, and coords."""
    pass
