from pathlib import Path

import numpy as np

from phage_annotator.io import ImageMeta, load_images, standardize_axes


def test_standardize_axes_shapes() -> None:
    arr2d = np.zeros((4, 5))
    std, has_time, has_z = standardize_axes(arr2d)
    assert std.shape == (1, 1, 4, 5)
    assert not has_time and not has_z

    arr3d_z = np.zeros((25, 4, 5))
    std, has_time, has_z = standardize_axes(arr3d_z)
    assert std.shape == (1, 25, 4, 5)
    assert not has_time and has_z

    arr3d_t = np.zeros((3, 4, 5))
    std, has_time, has_z = standardize_axes(arr3d_t)
    assert std.shape == (3, 1, 4, 5)
    assert has_time and not has_z

    arr4d = np.zeros((2, 3, 4, 5))
    std, has_time, has_z = standardize_axes(arr4d)
    assert std.shape == (2, 3, 4, 5)
    assert has_time and has_z


def test_load_images(tmp_path, monkeypatch) -> None:
    # create placeholder file and monkeypatch tifffile.imread
    img_path = tmp_path / "img.tif"
    img_path.write_bytes(b"")

    import phage_annotator.io as io

    def fake_imread(path):
        return np.zeros((2, 3, 4, 5))

    monkeypatch.setattr(io.tif, "imread", fake_imread)
    metas = load_images([img_path])
    assert len(metas) == 1
    meta: ImageMeta = metas[0]
    assert meta.array.shape == (2, 3, 4, 5)
    assert meta.has_time and meta.has_z
