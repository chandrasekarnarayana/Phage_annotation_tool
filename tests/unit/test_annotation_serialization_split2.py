"""Split definitions from test_annotation_serialization.py."""


import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from phage_annotator.core.annotation import Keypoint
from phage_annotator.io.csv_metadata_io import (
    load_keypoints_csv_with_metadata,
    save_keypoints_csv_with_metadata,
)
from phage_annotator.core.annotation import (
    save_keypoints_json,
    keypoints_from_json,
)


class TestJSONMetadataIO:
    """Test JSON serialization with metadata preservation."""
    
    @pytest.fixture
    def test_keypoints(self):
        """Create test keypoints with rich metadata."""
        return [
            Keypoint(
                image_id=0,
                image_name="image1.tif",
                t=0,
                z=5,
                y=100.5,
                x=200.5,
                label="phage",
                meta={
                    "confidence": 0.95,
                    "annotator": "alice",
                    "comment": "clear detection",
                    "uncertain": False,
                    "photons": 1000,
                },
            ),
            Keypoint(
                image_id=0,
                image_name="image1.tif",
                t=1,
                z=6,
                y=150.0,
                x=250.0,
                label="artifact",
                meta={
                    "confidence": 0.5,
                    "annotator": "bob",
                    "uncertain": True,
                },
            ),
        ]
    
    def test_json_round_trip_metadata(self, test_keypoints):
        """Test JSON preserves complete metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "annotations.json"
            
            # Save
            save_keypoints_json(test_keypoints, json_path)
            
            # Load
            loaded = keypoints_from_json(json_path)
            
            # Verify metadata preserved
            assert len(loaded) == 2
            
            ann1 = loaded[0]
            assert ann1.meta["confidence"] == 0.95
            assert ann1.meta["annotator"] == "alice"
            assert ann1.meta["uncertain"] == False
            
            ann2 = loaded[1]
            assert ann2.meta["confidence"] == 0.5
            assert ann2.meta["uncertain"] == True
    
    def test_json_structure(self, test_keypoints):
        """Test JSON structure includes metadata at annotation level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "annotations.json"
            
            save_keypoints_json(test_keypoints, json_path)
            
            # Read raw JSON
            data = json.loads(json_path.read_text())
            
            # Should be keyed by image_name
            assert "image1.tif" in data
            
            annotations = data["image1.tif"]
            assert len(annotations) == 2
            
            # Each annotation should have metadata
            assert "meta" in annotations[0]
            assert "confidence" in annotations[0]["meta"]
    
    def test_json_with_metadata_container(self):
        """Test JSON with top-level metadata container."""
        kp = Keypoint(
            image_id=0, image_name="test.tif", t=0, z=0,
            y=100.0, x=200.0, label="phage",
            meta={"confidence": 0.9},
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "annotations.json"
            
            # Save with project metadata
            save_keypoints_json(
                [kp],
                json_path,
                meta={"project": "test", "schema": "v3"},
            )
            
            # Read raw JSON
            data = json.loads(json_path.read_text())
            
            # Should have meta and annotations keys
            assert "meta" in data
            assert "annotations" in data
            assert data["meta"]["project"] == "test"

class TestCSVJSONParity:
    """Test CSV and JSON export parity for metadata."""
    
    @pytest.fixture
    def test_keypoints(self):
        """Create test keypoints."""
        return [
            Keypoint(
                image_id=0,
                image_name="img.tif",
                t=0,
                z=0,
                y=100.5,
                x=200.5,
                label="phage",
                meta={
                    "confidence": 0.95,
                    "annotator": "alice",
                    "comment": "test",
                    "uncertain": False,
                    "photons": 1000,
                },
            ),
        ]
    
    def test_csv_and_json_preserve_same_metadata(self, test_keypoints):
        """Test that CSV and JSON exports preserve the same metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "annotations.csv"
            json_path = Path(tmpdir) / "annotations.json"
            
            # Export to both formats
            save_keypoints_csv_with_metadata(
                test_keypoints,
                csv_path,
                include_metadata=True,
            )
            save_keypoints_json(test_keypoints, json_path)
            
            # Load from both
            csv_loaded, _ = load_keypoints_csv_with_metadata(csv_path)
            json_loaded = keypoints_from_json(json_path)
            
            # Metadata should match
            csv_meta = csv_loaded[0].meta
            json_meta = json_loaded[0].meta
            
            assert csv_meta["confidence"] == json_meta["confidence"]
            assert csv_meta["annotator"] == json_meta["annotator"]
            assert csv_meta["uncertain"] == json_meta["uncertain"]
