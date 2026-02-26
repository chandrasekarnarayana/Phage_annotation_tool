"""Targeted tests for canonical package internals after reorganization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phage_annotator.algorithms.analysis import compute_mean_std
from phage_annotator.cache.strategies import CacheStrategies, LRUEvictionStrategy
from phage_annotator.framework.command import Command, CommandRegistry
from phage_annotator.framework.events import AnnotationChangedEvent
from phage_annotator.io.projects.base import load_project, save_project
from phage_annotator.io.readers.base import standardize_axes


def test_algorithms_analysis_mean_std_shape() -> None:
    """Algorithm helpers should return 2D projections in expected dtype."""
    arr = np.arange(2 * 1 * 4 * 5, dtype=np.float32).reshape(2, 1, 4, 5)
    mean_proj, std_proj = compute_mean_std(arr)
    assert mean_proj.shape == (4, 5)
    assert std_proj.shape == (4, 5)
    assert mean_proj.dtype == np.float32
    assert std_proj.dtype == np.float32


def test_cache_strategies_registry_returns_expected_type() -> None:
    """Cache strategy registry should construct requested strategy classes."""
    strategy = CacheStrategies.get("lru", max_size=2)
    assert isinstance(strategy, LRUEvictionStrategy)
    strategy.put("a", 1)
    strategy.put("b", 2)
    assert strategy.should_evict() is True
    evicted = strategy.evict()
    assert evicted == "a"


class _EchoCommand(Command):
    @property
    def id(self) -> str:
        return "test.echo"

    @property
    def title(self) -> str:
        return "Echo"

    def execute(self, context=None, **kwargs):
        return kwargs.get("value", context)


def test_framework_command_registry_executes_registered_command() -> None:
    """Command registry should register and execute commands by ID."""
    registry = CommandRegistry()
    registry.register(_EchoCommand())
    result = registry.execute("test.echo", value="ok")
    assert result == "ok"


def test_framework_events_have_type_and_timestamp() -> None:
    """Events should carry derived event_type and timestamp metadata."""
    event = AnnotationChangedEvent(image_id=1, annotations=[], change_type="added")
    assert event.event_type == "AnnotationChangedEvent"
    assert isinstance(event.timestamp, float)
    assert event.image_id == 1


@dataclass
class _ImageStub:
    id: int
    path: Path
    interpret_3d_as: str = "auto"


def test_io_project_roundtrip_and_axes_standardization(tmp_path: Path) -> None:
    """Project save/load and axis-standardization should work via canonical modules."""
    image_path = tmp_path / "image_0.tif"
    project_path = tmp_path / "session.phageproj"
    image = _ImageStub(id=0, path=image_path)

    save_project(
        project_path,
        images=[image],
        annotations={0: []},
        settings={"last_fov_index": 0},
    )
    assert project_path.exists()

    images, settings, ann_map, *_ = load_project(project_path)
    assert len(images) == 1
    assert settings["last_fov_index"] == 0
    assert 0 in ann_map

    arr = np.zeros((3, 8, 9), dtype=np.float32)
    standardized, has_time, has_z = standardize_axes(arr, ome_axes="ZYX")
    assert standardized.shape == (1, 3, 8, 9)
    assert has_time is False
    assert has_z is True
