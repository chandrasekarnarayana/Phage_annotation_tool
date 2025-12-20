import numpy as np

from phage_annotator.auto_roi import propose_roi


def _center(rect):
    x, y, w, h = rect
    return x + w / 2.0, y + h / 2.0


def test_auto_roi_uniform_center():
    img = np.ones((200, 200), dtype=np.float32)
    spec, _ = propose_roi(img, request_w=60, request_h=60, stride=20)
    cx, cy = _center(spec.rect)
    assert abs(cx - 100) < 30
    assert abs(cy - 100) < 30


def test_auto_roi_avoids_dark_blob():
    img = np.ones((200, 200), dtype=np.float32)
    img[80:120, 80:120] = 0.0
    spec, _ = propose_roi(img, request_w=60, request_h=60, stride=20)
    cx, cy = _center(spec.rect)
    assert np.hypot(cx - 100, cy - 100) > 30


def test_auto_roi_avoids_bright_cluster():
    img = np.ones((200, 200), dtype=np.float32)
    img[10:40, 10:40] = 10.0
    spec, _ = propose_roi(img, request_w=60, request_h=60, stride=20)
    cx, cy = _center(spec.rect)
    assert np.hypot(cx - 25, cy - 25) > 30


def test_auto_roi_respects_bounds():
    img = np.ones((80, 80), dtype=np.float32)
    spec, _ = propose_roi(img, min_side=100, request_w=120, request_h=120)
    _, _, w, h = spec.rect
    assert w <= 80
    assert h <= 80


def test_auto_roi_circle_radius_clamp():
    img = np.ones((1000, 1000), dtype=np.float32)
    spec, _ = propose_roi(img, shape="circle", request_area=2_000_000, max_circle_radius=300)
    _, _, w, h = spec.rect
    assert w <= 600
    assert h <= 600
