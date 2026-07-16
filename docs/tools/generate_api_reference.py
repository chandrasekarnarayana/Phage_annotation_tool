"""Generate Sphinx API reference pages from the source tree.

The generated pages are intentionally simple: one page per module, one package
index per top-level package, and autosummary entries for public classes and
functions discovered with the Python AST.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "phage_annotator"
API = ROOT / "docs" / "api"
GENERATED = API / "generated"
PACKAGE = "phage_annotator"
SKIP_PARTS = {"__pycache__"}
SKIP_MODULES = {"__main__"}


def module_name(path: Path) -> str:
    """Return the import name for a Python source file."""
    rel = path.relative_to(SRC).with_suffix("")
    parts = [PACKAGE, *rel.parts]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def public_members(path: Path) -> tuple[list[str], list[str], list[str]]:
    """Return public object names and Qt signal attributes defined in a module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return [], [], []
    classes: list[str] = []
    functions: list[str] = []
    signals: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                if len(item.targets) != 1 or not isinstance(item.targets[0], ast.Name):
                    continue
                if (
                    isinstance(item.value, ast.Call)
                    and isinstance(item.value.func, ast.Attribute)
                    and item.value.func.attr == "pyqtSignal"
                ):
                    signals.append(item.targets[0].id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            functions.append(node.name)
    return classes, functions, sorted(set(signals))


def iter_module_files() -> list[Path]:
    """Return importable module files in stable order."""
    files: list[Path] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        if path.stem in SKIP_MODULES:
            continue
        files.append(path)
    return files


def title(text: str, marker: str = "=") -> str:
    """Return an reStructuredText title block."""
    return f"{text}\n{marker * len(text)}\n\n"


def write_module_page(path: Path) -> str:
    """Write the API page for one module and return its document name."""
    name = module_name(path)
    doc_name = f"generated/{name}"
    out = API / f"{doc_name}.rst"
    out.parent.mkdir(parents=True, exist_ok=True)
    classes, functions, signals = public_members(path)
    lines = [
        title(name),
        f".. automodule:: {name}\n",
        "   :members:\n",
        "   :undoc-members:\n",
        "   :show-inheritance:\n",
        "   :no-index:\n\n",
    ]
    if signals:
        lines.insert(-1, f"   :exclude-members: {', '.join(signals)}\n")
    if classes or functions:
        lines.append("Public objects\n--------------\n\n")
    if classes:
        lines.append("Classes\n~~~~~~~\n\n")
        lines.extend(f"- :class:`~{name}.{item}`\n" for item in classes)
        lines.append("\n")
    if functions:
        lines.append("Functions\n~~~~~~~~~\n\n")
        lines.extend(f"- :func:`~{name}.{item}`\n" for item in functions)
        lines.append("\n")
    out.write_text("".join(lines), encoding="utf-8")
    return doc_name


def write_package_indexes(module_docs: list[str]) -> None:
    """Write the top-level API index and package-group pages."""
    by_group: dict[str, list[str]] = {}
    for doc in module_docs:
        parts = doc.split(".")
        group = parts[1] if len(parts) > 1 else PACKAGE
        by_group.setdefault(group, []).append(doc)

    index_lines = [
        title("API Reference"),
        "These pages are generated from source-code docstrings.\n\n",
        ".. toctree::\n",
        "   :maxdepth: 2\n\n",
    ]
    for group in sorted(by_group):
        page = f"generated/{PACKAGE}.{group}" if group != PACKAGE else f"generated/{PACKAGE}"
        index_lines.append(f"   {page}\n")
    (API / "index.rst").write_text("".join(index_lines), encoding="utf-8")

    for group, docs in sorted(by_group.items()):
        page_name = f"{PACKAGE}.{group}" if group != PACKAGE else PACKAGE
        page_path = GENERATED / f"{page_name}.rst"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_doc = f"generated/{page_name}"
        lines = [title(page_name), ".. toctree::\n", "   :maxdepth: 1\n\n"]
        lines.extend(f"   ../{doc}\n" for doc in sorted(docs) if doc != page_doc)
        page_path.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    """Generate API reference pages."""
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    module_docs = [write_module_page(path) for path in iter_module_files()]
    write_package_indexes(module_docs)
    print(f"Generated {len(module_docs)} API module pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
