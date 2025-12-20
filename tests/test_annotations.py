from pathlib import Path

from phage_annotator.annotations import (Keypoint, keypoints_to_dataframe, save_keypoints_csv,
                                         save_keypoints_json)


def sample_keypoints():
    return [
        Keypoint(image_id=0, image_name="img.tif", t=0, z=0, y=1.0, x=2.0, label="phage"),
        Keypoint(image_id=0, image_name="img.tif", t=0, z=1, y=3.5, x=4.5, label="artifact"),
    ]


def test_dataframe_columns() -> None:
    df = keypoints_to_dataframe(sample_keypoints())
    assert set(df.columns) == {"image_id", "image_name", "t", "z", "y", "x", "label"}
    assert df.shape[0] == 2


def test_save_keypoints(tmp_path: Path) -> None:
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
