"""Unit tests for QC state management."""

from __future__ import annotations

from typing import List

import pytest

from phage_annotator.analysis.qc_validators import (
    QCIssue,
    IssueSeverity,
)
from phage_annotator.session.qc_state import QCState


@pytest.fixture
def sample_issues() -> List[QCIssue]:
    """Create sample QC issues for testing."""
    return [
        QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate annotations",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=0,
            location_t=0,
        ),
        QCIssue(
            issue_id="bound_001",
            severity=IssueSeverity.WARNING,
            issue_type="out_of_bounds",
            message="Out of bounds",
            image_id="img_001",
            affected_annotation_ids=["ann_3"],
            location_x=2000,
            location_y=2000,
            location_z=0,
            location_t=0,
        ),
        QCIssue(
            issue_id="label_001",
            severity=IssueSeverity.INFO,
            issue_type="missing_label",
            message="Missing label",
            image_id="img_001",
            affected_annotation_ids=["ann_4"],
            location_x=150,
            location_y=250,
            location_z=0,
            location_t=0,
        ),
    ]


@pytest.mark.order(1)
class TestQCStateBasics:
    """Test basic QC state functionality."""
    
    def test_create_empty_state(self):
        """Test creating an empty QC state."""
        state = QCState()
        
        assert state.issues == []
        assert state.validation_timestamp is None
        assert state.auto_validate is False
        assert state.filters is not None
    
    def test_add_issues(self, sample_issues):
        """Test adding issues to state."""
        state = QCState()
        
        for issue in sample_issues:
            state.add_issue(issue)
        
        assert len(state.issues) == 3
        assert state.issues[0].issue_id == "dup_001"
    
    def test_clear_issues(self, sample_issues):
        """Test clearing all issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        assert len(state.issues) == 3
        
        state.clear_issues()
        
        assert len(state.issues) == 0
    
    def test_duplicate_issue_ids(self, sample_issues):
        """Test that duplicate issue IDs are handled."""
        state = QCState()
        
        # Add first issue
        state.add_issue(sample_issues[0])
        assert len(state.issues) == 1
        
        # Add same issue again (by ID)
        state.add_issue(sample_issues[0])
        
        # Should allow duplicates (depends on UI layer to prevent)
        assert len(state.issues) == 2


@pytest.mark.order(1)
class TestQCStateFiltering:
    """Test QC state filtering functionality."""
    
    def test_default_filters(self):
        """Test default filter state."""
        state = QCState()
        
        # All filters should be enabled by default
        assert state.filters.get("error", True) is True
        assert state.filters.get("warning", True) is True
        assert state.filters.get("info", True) is True
    
    def test_set_filter(self):
        """Test setting individual filters."""
        state = QCState()
        
        state.set_filter("error", False)
        assert state.filters["error"] is False
        
        state.set_filter("warning", False)
        assert state.filters["warning"] is False
        
        state.set_filter("error", True)
        assert state.filters["error"] is True
    
    def test_get_visible_issues(self, sample_issues):
        """Test filtering visible issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # With all filters enabled, should see all
        visible = state.get_visible_issues()
        assert len(visible) == 3
        
        # Disable errors
        state.set_filter("error", False)
        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert not any(i.severity == IssueSeverity.ERROR for i in visible)
        
        # Disable warnings too
        state.set_filter("warning", False)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert all(i.severity == IssueSeverity.INFO for i in visible)
    
    def test_toggle_all_filters(self, sample_issues):
        """Test toggling all filters at once."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable all
        state.set_filter("error", False)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        visible = state.get_visible_issues()
        assert len(visible) == 0
        
        # Re-enable all
        state.set_filter("error", True)
        state.set_filter("warning", True)
        state.set_filter("info", True)
        
        visible = state.get_visible_issues()
        assert len(visible) == 3
    
    def test_filter_isolated_severity(self, sample_issues):
        """Test filtering to single severity level."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Show only errors
        state.set_filter("error", True)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].severity == IssueSeverity.ERROR


@pytest.mark.order(1)
class TestQCStateAffectedAnnotations:
    """Test affected annotation tracking."""
    
    def test_get_affected_annotation_ids(self, sample_issues):
        """Test retrieving all affected annotation IDs."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        affected = state.get_affected_annotation_ids()
        
        # Should have union of all affected IDs
        assert "ann_1" in affected
        assert "ann_2" in affected
        assert "ann_3" in affected
        assert "ann_4" in affected
        assert len(affected) == 4
    
    def test_affected_ids_with_filtering(self, sample_issues):
        """Test affected IDs respects filtering."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable errors
        state.set_filter("error", False)
        
        affected = state.get_affected_annotation_ids(respect_filters=True)
        
        # ann_1 and ann_2 are from error issue
        assert "ann_1" not in affected
        assert "ann_2" not in affected
        # These should still be present
        assert "ann_3" in affected
        assert "ann_4" in affected
    
    def test_affected_ids_ignore_filtering(self, sample_issues):
        """Test that affected IDs can ignore filtering."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable all filters
        state.set_filter("error", False)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        # With respect_filters=False, should still get all
        affected = state.get_affected_annotation_ids(respect_filters=False)
        assert len(affected) == 4
        
        # With respect_filters=True, should get none
        affected = state.get_affected_annotation_ids(respect_filters=True)
        assert len(affected) == 0
    
    def test_overlapping_affected_ids(self):
        """Test with overlapping affected annotations."""
        issue1 = QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=0,
            location_t=0,
        )
        
        issue2 = QCIssue(
            issue_id="dup_002",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate",
            image_id="img_001",
            affected_annotation_ids=["ann_2", "ann_3"],  # Overlaps with issue1
            location_x=150,
            location_y=250,
            location_z=0,
            location_t=0,
        )
        
        state = QCState()
        state.add_issue(issue1)
        state.add_issue(issue2)
        
        affected = state.get_affected_annotation_ids()
        
        # Should have unique union
        assert len(affected) == 3
        assert affected == {"ann_1", "ann_2", "ann_3"}


@pytest.mark.order(1)
class TestQCStateAutomaticValidation:
    """Test automatic validation control."""
    
    def test_auto_validate_flag(self):
        """Test auto_validate flag."""
        state = QCState()
        
        assert state.auto_validate is False
        
        state.auto_validate = True
        assert state.auto_validate is True
    
    def test_validation_timestamp(self):
        """Test validation timestamp tracking."""
        state = QCState()
        
        assert state.validation_timestamp is None
        
        from datetime import datetime
        now = datetime.now()
        state.validation_timestamp = now
        
        assert state.validation_timestamp == now


@pytest.mark.order(2)
class TestQCStateWorkflows:
    """Test QC state in realistic workflows."""
    
    def test_review_workflow(self, sample_issues):
        """Test typical reviewer workflow."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Step 1: Reviewer starts, sees all issues
        assert len(state.get_visible_issues()) == 3
        
        # Step 2: Focus on errors first
        state.set_filter("warning", False)
        state.set_filter("info", False)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "duplicate"
        
        # Step 3: After dealing with errors, look at warnings
        state.set_filter("error", False)
        state.set_filter("warning", True)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "out_of_bounds"
        
        # Step 4: Review info messages
        state.set_filter("warning", False)
        state.set_filter("info", True)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "missing_label"
    
    def test_export_report_workflow(self, sample_issues):
        """Test workflow for generating report."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Get all issues regardless of filter state
        report_issues = state.get_visible_issues(ignore_filters=True)
        assert len(report_issues) == 3
        
        # Count by severity
        error_count = sum(1 for i in report_issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in report_issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in report_issues if i.severity == IssueSeverity.INFO)
        
        assert error_count == 1
        assert warning_count == 1
        assert info_count == 1
    
    def test_batch_fix_workflow(self, sample_issues):
        """Test workflow for batch fixing issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Get all annotations that need attention
        affected = state.get_affected_annotation_ids(respect_filters=False)
        assert len(affected) == 4
        
        # Simulate fixing some annotations
        # Clear and add back only remaining issues
        remaining_issues = [issue for issue in sample_issues if "ann_1" not in issue.affected_annotation_ids]
        
        state.clear_issues()
        for issue in remaining_issues:
            state.add_issue(issue)
        
        affected = state.get_affected_annotation_ids()
        assert "ann_1" not in affected
        assert len(affected) == 2  # ann_3 and ann_4


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
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)

        assert state.resolve_issue("dup_001") is True
        assert state.get_issue_status("dup_001") == state.STATUS_RESOLVED

        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert all(issue.issue_id != "dup_001" for issue in visible)

    def test_ignore_issue_hides_from_visible(self, sample_issues):
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)

        assert state.ignore_issue("bound_001") is True
        assert state.get_issue_status("bound_001") == state.STATUS_IGNORED

        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert all(issue.issue_id != "bound_001" for issue in visible)

    def test_include_resolved_and_ignored_options(self, sample_issues):
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
