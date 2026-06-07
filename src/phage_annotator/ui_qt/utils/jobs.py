"""Background job wiring for the GUI."""

from __future__ import annotations

from phage_annotator.ui_qt.utils.job_management import JobManagementMixin
from phage_annotator.ui_qt.utils.job_lifecycle import JobLifecycleMixin


class JobsMixin(JobManagementMixin, JobLifecycleMixin):
    """Aggregated mixin for job management and lifecycle."""
    pass
