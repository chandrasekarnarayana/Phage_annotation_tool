"""Architecture guards for UI-to-controller mutation boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
UI_ROOT = ROOT / "src" / "phage_annotator" / "ui_qt"
FORBIDDEN_STATE_ROOTS = {
    "controller.session_state",
    "controller.view_state",
}
FORBIDDEN_COLLECTION_ROOTS = {
    "controller.session_state.annotations",
    "controller.session_state.suggestions",
    "controller.session_state.suggestion_history",
    "self.annotations",
    "self.suggestions",
}
MUTATING_METHODS = {
    "append",
    "clear",
    "extend",
    "insert",
    "pop",
    "remove",
    "setdefault",
    "sort",
    "update",
}


def _attr_path(node: ast.AST) -> str | None:
    """Build dotted attribute/subscript root paths for simple member access."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attr_path(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return _attr_path(node.value)
    return None


class _MutationVisitor(ast.NodeVisitor):
    """Collect forbidden UI mutations of controller-owned state."""

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
            if not path:
                continue
            if any(path.startswith(f"{root}.") for root in FORBIDDEN_STATE_ROOTS):
                self._record(node, f"direct assignment to {path}")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit AugAssign for the current workflow."""
        path = _attr_path(node.target)
        if path and any(path.startswith(f"{root}.") for root in FORBIDDEN_STATE_ROOTS):
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


def test_ui_modules_do_not_mutate_controller_owned_state() -> None:
    """UI layers should route direct and collection mutations through controller methods."""
    violations: list[str] = []
    for path in UI_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _MutationVisitor(path.relative_to(ROOT))
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert not violations, "Forbidden UI mutation of controller-owned state found:\n" + "\n".join(
        violations
    )
