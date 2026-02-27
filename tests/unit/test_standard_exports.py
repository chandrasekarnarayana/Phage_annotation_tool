"""Unit tests for standard export adapters."""

from __future__ import annotations

import json
import csv

from phage_annotator.core.annotation import Keypoint
from phage_annotator.io.standard_exports import (
    export_canonical_csv,
    export_canonical_json,
    export_coco_keypoints,
    export_evidence_bundle,
    validate_keypoints_for_export,
)


def _sample_points() -> list[Keypoint]:
    return [
        Keypoint(
            image_id=0,
            image_name="img0.tif",
            t=0,
            z=0,
            y=10.0,
            x=20.0,
            label="phage",
            annotation_id="a1",
        ),
        Keypoint(
            image_id=1,
            image_name="img1.tif",
            t=1,
            z=2,
            y=5.0,
            x=15.0,
            label="capsid",
            annotation_id="a2",
        ),
    ]


def test_standard_exports_generate_expected_files(tmp_path) -> None:
    points = _sample_points()
    assert validate_keypoints_for_export(points) == []

    csv_path = tmp_path / "annotations.canonical.csv"
    json_path = tmp_path / "annotations.canonical.json"
    coco_path = tmp_path / "annotations.coco.keypoints.json"

    export_canonical_csv(points, csv_path)
    export_canonical_json(points, json_path)
    export_coco_keypoints(
        points,
        image_records=[
            {"id": 0, "file_name": "img0.tif", "width": 64, "height": 64},
            {"id": 1, "file_name": "img1.tif", "width": 64, "height": 64},
        ],
        path=coco_path,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert coco_path.exists()

    canonical = json.loads(json_path.read_text())
    assert canonical["count"] == 2
    assert len(canonical["annotations"]) == 2

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["annotation_id"] == "a1"

    coco = json.loads(coco_path.read_text())
    assert len(coco["annotations"]) == 2
    assert len(coco["categories"]) == 2
    assert coco["annotations"][0]["attributes"]["annotation_id"] == "a1"


def test_evidence_bundle_contains_manifest_and_logs(tmp_path) -> None:
    points = _sample_points()
    manifest = export_evidence_bundle(
        tmp_path / "bundle",
        keypoints=points,
        qc_issues=[],
        audit_log=[{"event_type": "annotation_added"}],
        suggestion_metrics={"generated": 3, "accepted": 2, "rejected": 1},
    )
    assert manifest.exists()
    payload = json.loads(manifest.read_text())
    assert payload["summary"]["annotation_count"] == 2
    assert payload["summary"]["audit_event_count"] == 1
    assert "reviewer_analytics" in payload["files"]
    analytics_path = manifest.parent / payload["files"]["reviewer_analytics"]
    assert analytics_path.exists()
