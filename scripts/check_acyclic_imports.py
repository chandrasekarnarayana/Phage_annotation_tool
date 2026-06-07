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

Compatibility imports for split chunk modules.
"""

from scripts.check_acyclic_imports_chunk1 import ImportVisitor, get_package_from_module, get_imports_from_file, check_file_imports, check_all_files, print_summary
from scripts.check_acyclic_imports_chunk2 import suggest_fixes, main

if __name__ == "__main__":
    raise SystemExit(main())
