"""Unit tests for QC export functionality."""

from __future__ import annotations

import json
import tempfile
from csv import DictReader
from pathlib import Path
from typing import List

import pytest

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.io.qc_export import QCReportExporter


@pytest.fixture
def sample_issues() -> List[QCIssue]:
    """Create sample QC issues for testing."""
    return [
        QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate annotations at (100, 200)",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=5,
            location_t=10,
        ),
        QCIssue(
            issue_id="bound_001",
            severity=IssueSeverity.WARNING,
            issue_type="out_of_bounds",
            message="Annotation outside image bounds",
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
            message="Annotation has no label",
            image_id="img_001",
            affected_annotation_ids=["ann_4"],
            location_x=150,
            location_y=250,
            location_z=3,
            location_t=5,
        ),
    ]


@pytest.mark.order(1)
class TestQCReportExporter:
    """Test QC report export functionality."""
    
    def test_export_csv_success(self, sample_issues):
        """Test successful CSV export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.csv"
            
            result = QCReportExporter.export_csv(sample_issues, output_path)
            
            assert result is True
            assert output_path.exists()
            
            # Verify CSV content
            with open(output_path) as f:
                reader = DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 3
            assert rows[0]['issue_id'] == "dup_001"
            assert rows[0]['severity'] == "error"
            assert rows[0]['issue_type'] == "duplicate"
            assert rows[1]['severity'] == "warning"
            assert rows[2]['severity'] == "info"
    
    def test_export_csv_affected_annotations(self, sample_issues):
        """Test that affected annotations are properly exported to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.csv"
            QCReportExporter.export_csv(sample_issues, output_path)
            
            with open(output_path) as f:
                reader = DictReader(f)
                rows = list(reader)
            
            # Check that annotations are comma-separated
            assert rows[0]['affected_annotations'] == "ann_1,ann_2"
            assert rows[1]['affected_annotations'] == "ann_3"
            assert rows[2]['affected_annotations'] == "ann_4"
    
    def test_export_csv_empty_issues(self):
        """Test CSV export with no issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.csv"
            
            result = QCReportExporter.export_csv([], output_path)
            
            assert result is True
            assert output_path.exists()
            
            # Should have header but no data rows
            with open(output_path) as f:
                reader = DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 0
    
    def test_export_json_success(self, sample_issues):
        """Test successful JSON export with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            
            result = QCReportExporter.export_json(sample_issues, output_path)
            
            assert result is True
            assert output_path.exists()
            
            # Verify JSON content
            with open(output_path) as f:
                data = json.load(f)
            
            assert 'metadata' in data
            assert 'issues' in data
            assert data['metadata']['total_issues'] == 3
    
    def test_export_json_severity_counts(self, sample_issues):
        """Test that severity counts are correct in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            QCReportExporter.export_json(sample_issues, output_path)
            
            with open(output_path) as f:
                data = json.load(f)
            
            severity_counts = data['metadata']['by_severity']
            assert severity_counts['error'] == 1
            assert severity_counts['warning'] == 1
            assert severity_counts['info'] == 1
    
    def test_export_json_type_counts(self, sample_issues):
        """Test that issue type counts are correct in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            QCReportExporter.export_json(sample_issues, output_path)
            
            with open(output_path) as f:
                data = json.load(f)
            
            type_counts = data['metadata']['by_type']
            assert type_counts['duplicate'] == 1
            assert type_counts['out_of_bounds'] == 1
            assert type_counts['missing_label'] == 1
    
    def test_export_json_location_data(self, sample_issues):
        """Test that location data is properly exported in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            QCReportExporter.export_json(sample_issues, output_path)
            
            with open(output_path) as f:
                data = json.load(f)
            
            issue = data['issues'][0]
            assert issue['location']['x'] == 100
            assert issue['location']['y'] == 200
            assert issue['location']['z'] == 5
            assert issue['location']['t'] == 10
    
    def test_export_json_empty_issues(self):
        """Test JSON export with no issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            
            result = QCReportExporter.export_json([], output_path)
            
            assert result is True
            
            with open(output_path) as f:
                data = json.load(f)
            
            assert data['metadata']['total_issues'] == 0
            assert len(data['issues']) == 0
    
    def test_export_json_without_metadata(self, sample_issues):
        """Test JSON export without metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            
            result = QCReportExporter.export_json(
                sample_issues, output_path, include_metadata=False
            )
            
            assert result is True
            
            with open(output_path) as f:
                data = json.load(f)
            
            assert 'metadata' not in data
            assert 'issues' in data
            assert len(data['issues']) == 3
    
    def test_export_html_report_success(self, sample_issues):
        """Test successful HTML report export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            
            result = QCReportExporter.export_html_report(
                sample_issues, output_path, project_name="Test Project"
            )
            
            assert result is True
            assert output_path.exists()
            
            # Verify HTML content
            html_content = output_path.read_text()
            assert "Test Project" in html_content
            assert "<!DOCTYPE html>" in html_content
            assert "3" in html_content  # Check for issue count
    
    def test_export_html_report_statistics(self, sample_issues):
        """Test that HTML report contains correct statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            QCReportExporter.export_html_report(sample_issues, output_path)
            
            html_content = output_path.read_text()
            assert "3" in html_content
            assert "1" in html_content
    
    def test_export_html_report_tables(self, sample_issues):
        """Test that HTML report contains issue tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            QCReportExporter.export_html_report(sample_issues, output_path)
            
            html_content = output_path.read_text()
            
            # Check for tables
            assert "<table>" in html_content
            assert "duplicate" in html_content.lower()  # Case-insensitive
            
            # Check for issue data
            assert "Duplicate" in html_content
    
    def test_export_html_report_severity_styling(self, sample_issues):
        """Test that HTML report has severity styling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            QCReportExporter.export_html_report(sample_issues, output_path)
            
            html_content = output_path.read_text()
            
            # Check for severity classes
            assert "class='error'" in html_content
            assert "class='warning'" in html_content
            assert "class='info'" in html_content
    
    def test_export_html_report_empty_issues(self):
        """Test HTML report export with no issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            
            result = QCReportExporter.export_html_report([], output_path)
            
            assert result is True
            
            html_content = output_path.read_text()
            assert "0" in html_content
    
    def test_export_invalid_path(self, sample_issues):
        """Test export with invalid path."""
        # Use a path in a non-existent directory
        invalid_path = Path("/this/path/does/not/exist/report.csv")
        
        result = QCReportExporter.export_csv(sample_issues, invalid_path)
        
        # Should return False on error
        assert result is False
    
    def test_export_csv_json_consistency(self, sample_issues):
        """Test that CSV and JSON exports contain same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "report.csv"
            json_path = Path(tmpdir) / "report.json"
            
            QCReportExporter.export_csv(sample_issues, csv_path)
            QCReportExporter.export_json(sample_issues, json_path)
            
            # Read both
            with open(csv_path) as f:
                csv_rows = list(DictReader(f))
            
            with open(json_path) as f:
                json_data = json.load(f)
            
            # Check counts match
            assert len(csv_rows) == len(json_data['issues'])
            
            # Check first issue matches
            assert csv_rows[0]['issue_id'] == json_data['issues'][0]['issue_id']
            assert csv_rows[0]['severity'] == json_data['issues'][0]['severity']


@pytest.mark.order(2)
class TestQCExportIntegration:
    """Test QC export integration scenarios."""
    
    def test_export_multiple_same_type(self):
        """Test export with multiple issues of same type."""
        issues = [
            QCIssue(
                issue_id=f"dup_{i:03d}",
                severity=IssueSeverity.ERROR,
                issue_type="duplicate",
                message=f"Duplicate at ({100 + i*10}, {200 + i*10})",
                image_id="img_001",
                affected_annotation_ids=[f"ann_{i}", f"ann_{i+1}"],
                location_x=100 + i*10,
                location_y=200 + i*10,
                location_z=0,
                location_t=0,
            )
            for i in range(5)
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            QCReportExporter.export_json(issues, json_path)
            
            with open(json_path) as f:
                data = json.load(f)
            
            # Should have 5 duplicates
            assert data['metadata']['by_type']['duplicate'] == 5
            assert len(data['issues']) == 5
    
    def test_export_large_annotation_list(self):
        """Test export with issue affecting many annotations."""
        affected = [f"ann_{i}" for i in range(100)]
        
        issue = QCIssue(
            issue_id="cluster_001",
            severity=IssueSeverity.WARNING,
            issue_type="density_cluster",
            message="High density cluster with 100 annotations",
            image_id="img_001",
            affected_annotation_ids=affected,
            location_x=500,
            location_y=500,
            location_z=0,
            location_t=0,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "report.csv"
            json_path = Path(tmpdir) / "report.json"
            
            QCReportExporter.export_csv([issue], csv_path)
            QCReportExporter.export_json([issue], json_path)
            
            # CSV should have comma-separated list
            with open(csv_path) as f:
                rows = list(DictReader(f))
                assert len(rows[0]['affected_annotations'].split(',')) == 100
            
            # JSON should preserve list
            with open(json_path) as f:
                data = json.load(f)
                assert len(data['issues'][0]['affected_annotation_ids']) == 100
