"""Architecture guards for session-layer mutation and signal discipline."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SESSION_ROOT = ROOT / "src" / "phage_annotator" / "session"
SRC_ROOT = ROOT / "src" / "phage_annotator"
ALLOWED_DIRTY_WRITE_MODULES = {
    SESSION_ROOT / "project_persistence.py",
    SESSION_ROOT / "signal_hub.py",
}
ALLOWED_MUTATION_MODULES = {
    SESSION_ROOT / "annotations.py",
    SESSION_ROOT / "annotation_io.py",
    SESSION_ROOT / "annotation_io_methods1.py",
    SESSION_ROOT / "annotation_io_methods2.py",
    SESSION_ROOT / "batch_commands.py",
    SESSION_ROOT / "commands.py",
    SESSION_ROOT / "controller_annotation_contexts.py",
    SESSION_ROOT / "controller.py",
    SESSION_ROOT / "context_commands.py",
    SESSION_ROOT / "controller_display.py",
    SESSION_ROOT / "controller_preferences.py",
    SESSION_ROOT / "controller_sync.py",
    SESSION_ROOT / "controller_smlm.py",
    SESSION_ROOT / "controller_suggestions.py",
    SESSION_ROOT / "controller_threshold_particles.py",
    SESSION_ROOT / "images.py",
    SESSION_ROOT / "metadata_commands.py",
    SESSION_ROOT / "migration.py",
    SESSION_ROOT / "modality_facade.py",
    SESSION_ROOT / "playback.py",
    SESSION_ROOT / "project_bridge.py",
    SESSION_ROOT / "project_bridge_methods1.py",
    SESSION_ROOT / "project_bridge_methods2.py",
    SESSION_ROOT / "project_persistence.py",
    SESSION_ROOT / "project_recovery.py",
    SESSION_ROOT / "signal_hub.py",
    SESSION_ROOT / "suggestion_commands.py",
    SESSION_ROOT / "suggestion_operations.py",
    SESSION_ROOT / "suggestion_pipeline.py",
    SESSION_ROOT / "suggestion_rescore.py",
    SESSION_ROOT / "suggestion_training.py",
    SESSION_ROOT / "session_bridge.py",
    SESSION_ROOT / "session_bridge_loader.py",
    SESSION_ROOT / "file_io.py",
    SESSION_ROOT / "view.py",
}
ALLOWED_RAW_SIGNAL_EMIT_MODULES = {
    SESSION_ROOT / "signal_hub.py",
    SESSION_ROOT / "view_sync.py",
    SESSION_ROOT / "view_sync_crop.py",
    SESSION_ROOT / "view_sync_index.py",
    SESSION_ROOT / "view_sync_state.py",
    SESSION_ROOT / "view_sync_zoom_pan.py",
}
ALLOWED_ANNOTATION_OWNER_MODULES = {
    SESSION_ROOT / "annotations.py",
    SESSION_ROOT / "annotation_io.py",
    SESSION_ROOT / "annotation_io_methods1.py",
    SESSION_ROOT / "annotation_io_methods2.py",
    SESSION_ROOT / "controller_annotation_contexts.py",
    SESSION_ROOT / "context_commands.py",
    SESSION_ROOT / "controller_suggestions.py",
    SESSION_ROOT / "file_io.py",
    SESSION_ROOT / "images.py",
    SESSION_ROOT / "project_bridge.py",
    SESSION_ROOT / "project_bridge_methods2.py",
    SESSION_ROOT / "project_recovery.py",
    SESSION_ROOT / "suggestion_commands.py",
    SESSION_ROOT / "suggestion_operations.py",
    SESSION_ROOT / "session_bridge_loader.py",
}
FORBIDDEN_MUTATION_ROOTS = {
    "self.session_state",
    "self.view_state",
    "self.display_mapping",
    "controller.session_state",
    "controller.view_state",
    "controller.display_mapping",
}
FORBIDDEN_COLLECTION_ROOTS = {
    "self.session_state.annotations",
    "self.session_state.suggestions",
    "self.session_state.suggestion_history",
    "controller.session_state.annotations",
    "controller.session_state.suggestions",
    "controller.session_state.suggestion_history",
}
MUTATING_METHODS = {"append", "clear", "extend", "insert", "pop", "remove", "setdefault", "sort", "update"}


def _attr_path(node: ast.AST) -> str | None:
    """Build a dotted attribute path for simple member access."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attr_path(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return _attr_path(node.value)
    return None


class _DirtyWriteVisitor(ast.NodeVisitor):
    """Find direct `dirty` assignments on session state."""

    def __init__(self, rel_path: Path) -> None:
        """Initialize the object and prepare its runtime state."""
        self.rel_path = rel_path
        self.violations: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit Assign for the current workflow."""
        for target in node.targets:
            path = _attr_path(target)
            if path and (
                path == "self.session_state.dirty"
                or path.endswith(".session_state.dirty")
            ):
                self.violations.append(
                    f"{self.rel_path}:{getattr(node, 'lineno', 0)}: direct dirty write to {path}"
                )
        self.generic_visit(node)


class _StateMutationVisitor(ast.NodeVisitor):
    """Find direct mutation roots that should stay in approved session modules only."""

    def __init__(self, rel_path: Path) -> None:
        """Initialize the object and prepare its runtime state."""
        self.rel_path = rel_path
        self.violations: list[str] = []

    def _record(self, node: ast.AST, detail: str) -> None:
        """Record record for the current workflow."""
        self.violations.append(f"{self.rel_path}:{getattr(node, 'lineno', 0)}: {detail}")

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit Assign for the current workflow."""
        for target in node.targets:
            path = _attr_path(target)
            if path and any(path.startswith(f"{root}.") for root in FORBIDDEN_MUTATION_ROOTS):
                self._record(node, f"direct assignment to {path}")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit AugAssign for the current workflow."""
        path = _attr_path(node.target)
        if path and any(path.startswith(f"{root}.") for root in FORBIDDEN_MUTATION_ROOTS):
            self._record(node, f"augmented assignment to {path}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit Call for the current workflow."""
        func = node.func
        if isinstance(func, ast.Attribute):
            owner_path = _attr_path(func.value)
            method = func.attr
            if owner_path in FORBIDDEN_COLLECTION_ROOTS and method in MUTATING_METHODS:
                self._record(node, f"collection mutation {owner_path}.{method}()")
        self.generic_visit(node)


class _RawSignalEmitVisitor(ast.NodeVisitor):
    """Find raw controller signal emits outside the central hub/Qt-specific sync path."""

    SIGNAL_NAMES = {
        "state_changed",
        "view_changed",
        "display_changed",
        "annotations_changed",
        "playback_changed",
        "error_occurred",
        "roi_changed",
    }

    def __init__(self, rel_path: Path) -> None:
        """Initialize the object and prepare its runtime state."""
        self.rel_path = rel_path
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Visit Call for the current workflow."""
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "emit":
            owner = func.value
            if isinstance(owner, ast.Attribute) and owner.attr in self.SIGNAL_NAMES:
                self.violations.append(
                    f"{self.rel_path}:{getattr(node, 'lineno', 0)}: raw signal emit on {owner.attr}"
                )
        self.generic_visit(node)


class _AnnotationWriteVisitor(ast.NodeVisitor):
    """Find direct annotation collection mutations outside approved owner modules."""

    def __init__(self, rel_path: Path) -> None:
        """Initialize the object and prepare its runtime state."""
        self.rel_path = rel_path
        self.violations: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit Assign for the current workflow."""
        for target in node.targets:
            path = _attr_path(target)
            if path in {"self.session_state.annotations", "controller.session_state.annotations"}:
                self.violations.append(
                    f"{self.rel_path}:{getattr(node, 'lineno', 0)}: direct annotation store assignment to {path}"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit Call for the current workflow."""
        func = node.func
        if isinstance(func, ast.Attribute):
            owner_path = _attr_path(func.value)
            method = func.attr
            if owner_path in {
                "self.session_state.annotations",
                "controller.session_state.annotations",
            } and method in MUTATING_METHODS:
                self.violations.append(
                    f"{self.rel_path}:{getattr(node, 'lineno', 0)}: direct annotation mutation {owner_path}.{method}()"
                )
        self.generic_visit(node)


def test_session_modules_only_use_approved_dirty_write_roots() -> None:
    """Only the central signal hub and persistence helper may assign the dirty flag."""
    violations: list[str] = []
    for path in SESSION_ROOT.rglob("*.py"):
        if path in ALLOWED_DIRTY_WRITE_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _DirtyWriteVisitor(path.relative_to(ROOT))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert not violations, "Forbidden direct dirty writes found in session modules:\n" + "\n".join(
        violations
    )


def test_session_state_mutation_roots_stay_in_approved_modules() -> None:
    """Direct session/view/display mutations should stay in designated state-owner modules."""
    violations: list[str] = []
    for path in SESSION_ROOT.rglob("*.py"):
        if path in ALLOWED_MUTATION_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _StateMutationVisitor(path.relative_to(ROOT))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert (
        not violations
    ), "Forbidden direct session/view/display mutations found outside approved modules:\n" + "\n".join(
        violations
    )


def test_raw_controller_signal_emit_calls_stay_centralized() -> None:
    """Controller Qt signal emits should stay in the signal hub or Qt-local view sync module."""
    violations: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path in ALLOWED_RAW_SIGNAL_EMIT_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _RawSignalEmitVisitor(path.relative_to(ROOT))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert not violations, "Raw controller signal emits found outside approved modules:\n" + "\n".join(
        violations
    )


def test_annotation_writes_stay_in_annotation_owner_modules() -> None:
    """Committed annotation writes should stay in the annotation model/restore owner modules."""
    violations: list[str] = []
    for path in SESSION_ROOT.rglob("*.py"):
        if path in ALLOWED_ANNOTATION_OWNER_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _AnnotationWriteVisitor(path.relative_to(ROOT))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert not violations, "Direct annotation writes found outside approved owner modules:\n" + "\n".join(
        violations
    )
