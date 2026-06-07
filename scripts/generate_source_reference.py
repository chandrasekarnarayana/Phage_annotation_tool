#!/usr/bin/env python3
"""Generate source-reference documentation from Python docstrings."""

from __future__ import annotations

import ast
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src" / "phage_annotator"
OUTPUT = ROOT / "docs" / "SOURCE_REFERENCE.md"


def _module_name(path: Path) -> str:
    """Handle the module name helper flow."""
    rel = path.relative_to(SRC_ROOT)
    if rel.name == "__init__.py":
        parts = rel.parent.parts
    else:
        parts = rel.with_suffix("").parts
    suffix = ".".join(parts)
    return "phage_annotator" + (f".{suffix}" if suffix else "")


def _short_doc(node: ast.AST) -> str:
    """Handle the short doc helper flow."""
    docstring = ast.get_docstring(node) or ""
    first_paragraph = docstring.strip().split("\n\n", maxsplit=1)[0]
    return " ".join(first_paragraph.split())


def _public_members(tree: ast.Module) -> list[tuple[str, str, str]]:
    """Handle the public members helper flow."""
    members: list[tuple[str, str, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        doc = _short_doc(node)
        if not doc:
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        members.append((kind, node.name, doc))
    return members


def _iter_module_docs() -> list[str]:
    """Handle the iter module docs helper flow."""
    sections: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_doc = _short_doc(tree)
        members = _public_members(tree)
        if not module_doc and not members:
            continue

        lines = [f"## `{_module_name(path)}`"]
        if module_doc:
            lines.append("")
            lines.append(textwrap.fill(module_doc, width=100))
        if members:
            lines.append("")
            lines.append("Public documented symbols:")
            for kind, name, doc in members:
                lines.append(f"- `{name}` ({kind}): {doc}")
        sections.append("\n".join(lines))
    return sections


def main() -> int:
    """Write the generated source-reference document."""
    content = [
        "# Source Reference",
        "",
        "Generated from module, class, and function docstrings under `src/phage_annotator`.",
        "Regenerate with `python scripts/generate_source_reference.py` after source-docstring changes.",
        "",
        *_iter_module_docs(),
        "",
    ]
    OUTPUT.write_text("\n\n".join(content), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
