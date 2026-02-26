from phage_annotator.demo import generate_dummy_image
from phage_annotator.io import load_images


def test_dummy_image_loads(tmp_path) -> None:
    path = generate_dummy_image(tmp_path / "dummy.tif", mode="tz")
    metas = load_images([path])
    assert len(metas) == 1
    meta = metas[0]
    assert meta.array.shape == (2, 3, 64, 64)
    assert meta.has_time is True
    assert meta.has_z is True
    assert meta.name == path.name
