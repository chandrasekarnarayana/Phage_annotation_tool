#!/usr/bin/env python3
"""Validate internal `phage_annotator` import integrity.

Checks:
1. Every `phage_annotator.*` import resolves to an importable module.
2. No file imports its own module path directly.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
PKG_ROOT = SRC_ROOT / "phage_annotator"


class ImportVisitor(ast.NodeVisitor):
    """Collect imports while skipping `if TYPE_CHECKING:` blocks."""

    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.imports: list[tuple[str, str]] = []
        self._in_type_checking = False

    def visit_If(self, node: ast.If) -> None:
        """Visit If for the current workflow."""
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            prev = self._in_type_checking
            self._in_type_checking = True
            for child in node.body:
                self.visit(child)
            self._in_type_checking = prev
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit Import for the current workflow."""
        if self._in_type_checking:
            return
        for alias in node.names:
            self.imports.append(("import", alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit ImportFrom for the current workflow."""
        if self._in_type_checking:
            return
        if node.module is None:
            return
        if node.level:
            self.imports.append(("relative", f"{node.level}:{node.module}"))
        else:
            self.imports.append(("from", node.module))


def _module_name_for_file(path: Path) -> str:
    """Handle the module name for file helper flow."""
    rel = path.relative_to(PKG_ROOT)
    if rel.name == "__init__.py":
        parts = rel.parent.parts
    else:
        parts = rel.with_suffix("").parts
    if parts:
        return "phage_annotator." + ".".join(parts)
    return "phage_annotator"


def _resolve_relative_import(
    current_module: str,
    is_package_module: bool,
    level: int,
    module: str,
) -> str | None:
    """Resolve relative import for the current workflow."""
    base_parts = current_module.split(".") if is_package_module else current_module.split(".")[:-1]
    keep = len(base_parts) - (level - 1)
    if keep <= 0:
        return None
    prefix = base_parts[:keep]
    if module:
        prefix.extend(module.split("."))
    return ".".join(prefix)


def _collect_phage_imports(path: Path) -> Iterable[str]:
    """Collect phage imports for the current workflow."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = ImportVisitor()
    visitor.visit(tree)

    current_module = _module_name_for_file(path)
    is_package_module = path.name == "__init__.py"
    for kind, name in visitor.imports:
        if kind in {"import", "from"}:
            if name.startswith("phage_annotator"):
                yield name
            continue
        if kind == "relative":
            raw_level, raw_module = name.split(":", maxsplit=1)
            resolved = _resolve_relative_import(
                current_module=current_module,
                is_package_module=is_package_module,
                level=int(raw_level),
                module=raw_module,
            )
            if resolved and resolved.startswith("phage_annotator"):
                yield resolved


def _module_exists(module_name: str) -> bool:
    """Handle the module exists helper flow."""
    if module_name == "phage_annotator":
        return (PKG_ROOT / "__init__.py").exists()
    if not module_name.startswith("phage_annotator."):
        return True

    rel_parts = module_name.split(".")[1:]
    if not rel_parts:
        return (PKG_ROOT / "__init__.py").exists()

    package_dir = PKG_ROOT.joinpath(*rel_parts)
    if package_dir.is_dir() and (package_dir / "__init__.py").exists():
        return True

    module_file = PKG_ROOT.joinpath(*rel_parts[:-1], f"{rel_parts[-1]}.py")
    return module_file.exists()


def main() -> int:
    """Run the main workflow."""
    unresolved: list[tuple[str, str]] = []
    self_imports: list[tuple[str, str]] = []

    for path in sorted(PKG_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module_name = _module_name_for_file(path)
        try:
            imports = list(_collect_phage_imports(path))
        except SyntaxError as exc:
            unresolved.append((str(path), f"SyntaxError: {exc}"))
            continue

        for imported in imports:
            if imported == module_name:
                self_imports.append((str(path), imported))
                continue
            if not _module_exists(imported):
                unresolved.append((str(path), imported))

    if self_imports or unresolved:
        print("❌ Import integrity check failed.")
        if self_imports:
            print("\nSelf-imports:")
            for file_path, imported in self_imports:
                print(f"  - {file_path} imports itself as {imported}")
        if unresolved:
            print("\nUnresolved imports:")
            for file_path, imported in unresolved:
                print(f"  - {file_path} -> {imported}")
        return 1

    print("✅ Import integrity passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
