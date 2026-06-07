"""Split definitions from test_qc_export.py."""

from __future__ import annotations

import json
import tempfile
from csv import DictReader
from pathlib import Path
from typing import List

import pytest

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.io.qc_export import QCReportExporter


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
