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


class TestCSVMetadataIO:
    """Test CSV serialization with metadata preservation."""
    
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
                    "timestamp": "2026-02-27T12:00:00",
                    "photons": 1000,
                    "custom_field": "custom_value",
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
                    "comment": "ambiguous",
                    "uncertain": True,
                    "timestamp": "2026-02-27T12:15:00",
                    "photons": 500,
                },
            ),
        ]
    
    def test_save_and_load_extended_csv(self, test_keypoints):
        """Test extended CSV format with metadata columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "annotations.csv"
            
            # Save with metadata
            save_keypoints_csv_with_metadata(
                test_keypoints,
                csv_path,
                include_metadata=True,
                meta={"project": "test", "version": "1.0"},
            )
            
            # Load with metadata
            loaded, project_meta = load_keypoints_csv_with_metadata(csv_path)
            
            # Verify counts
            assert len(loaded) == 2
            assert project_meta is not None
            assert project_meta["project"] == "test"
            
            # Verify first annotation
            ann1 = loaded[0]
            assert ann1.label == "phage"
            assert ann1.meta["confidence"] == 0.95
            assert ann1.meta["annotator"] == "alice"
            assert ann1.meta["comment"] == "clear detection"
            assert ann1.meta["uncertain"] == False
            assert ann1.meta["photons"] == 1000
            assert ann1.meta["custom_field"] == "custom_value"
            
            # Verify second annotation
            ann2 = loaded[1]
            assert ann2.label == "artifact"
            assert ann2.meta["confidence"] == 0.5
            assert ann2.meta["uncertain"] == True
    
    def test_save_legacy_csv_format(self, test_keypoints):
        """Test legacy CSV format without metadata columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "annotations.csv"
            
            # Save without metadata
            save_keypoints_csv_with_metadata(
                test_keypoints,
                csv_path,
                include_metadata=False,
            )
            
            # Verify file exists and is readable
            content = csv_path.read_text()
            assert "image_id" in content
            assert "image_name" in content
            assert "label" in content
            
            # Legacy format shouldn't have metadata columns
            assert "confidence" not in content.split("\n")[0]  # Not in header
    
    def test_csv_with_nested_metadata(self):
        """Test CSV serialization of nested metadata (dict/list)."""
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=0,
            z=0,
            y=100.0,
            x=200.0,
            label="phage",
            meta={
                "confidence": 0.9,
                "nested_dict": {"key": "value", "number": 42},
                "nested_list": [1, 2, 3],
            },
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "nested.csv"
            
            # Save
            save_keypoints_csv_with_metadata([kp], csv_path, include_metadata=True)
            
            # Load
            loaded, _ = load_keypoints_csv_with_metadata(csv_path)
            
            assert len(loaded) == 1
            loaded_kp = loaded[0]
            assert loaded_kp.meta["nested_dict"] == {"key": "value", "number": 42}
            assert loaded_kp.meta["nested_list"] == [1, 2, 3]
    
    def test_csv_round_trip_schema(self, test_keypoints):
        """Test that annotation_id is preserved in round-trip."""
        original_ids = [kp.annotation_id for kp in test_keypoints]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "annotations.csv"
            
            save_keypoints_csv_with_metadata(
                test_keypoints,
                csv_path,
                include_metadata=True,
            )
            
            loaded, _ = load_keypoints_csv_with_metadata(csv_path)
            loaded_ids = [kp.annotation_id for kp in loaded]
            
            assert loaded_ids == original_ids
    
    def test_csv_with_missing_optional_metadata(self):
        """Test CSV handling when some annotations lack certain metadata fields."""
        kp1 = Keypoint(
            image_id=0, image_name="test.tif", t=0, z=0,
            y=100.0, x=200.0, label="phage",
            meta={"confidence": 0.9, "annotator": "alice"},
        )
        kp2 = Keypoint(
            image_id=0, image_name="test.tif", t=1, z=1,
            y=150.0, x=250.0, label="artifact",
            meta={"confidence": 0.5},  # Missing annotator
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "annotations.csv"
            
            save_keypoints_csv_with_metadata(
                [kp1, kp2],
                csv_path,
                include_metadata=True,
            )
            
            loaded, _ = load_keypoints_csv_with_metadata(csv_path)
            
            # Verify both loaded correctly
            assert len(loaded) == 2
            assert loaded[0].meta["annotator"] == "alice"
            # Second one should have NaN or None for missing field
            assert pd.isna(loaded[1].meta.get("annotator")) or loaded[1].meta.get("annotator") is None
