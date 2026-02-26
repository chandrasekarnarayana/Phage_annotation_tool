#!/usr/bin/env python3
"""Acyclic import checker for FIJI-style layer separation.

This script enforces dependency layer rules to prevent circular dependencies
and maintain clean architecture separation.

Layer Rules
-----------
1. core/ - Domain models (no dependencies on other packages)
2. io/ - I/O operations (depends on: core)
3. data/ - Data handling (depends on: core, io)
4. cache/ - Caching strategies (depends on: core, data)
5. algorithms/ - Analysis algorithms (depends on: core, data, cache)
6. framework/ - Service architecture (depends on: core)
7. tools/ - Utilities (depends on: algorithms)
8. ui_qt/ - Qt GUI (depends on: all below)
9. plugins/ - Plugin space (independent)

Example Usage
-------------
python scripts/check_acyclic_imports.py
python scripts/check_acyclic_imports.py --verbose
python scripts/check_acyclic_imports.py --fix-suggestions

Exit codes:
  0 - All checks passed
  1 - Violations found
  2 - Usage error
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Define the layer hierarchy (lower number = lower layer)
LAYER_HIERARCHY = {
    "core": 1,
    "io": 2,
    "data": 3,
    "cache": 4,
    "algorithms": 5,
    "framework": 2,  # framework is at same level as io (independent)
    "tools": 6,
    "ui_qt": 8,
    "plugins": 99,  # plugins are independent
}

# Define allowed dependencies (layer -> list of allowed lower layers)
ALLOWED_DEPENDENCIES = {
    "core": set(),
    "io": {"core"},
    "data": {"core", "io"},
    "cache": {"core", "data"},
    "algorithms": {"core", "data", "cache", "io"},
    "framework": {"core"},
    "tools": {"algorithms", "core", "data", "cache", "io"},
    "ui_qt": {"core", "io", "data", "cache", "algorithms", "framework", "tools"},
    "plugins": {"core", "io", "data", "cache", "algorithms", "framework", "tools", "ui_qt"},
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import statements."""
    
    def __init__(self):
        self.imports: List[str] = []
        self.in_type_checking = False
    
    def visit_If(self, node: ast.If) -> None:
        """Visit if statements to detect TYPE_CHECKING blocks."""
        # Check if this is an "if TYPE_CHECKING:" block
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            # Save current state
            old_state = self.in_type_checking
            self.in_type_checking = True
            
            # Visit the body
            for child in node.body:
                self.visit(child)
            
            # Restore state
            self.in_type_checking = old_state
            
            # Visit else clause if exists
            for child in node.orelse:
                self.visit(child)
        else:
            # Normal if statement
            self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit 'import X' statements."""
        if not self.in_type_checking:
            for alias in node.names:
                self.imports.append(alias.name)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit 'from X import Y' statements."""
        if not self.in_type_checking and node.module:
            self.imports.append(node.module)


def get_package_from_module(module_name: str) -> str:
    """Extract package name from full module path.
    
    Examples
    --------
    >>> get_package_from_module("phage_annotator.core.annotation")
    'core'
    >>> get_package_from_module("phage_annotator.data.models")
    'data'
    """
    parts = module_name.split(".")
    if len(parts) >= 2 and parts[0] == "phage_annotator":
        return parts[1]
    return ""


def get_imports_from_file(file_path: Path) -> List[str]:
    """Extract all import statements from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        visitor = ImportVisitor()
        visitor.visit(tree)
        return visitor.imports
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: Error parsing {file_path}: {e}", file=sys.stderr)
        return []


def check_file_imports(
    file_path: Path,
    src_root: Path,
    verbose: bool = False,
) -> List[Tuple[str, str, str, str]]:
    """Check a single file for layer violations.
    
    Returns
    -------
    list of (source_pkg, target_pkg, reason, file_path)
        List of violations found
    """
    # Determine which package this file belongs to
    try:
        relative = file_path.relative_to(src_root / "phage_annotator")
    except ValueError:
        return []  # Not in phage_annotator package
    
    source_package = relative.parts[0] if relative.parts else ""
    if source_package not in LAYER_HIERARCHY:
        return []  # Not a managed package
    
    # Extract imports
    imports = get_imports_from_file(file_path)
    
    violations = []
    for imp in imports:
        target_package = get_package_from_module(imp)
        
        if not target_package or target_package not in LAYER_HIERARCHY:
            continue  # Not a managed package, skip
        
        if target_package == source_package:
            continue  # Same package, OK
        
        # Check if dependency is allowed
        allowed = ALLOWED_DEPENDENCIES.get(source_package, set())
        if target_package not in allowed:
            reason = f"'{source_package}' cannot depend on '{target_package}'"
            violations.append((source_package, target_package, reason, str(file_path)))
            if verbose:
                print(f"  ❌ {file_path.name}: {imp} ({reason})")
    
    return violations


def check_all_files(
    src_root: Path,
    verbose: bool = False,
) -> Dict[str, List[Tuple[str, str, str, str]]]:
    """Check all Python files in the source tree.
    
    Returns
    -------
    dict
        Package name -> list of violations
    """
    violations_by_package: Dict[str, List] = {pkg: [] for pkg in LAYER_HIERARCHY}
    
    # Find all Python files
    python_files = list((src_root / "phage_annotator").rglob("*.py"))
    
    if verbose:
        print(f"Checking {len(python_files)} Python files...")
    
    for file_path in python_files:
        if "__pycache__" in str(file_path):
            continue
        
        violations = check_file_imports(file_path, src_root, verbose)
        for source_pkg, target_pkg, reason, fpath in violations:
            violations_by_package[source_pkg].append((source_pkg, target_pkg, reason, fpath))
    
    return violations_by_package


def print_summary(violations_by_package: Dict[str, List]) -> int:
    """Print violation summary.
    
    Returns
    -------
    int
        Number of total violations
    """
    total_violations = sum(len(v) for v in violations_by_package.values())
    
    if total_violations == 0:
        print("✅ All checks passed! No layer violations found.")
        return 0
    
    print(f"\n❌ Found {total_violations} layer violation(s):\n")
    
    for package, violations in violations_by_package.items():
        if not violations:
            continue
        
        print(f"Package: {package}/ ({len(violations)} violations)")
        for source_pkg, target_pkg, reason, fpath in violations:
            print(f"  - {fpath}")
            print(f"    {reason}")
        print()
    
    return total_violations


def suggest_fixes(violations_by_package: Dict[str, List]) -> None:
    """Suggest fixes for common violations."""
    print("\n💡 Suggested Fixes:\n")
    
    for package, violations in violations_by_package.items():
        if not violations:
            continue
        
        print(f"Package: {package}/")
        
        # Group by target package
        by_target: Dict[str, int] = {}
        for _, target_pkg, _, _ in violations:
            by_target[target_pkg] = by_target.get(target_pkg, 0) + 1
        
        for target_pkg, count in by_target.items():
            print(f"  - Remove {count} import(s) from '{target_pkg}'")
            print(f"    → Move shared code to a lower layer (e.g., 'core' or 'data')")
            print(f"    → Use dependency injection instead of direct imports")
            print(f"    → Consider using TYPE_CHECKING for type hints only")
        print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for acyclic import violations (FIJI-style layer separation)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Layer Hierarchy:
  1. core/       - Domain models (no dependencies)
  2. io/         - I/O operations (depends on: core)
  2. framework/  - Service architecture (depends on: core)
  3. data/       - Data handling (depends on: core, io)
  4. cache/      - Caching strategies (depends on: core, data)
  5. algorithms/ - Analysis algorithms (depends on: core, data, cache, io)
  6. tools/      - Utilities (depends on: algorithms)
  8. ui_qt/      - Qt GUI (depends on: all below)
  99. plugins/   - Plugin space (independent)
        """,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed violation information",
    )
    parser.add_argument(
        "--fix-suggestions",
        action="store_true",
        help="Print suggested fixes for violations",
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        default=Path(__file__).parent.parent / "src",
        help="Path to src/ directory (default: ../src)",
    )
    
    args = parser.parse_args()
    
    if not args.src_root.exists():
        print(f"Error: Source root not found: {args.src_root}", file=sys.stderr)
        return 2
    
    # Check all files
    violations = check_all_files(args.src_root, args.verbose)
    
    # Print summary
    total = print_summary(violations)
    
    # Print suggestions if requested
    if args.fix_suggestions and total > 0:
        suggest_fixes(violations)
    
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
