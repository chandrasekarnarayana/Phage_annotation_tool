import json
from pathlib import Path

import pandas as pd

from phage_annotator.annotations import (
    Keypoint,
    keypoints_to_dataframe,
    save_keypoints_csv,
    save_keypoints_json,
)


def _sample_keypoints() -> list[Keypoint]:
    return [
        Keypoint(image_id=0, image_name="img0.tif", t=0, z=0, y=1.0, x=2.0, label="phage"),
        Keypoint(image_id=0, image_name="img0.tif", t=1, z=0, y=3.5, x=4.5, label="artifact"),
        Keypoint(image_id=1, image_name="img1.tif", t=0, z=1, y=5.0, x=6.0, label="other"),
    ]


def test_csv_json_roundtrip(tmp_path: Path) -> None:
    kps = _sample_keypoints()
    csv_path = tmp_path / "ann.csv"
    json_path = tmp_path / "ann.json"

    save_keypoints_csv(kps, csv_path)
    save_keypoints_json(kps, json_path)

    df = pd.read_csv(csv_path)
    assert df.shape[0] == len(kps)
    for kp, row in zip(kps, df.itertuples(index=False), strict=True):
        assert kp.image_id == row.image_id
        assert kp.image_name == row.image_name
        assert kp.t == row.t
        assert kp.z == row.z
        assert kp.y == row.y
        assert kp.x == row.x
        assert kp.label == row.label

    data = json.loads(json_path.read_text())
    assert set(data.keys()) == {"img0.tif", "img1.tif"}
    flat = [item for records in data.values() for item in records]
    assert len(flat) == len(kps)


def test_empty_serialization(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    json_path = tmp_path / "empty.json"
    save_keypoints_csv([], csv_path)
    save_keypoints_json([], json_path)

    df = pd.read_csv(csv_path)
    assert df.shape[0] == 0
    loaded = json.loads(json_path.read_text())
    assert loaded == {}


def test_dataframe_columns_order() -> None:
    df = keypoints_to_dataframe(_sample_keypoints())
    assert list(df.columns) == ["image_id", "image_name", "t", "z", "y", "x", "label"]
