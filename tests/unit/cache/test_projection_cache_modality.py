"""Tests for modality-aware projection cache behavior."""

from __future__ import annotations

import numpy as np

from phage_annotator.cache.projection_cache import ProjectionCache


def _key(image_id: int, kind: str, modality_idx: int) -> tuple:
    return (image_id, kind, (0.0, 0.0, 0.0, 0.0), -1, -1, modality_idx)


def _pyramid_key(image_id: int, kind: str, modality_idx: int, level: int = 3) -> tuple:
    return (image_id, kind, -1, -1, (0.0, 0.0, 0.0, 0.0), level, modality_idx)


def test_set_modality_count_clamps_to_one() -> None:
    cache = ProjectionCache(max_mb=10)
    cache.set_modality_count(0)
    assert cache._modality_count == 1


def test_modality_usage_tracks_main_and_pyramid() -> None:
    cache = ProjectionCache(max_mb=10)
    data = np.ones((10, 10), dtype=np.float32)
    cache.put(_key(0, "mean", 0), data)
    cache.put_pyramid(_pyramid_key(0, "mean", 0), data)
    bytes_used, _ = cache.get_modality_usage(0)
    assert bytes_used == data.nbytes * 2


def test_modality_over_budget_eviction_prefers_overused() -> None:
    cache = ProjectionCache(max_mb=1)
    cache.set_modality_count(2)
    data = np.ones((256, 256), dtype=np.float32)  # ~0.25 MB

    cache.put(_key(0, "mean", 0), data)
    cache.put(_key(1, "mean", 0), data)
    cache.put(_key(2, "mean", 0), data)
    cache.put(_key(3, "mean", 1), data)
    cache.put(_key(4, "mean", 0), data)  # Push over total budget

    per_modality_budget = cache._max_bytes // cache._modality_count
    bytes_used, _ = cache.get_modality_usage(0)
    assert bytes_used <= per_modality_budget


def test_should_compute_blocks_when_over_budget() -> None:
    cache = ProjectionCache(max_mb=1)
    data = np.ones((512, 512), dtype=np.float32)  # ~1 MB
    cache.put(_key(0, "mean", 0), data)
    assert cache.should_compute(0) is False


def test_should_compute_allows_under_budget() -> None:
    cache = ProjectionCache(max_mb=10)
    assert cache.should_compute(0) is True


def test_should_compute_blocks_when_cache_is_thrashing() -> None:
    cache = ProjectionCache(max_mb=10)
    cache._telemetry.hits_this_cycle = 1
    cache._telemetry.evictions_this_cycle = 3
    assert cache.should_compute(0) is False


def test_pyramid_usage_included_in_modality_usage() -> None:
    cache = ProjectionCache(max_mb=10)
    data = np.ones((20, 20), dtype=np.float32)
    cache.put_pyramid(_pyramid_key(0, "mean", 1), data)
    bytes_used, _ = cache.get_modality_usage(1)
    assert bytes_used == data.nbytes


def test_clear_resets_modality_usage() -> None:
    cache = ProjectionCache(max_mb=10)
    data = np.ones((10, 10), dtype=np.float32)
    cache.put(_key(0, "mean", 0), data)
    cache.clear()
    bytes_used, _ = cache.get_modality_usage(0)
    assert bytes_used == 0


def test_invalidate_image_updates_modality_usage() -> None:
    cache = ProjectionCache(max_mb=10)
    data = np.ones((10, 10), dtype=np.float32)
    cache.put(_key(0, "mean", 0), data)
    cache.put(_key(1, "mean", 0), data)
    cache.invalidate_image(0)
    bytes_used, _ = cache.get_modality_usage(0)
    assert bytes_used == data.nbytes


def test_warning_callback_emits_once_at_ninety_percent_budget() -> None:
    cache = ProjectionCache(max_mb=1)
    warned: list[str] = []
    cache.set_warning_callback(warned.append)
    data = np.ones((512, 512), dtype=np.float32)  # ~1.0 MB, pushes over 90% in one put
    cache.put(_key(0, "mean", 0), data)
    cache.put(_key(1, "mean", 0), data)
    assert len(warned) == 1
    assert "Cache at" in warned[0]
