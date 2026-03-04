"""QC issue state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity


@dataclass
class QCState:
    """State for QC issues and validation."""
    
    issues: List[QCIssue] = field(default_factory=list)
    validation_timestamp: Optional[float] = None
    auto_validate: bool = False  # Run validation after edits
    auto_monitor_enabled: bool = True  # Background monitoring active
    issue_status: Dict[str, str] = field(default_factory=dict)
    filters: Dict[str, bool] = field(default_factory=lambda: {
        "error": True,
        "warning": True,
        "info": True,  # All visible by default
    })
    monitor_debounce_ms: int = 2000  # Debounce interval for user changes (ms)
    monitor_periodic_ms: int = 10000  # Periodic full scan interval (ms)

    STATUS_ACTIVE = "active"
    STATUS_RESOLVED = "resolved"
    STATUS_IGNORED = "ignored"
    
    def add_issue(self, issue: QCIssue) -> None:
        """Add an issue to the state."""
        self.issues.append(issue)
        self.issue_status.setdefault(str(issue.issue_id), self.STATUS_ACTIVE)
    
    def clear_issues(self) -> None:
        """Clear all issues."""
        self.issues = []
        self.issue_status = {}

    def prune_issue_statuses(self) -> None:
        """Remove status entries for issues no longer present."""
        valid_ids = {str(issue.issue_id) for issue in self.issues}
        stale_ids = [issue_id for issue_id in self.issue_status if issue_id not in valid_ids]
        for issue_id in stale_ids:
            self.issue_status.pop(issue_id, None)

    def get_issue_status(self, issue_id: str) -> str:
        """Return issue state: active/resolved/ignored."""
        return str(self.issue_status.get(str(issue_id), self.STATUS_ACTIVE))

    def set_issue_status(self, issue_id: str, status: str) -> bool:
        """Update issue state.

        Returns True if the issue exists and status was updated.
        """
        normalized = str(status).lower().strip()
        if normalized not in {self.STATUS_ACTIVE, self.STATUS_RESOLVED, self.STATUS_IGNORED}:
            return False
        issue_key = str(issue_id)
        if not any(str(issue.issue_id) == issue_key for issue in self.issues):
            return False
        self.issue_status[issue_key] = normalized
        return True

    def resolve_issue(self, issue_id: str) -> bool:
        """Mark issue as resolved."""
        return self.set_issue_status(issue_id, self.STATUS_RESOLVED)

    def ignore_issue(self, issue_id: str) -> bool:
        """Mark issue as ignored."""
        return self.set_issue_status(issue_id, self.STATUS_IGNORED)

    def reset_issue(self, issue_id: str) -> bool:
        """Return issue to active status."""
        return self.set_issue_status(issue_id, self.STATUS_ACTIVE)
    
    def get_issues_by_severity(self, severity: IssueSeverity) -> List[QCIssue]:
        """Get issues filtered by severity."""
        return [i for i in self.issues if i.severity == severity]
    
    def get_visible_issues(
        self,
        respect_filters: bool = True,
        ignore_filters: bool = False,
        include_resolved: bool = False,
        include_ignored: bool = False,
        order_by_severity: bool = False,
    ) -> List[QCIssue]:
        """Get issues that pass current filters.
        
        Parameters
        ----------
        respect_filters : bool, default True
            Apply current filter settings to results.
        ignore_filters : bool, default False
            Ignore filter settings and return all issues (overrides respect_filters).
        
        Returns
        -------
        list of QCIssue
            Visible issues based on filtering.
        """
        issues = self.issues.copy()

        if not include_resolved:
            issues = [
                issue
                for issue in issues
                if self.get_issue_status(str(issue.issue_id)) != self.STATUS_RESOLVED
            ]
        if not include_ignored:
            issues = [
                issue
                for issue in issues
                if self.get_issue_status(str(issue.issue_id)) != self.STATUS_IGNORED
            ]

        if ignore_filters or not respect_filters:
            visible = issues
        else:
            visible = []
            for issue in issues:
                severity_key = issue.severity.value
                if self.filters.get(severity_key, True):
                    visible.append(issue)
        
        if order_by_severity:
            severity_order = {
                IssueSeverity.ERROR: 0,
                IssueSeverity.WARNING: 1,
                IssueSeverity.INFO: 2,
            }
            visible.sort(
                key=lambda issue: (
                    int(severity_order.get(issue.severity, 99)),
                    str(issue.issue_type),
                    str(issue.issue_id),
                )
            )
        return visible
    
    def set_filter(self, severity: str, visible: bool) -> None:
        """Toggle visibility of issues by severity."""
        valid_severities = ["error", "warning", "info"]
        if severity in valid_severities:
            self.filters[severity] = visible
    
    def get_affected_annotation_ids(self, respect_filters: bool = False) -> set:
        """Get all annotation IDs with issues.
        
        Parameters
        ----------
        respect_filters : bool, default False
            Only include IDs from visible issues (respecting filter settings).
        
        Returns
        -------
        set
            Set of affected annotation IDs.
        """
        issues_to_check = self.get_visible_issues(respect_filters=respect_filters) if respect_filters else self.issues
        ids = set()
        for issue in issues_to_check:
            ids.update(issue.affected_annotation_ids)
        return ids
