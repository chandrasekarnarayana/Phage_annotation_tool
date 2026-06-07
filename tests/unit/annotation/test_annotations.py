"""Unit tests for annotation serialization helpers."""

from pathlib import Path

from phage_annotator.annotation.core import (
    Keypoint,
    keypoints_to_dataframe,
    keypoints_from_csv,
    keypoints_from_json,
    save_keypoints_csv,
    save_keypoints_json,
)


def sample_keypoints():
    """Run the sample keypoints workflow."""
    return [
        Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=1.0, x=2.0, label="phage"),
        Keypoint(image_id=0, image_name="img.tif", t=0, z=1, y=3.5, x=4.5, label="artifact"),
    ]


def test_dataframe_columns() -> None:
    """Verify dataframe columns for the current workflow."""
    df = keypoints_to_dataframe(sample_keypoints())
    assert set(df.columns) == {"image_id", "image_name", "t", "z", "y", "x", "label"}
    assert df.shape[0] == 2


def test_save_keypoints(tmp_path: Path) -> None:
    """Verify save keypoints for the current workflow."""
    csv_path = tmp_path / "ann.csv"
    json_path = tmp_path / "ann.json"
    kps = sample_keypoints()

    save_keypoints_csv(kps, csv_path)
    save_keypoints_json(kps, json_path)

    assert csv_path.exists()
    assert json_path.exists()
    assert "phage" in csv_path.read_text()
    content = json_path.read_text()
    assert "img.tif" in content


def test_annotation_meta_defaults() -> None:
    """Verify annotation meta defaults for the current workflow."""
    kp = Keypoint(
        image_id=0,
        image_name="img.tif",
        t=0,
        z=0,
        y=1.0,
        x=2.0,
        label="phage",
        meta={"confidence": 0.75},
    )
    assert kp.meta["confidence"] == 0.75
    assert kp.meta["annotator"] == ""
    assert kp.meta["timestamp"] is None
    assert kp.meta["comment"] == ""
    assert kp.meta["uncertain"] is False


def test_provenance_roundtrip_csv_json(tmp_path: Path) -> None:
    """Verify provenance roundtrip csv json for the current workflow."""
    kp = Keypoint(
        image_id=0,
        image_name="img.tif",
        t=0,
        z=0,
        y=1.0,
        x=2.0,
        label="phage",
        source="assist",
    )
    kp.status = "accepted"
    kp.confidence = 0.87
    kp.roi_name = "roi-a"
    kp.notes = "verified"
    csv_path = tmp_path / "ann.csv"
    json_path = tmp_path / "ann.json"

    df = keypoints_to_dataframe([kp], include_provenance=True)
    assert list(df.columns) == [
        "image_id",
        "image_name",
        "t",
        "z",
        "y",
        "x",
        "label",
        "source",
        "status",
        "confidence",
        "roi",
        "notes",
    ]

    save_keypoints_csv([kp], csv_path, include_provenance=True)
    save_keypoints_json([kp], json_path, include_provenance=True)

    loaded_csv = keypoints_from_csv(csv_path)
    loaded_json = keypoints_from_json(json_path)
    assert loaded_csv[0].source == "assist"
    assert loaded_csv[0].status == "accepted"
    assert loaded_csv[0].confidence == 0.87
    assert loaded_csv[0].roi_name == "roi-a"
    assert loaded_csv[0].notes == "verified"
    assert loaded_json[0].status == "accepted"
    assert loaded_json[0].confidence == 0.87
