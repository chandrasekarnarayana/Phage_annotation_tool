import json
from types import SimpleNamespace

import numpy as np

from phage_annotator.analysis import apply_crop_rect, map_point_to_crop, roi_mask_for_shape
from phage_annotator.io import standardize_axes
from phage_annotator.project_io import load_project, save_project
from phage_annotator.projection_cache import ProjectionCache
from phage_annotator.annotations import Keypoint


def test_standardize_axes_2d_3d_4d_heuristic() -> None:
    arr2d = np.zeros((5, 6), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr2d)
    assert std.shape == (1, 1, 5, 6)
    assert not has_time and not has_z

    arr3d_time = np.zeros((3, 5, 6), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr3d_time, interpret_3d_as="auto")
    assert std.shape == (3, 1, 5, 6)
    assert has_time and not has_z

    arr3d_depth = np.zeros((10, 5, 6), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr3d_depth, interpret_3d_as="auto")
    assert std.shape == (1, 10, 5, 6)
    assert not has_time and has_z

    arr4d = np.zeros((2, 3, 5, 6), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr4d)
    assert std.shape == (2, 3, 5, 6)
    assert has_time and has_z


def test_standardize_axes_ome_metadata() -> None:
    arr_zyx = np.zeros((3, 4, 5), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr_zyx, ome_axes="ZYX")
    assert std.shape == (1, 3, 4, 5)
    assert not has_time and has_z

    arr_tyx = np.zeros((2, 4, 5), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr_tyx, ome_axes="TYX")
    assert std.shape == (2, 1, 4, 5)
    assert has_time and not has_z

    arr_cyx = np.zeros((1, 4, 5), dtype=np.float32)
    std, has_time, has_z = standardize_axes(arr_cyx, ome_axes="CYX")
    assert std.shape == (1, 1, 4, 5)
    assert not has_time and not has_z


def test_crop_mapping() -> None:
    arr = np.arange(100, dtype=np.float32).reshape(10, 10)
    crop = (2.0, 3.0, 4.0, 5.0)
    cropped = apply_crop_rect(arr, crop)
    assert cropped.shape == (5, 4)
    x2, y2 = map_point_to_crop(2.0, 3.0, crop)
    assert (x2, y2) == (0.0, 0.0)

    full_crop = (0.0, 0.0, 10.0, 10.0)
    cropped_full = apply_crop_rect(arr, full_crop)
    assert cropped_full.shape == arr.shape
    x3, y3 = map_point_to_crop(4.0, 5.0, full_crop)
    assert (x3, y3) == (4.0, 5.0)


def test_roi_mask_box_circle() -> None:
    box = roi_mask_for_shape((5, 5), (1.0, 1.0, 2.0, 2.0), "box")
    assert box[1, 1]
    assert box[3, 3]
    assert not box[0, 0]

    circle = roi_mask_for_shape((5, 5), (1.0, 1.0, 2.0, 2.0), "circle")
    assert circle[2, 2]
    assert circle[1, 2]
    assert not circle[0, 0]


def test_project_roundtrip_and_backward_compat(tmp_path) -> None:
    img1 = SimpleNamespace(id=0, path=str(tmp_path / "img1.tif"), interpret_3d_as="time")
    img2 = SimpleNamespace(id=1, path=str(tmp_path / "img2.tif"), interpret_3d_as="depth")
    ann = {
        0: [Keypoint(image_id=0, image_name="img1.tif", t=0, z=0, y=1.0, x=2.0, label="phage")],
        1: [],
    }
    proj = tmp_path / "session.phageproj"
    save_project(proj, [img1, img2], ann, {"last_fov_index": 0})
    images, settings, ann_map = load_project(proj)
    assert images[0]["interpret_3d_as"] == "time"
    assert images[1]["interpret_3d_as"] == "depth"
    assert settings["last_fov_index"] == 0
    assert 0 in ann_map and 1 in ann_map

    legacy = tmp_path / "legacy.phageproj"
    legacy.write_text(
        json.dumps(
            {"tool": "PhageAnnotator", "version": "0.9.0", "images": [{"path": "x.tif"}], "settings": {}}
        )
    )
    images2, settings2, ann_map2 = load_project(legacy)
    assert images2[0]["path"] == "x.tif"
    assert settings2 == {}
    assert ann_map2 == {}


def test_projection_cache_eviction() -> None:
    cache = ProjectionCache(max_mb=0)
    arr = np.zeros((10, 10), dtype=np.float64)
    cache.put((0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1), arr)
    assert cache.get((0, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1)) is None

    cache = ProjectionCache(max_mb=1)
    a = np.zeros((200, 200), dtype=np.float64)
    b = np.ones((200, 200), dtype=np.float64)
    c = np.full((200, 200), 2.0, dtype=np.float64)
    d = np.full((200, 200), 3.0, dtype=np.float64)
    cache.put((1, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1), a)
    cache.put((2, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1), b)
    cache.put((3, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1), c)
    # Should evict the oldest if over budget after adding another item
    cache.put((4, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1), d)
    assert cache.get((1, "mean", (0.0, 0.0, 0.0, 0.0), -1, -1)) is None
