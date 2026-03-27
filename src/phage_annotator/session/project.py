"""Project persistence compatibility shim.

This module keeps `SessionProjectMixin` as the public import path while
delegating implementation to focused project persistence mixins.
"""

from __future__ import annotations

from phage_annotator.session.project_bridge import SessionProjectBridgeMixin
from phage_annotator.session.project_export import SessionProjectExportMixin
from phage_annotator.session.project_persistence import SessionProjectPersistenceMixin
from phage_annotator.session.project_recovery import SessionProjectRecoveryMixin


class SessionProjectMixin(
    SessionProjectExportMixin,
    SessionProjectPersistenceMixin,
    SessionProjectRecoveryMixin,
    SessionProjectBridgeMixin,
):
    """Compatibility shim aggregating project persistence, bridge, and recovery mixins."""

    pass
