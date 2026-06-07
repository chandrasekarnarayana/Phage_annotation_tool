"""Split definitions from test_qc_state.py."""

from __future__ import annotations

from typing import List

import pytest

from phage_annotator.analysis.qc_validators import (
    QCIssue,
    IssueSeverity,
)
from phage_annotator.session.qc_state import QCState


from tests.unit.test_qc_state_split1 import sample_issues

@pytest.mark.order(2)
class TestQCStateEdgeCases:
    """Test edge cases in QC state."""
    
    def test_empty_filtered_results(self, sample_issues):
        """Test getting visible issues when all filtered out."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Filter everything
        state.set_filter("error", False)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        visible = state.get_visible_issues()
        assert len(visible) == 0
    
    def test_single_issue_state(self):
        """Test state with single issue."""
        issue = QCIssue(
            issue_id="single",
            severity=IssueSeverity.ERROR,
            issue_type="test",
            message="Test issue",
            image_id="img_001",
            affected_annotation_ids=["ann_1"],
            location_x=100,
            location_y=200,
            location_z=0,
            location_t=0,
        )
        
        state = QCState()
        state.add_issue(issue)
        
        assert len(state.issues) == 1
        assert len(state.get_visible_issues()) == 1
        assert len(state.get_affected_annotation_ids()) == 1
    
    def test_large_issue_set(self):
        """Test state with many issues."""
        state = QCState()
        
        # Add 100 issues
        for i in range(100):
            issue = QCIssue(
                issue_id=f"issue_{i:03d}",
                severity=[IssueSeverity.ERROR, IssueSeverity.WARNING, IssueSeverity.INFO][i % 3],
                issue_type=f"type_{i % 5}",
                message=f"Issue {i}",
                image_id="img_001",
                affected_annotation_ids=[f"ann_{i}"],
                location_x=i * 10,
                location_y=i * 10,
                location_z=0,
                location_t=0,
            )
            state.add_issue(issue)
        
        assert len(state.issues) == 100
        assert len(state.get_visible_issues()) == 100
        
        # Filter and check
        state.set_filter("error", False)
        visible = state.get_visible_issues()
        assert len(visible) == 100 - 34  # 100 // 3 = 33, but some rounding
    
    def test_issue_with_multiple_affected(self):
        """Test issue affecting many annotations."""
        affected_list = [f"ann_{i}" for i in range(50)]
        
        issue = QCIssue(
            issue_id="large_cluster",
            severity=IssueSeverity.WARNING,
            issue_type="density_cluster",
            message="Large cluster",
            image_id="img_001",
            affected_annotation_ids=affected_list,
            location_x=500,
            location_y=500,
            location_z=0,
            location_t=0,
        )
        
        state = QCState()
        state.add_issue(issue)
        
        affected = state.get_affected_annotation_ids()
        assert len(affected) == 50

@pytest.mark.order(2)
class TestQCStateIssueStatus:
    """Test issue status transitions (active/resolved/ignored)."""

    def test_resolve_issue_hides_from_visible(self, sample_issues):
        """Verify resolve issue hides from visible for the current workflow."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)

        assert state.resolve_issue("dup_001") is True
        assert state.get_issue_status("dup_001") == state.STATUS_RESOLVED

        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert all(issue.issue_id != "dup_001" for issue in visible)

    def test_ignore_issue_hides_from_visible(self, sample_issues):
        """Verify ignore issue hides from visible for the current workflow."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)

        assert state.ignore_issue("bound_001") is True
        assert state.get_issue_status("bound_001") == state.STATUS_IGNORED

        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert all(issue.issue_id != "bound_001" for issue in visible)

    def test_include_resolved_and_ignored_options(self, sample_issues):
        """Verify include resolved and ignored options for the current workflow."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)

        state.resolve_issue("dup_001")
        state.ignore_issue("bound_001")

        default_visible = state.get_visible_issues()
        assert len(default_visible) == 1

        include_all = state.get_visible_issues(include_resolved=True, include_ignored=True)
        assert len(include_all) == 3

    def test_order_by_severity(self):
        """Verify order by severity for the current workflow."""
        state = QCState()
        state.add_issue(
            QCIssue(
                issue_id="i_info",
                severity=IssueSeverity.INFO,
                issue_type="density_cluster",
                message="info",
                image_id="img_001",
                affected_annotation_ids=["ann_1"],
            )
        )
        state.add_issue(
            QCIssue(
                issue_id="i_error",
                severity=IssueSeverity.ERROR,
                issue_type="duplicate",
                message="error",
                image_id="img_001",
                affected_annotation_ids=["ann_2"],
            )
        )
        state.add_issue(
            QCIssue(
                issue_id="i_warning",
                severity=IssueSeverity.WARNING,
                issue_type="missing_label",
                message="warning",
                image_id="img_001",
                affected_annotation_ids=["ann_3"],
            )
        )

        ordered = state.get_visible_issues(order_by_severity=True)
        assert [issue.issue_id for issue in ordered] == ["i_error", "i_warning", "i_info"]
