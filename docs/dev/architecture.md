Architecture Boundaries
======================

Core vs UI layers
-----------------
The codebase is split into core (logic/data) and UI/controller layers:

Core modules (Qt-free):
- `src/phage_annotator/io.py`
- `src/phage_annotator/analysis.py`
- `src/phage_annotator/annotations.py`
- `src/phage_annotator/project_io.py`
- `src/phage_annotator/projection_cache.py`
- `src/phage_annotator/pyramid.py`
- `src/phage_annotator/ring_buffer.py`
- `src/phage_annotator/session_state.py`

UI/controller modules (Qt-allowed):
- `src/phage_annotator/gui_mpl.py`
- `src/phage_annotator/session_controller.py`
- `src/phage_annotator/session_controller_*.py`
- `src/phage_annotator/ui_actions.py`
- `src/phage_annotator/ui_docks.py`
- `src/phage_annotator/gui_controls*.py`
- `src/phage_annotator/tools.py`
- `src/phage_annotator/logger.py`
- `src/phage_annotator/jobs.py`
- `src/phage_annotator/render_mpl.py`

Rules
-----
- Core modules must not import Qt (`PyQt*`, `PySide*`, `QtCore`, `QtWidgets`).
- Core modules should expose pure functions and data structures only.
- UI/controller modules adapt core data to Qt widgets and signals.
- Any new Qt usage must remain in UI/controller layers.

Guard
-----
Run `python scripts/check_core_no_qt.py` to ensure core modules remain Qt-free.
