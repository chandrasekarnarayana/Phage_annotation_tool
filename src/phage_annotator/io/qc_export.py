"""QC report export functionality."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity


class QCReportExporter:
    """Export QC issues to various formats."""
    
    @staticmethod
    def export_csv(
        issues: List[QCIssue],
        output_path: Path,
    ) -> bool:
        """Export issues as CSV file.
        
        Parameters
        ----------
        issues : list of QCIssue
            Issues to export.
        output_path : Path
            Output file path.
        
        Returns
        -------
        bool
            True if export successful.
        """
        try:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        'issue_id', 'severity', 'issue_type', 'message',
                        'image_id', 'affected_annotations', 'location_x', 'location_y'
                    ],
                )
                writer.writeheader()
                
                for issue in issues:
                    writer.writerow({
                        'issue_id': issue.issue_id,
                        'severity': issue.severity.value,
                        'issue_type': issue.issue_type,
                        'message': issue.message,
                        'image_id': issue.image_id,
                        'affected_annotations': ','.join(issue.affected_annotation_ids),
                        'location_x': issue.location_x,
                        'location_y': issue.location_y,
                    })
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def export_json(
        issues: List[QCIssue],
        output_path: Path,
        include_metadata: bool = True,
    ) -> bool:
        """Export issues as JSON file.
        
        Parameters
        ----------
        issues : list of QCIssue
            Issues to export.
        output_path : Path
            Output file path.
        include_metadata : bool, default True
            Include export timestamp and summary statistics.
        
        Returns
        -------
        bool
            True if export successful.
        """
        try:
            data = {}
            
            if include_metadata:
                # Count by severity
                severity_counts = {}
                for severity in IssueSeverity:
                    count = sum(1 for i in issues if i.severity == severity)
                    severity_counts[severity.value] = count
                
                data['metadata'] = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_issues': len(issues),
                    'by_severity': severity_counts,
                    'by_type': {},
                }
                
                # Count by type
                type_counts = {}
                for issue in issues:
                    type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1
                data['metadata']['by_type'] = type_counts
            
            # Export issues
            data['issues'] = [
                {
                    'issue_id': issue.issue_id,
                    'severity': issue.severity.value,
                    'issue_type': issue.issue_type,
                    'message': issue.message,
                    'image_id': issue.image_id,
                    'affected_annotation_ids': issue.affected_annotation_ids,
                    'location': {
                        'x': issue.location_x,
                        'y': issue.location_y,
                        'z': issue.location_z,
                        't': issue.location_t,
                    },
                }
                for issue in issues
            ]
            
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def export_html_report(
        issues: List[QCIssue],
        output_path: Path,
        project_name: str = "QC Report",
    ) -> bool:
        """Export issues as HTML report.
        
        Parameters
        ----------
        issues : list of QCIssue
            Issues to export.
        output_path : Path
            Output file path.
        project_name : str, default "QC Report"
            Title for the report.
        
        Returns
        -------
        bool
            True if export successful.
        """
        try:
            # Count statistics
            total = len(issues)
            errors = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
            warnings = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
            infos = sum(1 for i in issues if i.severity == IssueSeverity.INFO)
            
            # Group by type
            by_type = {}
            for issue in issues:
                if issue.issue_type not in by_type:
                    by_type[issue.issue_type] = []
                by_type[issue.issue_type].append(issue)
            
            html_parts = [
                f"<!DOCTYPE html>",
                f"<html>",
                f"<head>",
                f"  <title>{project_name}</title>",
                f"  <style>",
                f"    body {{ font-family: Arial, sans-serif; margin: 20px; }}",
                f"    h1 {{ color: #333; }}",
                f"    .summary {{ margin: 20px 0; padding: 10px; background: #f0f0f0; border-radius: 5px; }}",
                f"    .error {{ color: #d32f2f; font-weight: bold; }}",
                f"    .warning {{ color: #f57c00; }}",
                f"    .info {{ color: #0277bd; }}",
                f"    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}",
                f"    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}",
                f"    th {{ background-color: #4CAF50; color: white; }}",
                f"  </style>",
                f"</head>",
                f"<body>",
                f"  <h1>{project_name}</h1>",
                f"  <div class='summary'>",
                f"    <p><strong>Total Issues:</strong> {total}</p>",
                f"    <p><strong>Errors:</strong> <span class='error'>{errors}</span></p>",
                f"    <p><strong>Warnings:</strong> <span class='warning'>{warnings}</span></p>",
                f"    <p><strong>Info:</strong> <span class='info'>{infos}</span></p>",
                f"    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
                f"  </div>",
            ]
            
            # Add tables by issue type
            for issue_type, type_issues in sorted(by_type.items()):
                html_parts.append(f"  <h2>{issue_type.title()}</h2>")
                html_parts.append(f"  <table>")
                html_parts.append(f"    <tr>")
                html_parts.append(f"      <th>Severity</th>")
                html_parts.append(f"      <th>Message</th>")
                html_parts.append(f"      <th>Affected Annotations</th>")
                html_parts.append(f"    </tr>")
                
                for issue in type_issues:
                    severity_class = issue.severity.value
                    html_parts.append(f"    <tr>")
                    html_parts.append(f"      <td><span class='{severity_class}'>{issue.severity.value.upper()}</span></td>")
                    html_parts.append(f"      <td>{issue.message}</td>")
                    html_parts.append(f"      <td>{', '.join(issue.affected_annotation_ids)}</td>")
                    html_parts.append(f"    </tr>")
                
                html_parts.append(f"  </table>")
            
            html_parts.extend([
                f"</body>",
                f"</html>",
            ])
            
            with open(output_path, 'w') as f:
                f.write('\n'.join(html_parts))
            
            return True
        except Exception:
            return False
