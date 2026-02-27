"""Stress coverage for rapid undo/redo on navigation command history."""

from __future__ import annotations

from types import SimpleNamespace

from phage_annotator.core.session_state import ViewState
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.navigation_commands import JumpToFrameCommand, JumpToZCommand
from phage_annotator.session.view import SessionViewMixin


class _Emitter:
    def emit(self) -> None:
        """Minimal Qt-like emitter used by the mixin harness."""


class _NavigationHistoryHarness(SessionViewMixin, SessionAnnotationsMixin):
    """Controller-like harness to validate stack behavior without Qt GUI."""

    def __init__(self) -> None:
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.state_changed = _Emitter()
        self.view_changed = _Emitter()
        self.display_changed = _Emitter()
        self.roi_changed = _Emitter()
        self.annotations_changed = _Emitter()
        self.session_state = SimpleNamespace(
            images=[SimpleNamespace(shape=(60, 12, 64, 64))],
            annotations={0: []},
            annotations_loaded={0: False},
            dirty=False,
        )
        self.view_state = ViewState(t=0, z=0)
        self.display_mapping = DisplayMapping(0.0, 1.0)

    def set_dirty(self, dirty: bool = True) -> None:
        """Compatibility shim required by SessionAnnotationsMixin."""
        self.session_state.dirty = dirty


def test_rapid_navigation_undo_redo_stability() -> None:
    """Rapid undo/redo should keep jump history intact and state consistent."""
    harness = _NavigationHistoryHarness()

    for frame_idx in range(1, 31):
        assert harness.execute_view_command(JumpToFrameCommand(harness, 0, frame_idx))
    for z_idx in range(1, 7):
        assert harness.execute_view_command(JumpToZCommand(harness, 0, z_idx))

    assert harness.view_state.t == 30
    assert harness.view_state.z == 6
    assert len(harness._undo_stack) == 36
    assert len(harness._redo_stack) == 0

    for _ in range(36):
        assert harness.undo()
    assert harness.view_state.t == 0
    assert harness.view_state.z == 0
    assert len(harness._undo_stack) == 0
    assert len(harness._redo_stack) == 36

    for _ in range(36):
        assert harness.redo()
    assert harness.view_state.t == 30
    assert harness.view_state.z == 6
    assert len(harness._undo_stack) == 36
    assert len(harness._redo_stack) == 0

    for _ in range(150):
        assert harness.undo()
        assert harness.redo()

    assert harness.view_state.t == 30
    assert harness.view_state.z == 6
    assert len(harness._undo_stack) == 36
    assert len(harness._redo_stack) == 0
