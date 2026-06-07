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


from scripts.check_acyclic_imports_chunk1 import check_all_files, print_summary

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
