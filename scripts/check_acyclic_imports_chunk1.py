"""Split chunk from check_acyclic_imports.py."""


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
        """Initialize the object and prepare its runtime state."""
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
