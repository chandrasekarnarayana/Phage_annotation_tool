"""Pytest configuration for local and CI test policy.

This conftest centralizes:
- import-path bootstrapping for ``src/``
- explicit GUI test opt-in via ``--run-gui``
- auto-detection and marking of Qt-dependent test modules
- collection-time exclusion of GUI modules in core runs
"""

from __future__ import annotations

import os
import re
import sys
from importlib.util import find_spec
from functools import lru_cache
from pathlib import Path

import matplotlib
import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

GUI_CONTENT_HINTS = (
    "from PyQt5",
    "import PyQt5",
    "qtbot",
    "pytestqt",
    "matplotlib.backends.qt_compat",
    "ui_qt.panels",
    "ui_qt.dialogs",
    "ui_qt.widgets",
)

# Fast directory-level bypass for the dedicated GUI integration suite.
GUI_DIRECTORY_HINTS = ("tests/integration/gui/",)
GUI_WORD_RE = re.compile(r"\bgui\b")
NOT_GUI_RE = re.compile(r"\bnot\s*(?:\(\s*)?gui\b")


def _to_path(path_like: object) -> Path:
    """Normalize py.path/pathlib values from different pytest versions."""
    return Path(str(path_like))


def _is_gui_requested(config: pytest.Config) -> bool:
    """Return True when GUI tests are explicitly requested."""
    if config.getoption("--run-gui"):
        return True
    marker_expr = (config.getoption("-m") or "").strip().lower()
    if not marker_expr:
        return False
    if NOT_GUI_RE.search(marker_expr):
        return False
    return bool(GUI_WORD_RE.search(marker_expr))


@lru_cache(maxsize=None)
def _is_gui_test_file(path_str: str) -> bool:
    """Return True when a test module depends on Qt/GUI runtime."""
    path = Path(path_str)
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return False

    normalized = path.as_posix()
    if any(hint in normalized for hint in GUI_DIRECTORY_HINTS):
        return True

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(hint in content for hint in GUI_CONTENT_HINTS)


def _is_gui_collection_path(path_like: object) -> bool:
    """Check whether a collected path belongs to the GUI test slice."""
    path = _to_path(path_like)
    normalized = path.as_posix()
    if path.is_dir():
        return any(hint.rstrip("/") in normalized for hint in GUI_DIRECTORY_HINTS)
    return _is_gui_test_file(str(path))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add CLI switch to opt-in GUI test execution."""
    parser.addoption(
        "--run-gui",
        action="store_true",
        default=False,
        help="Run GUI tests (requires Qt backend / Xvfb).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used by suite selection policy."""
    config.addinivalue_line("markers", "gui: GUI tests that require a Qt backend/Xvfb")


def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    """Skip GUI collection in core runs to avoid import-time Qt failures."""
    if _is_gui_requested(config):
        return False
    return _is_gui_collection_path(collection_path)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-mark GUI tests and skip them unless explicitly requested."""
    run_gui = _is_gui_requested(config)
    skip_gui = pytest.mark.skip(reason="Use --run-gui (or -m gui) to run GUI tests.")
    skip_missing_pyqt = pytest.mark.skip(reason="PyQt5 is not installed in this environment.")
    skip_unsupported_runtime = pytest.mark.skip(
        reason="GUI tests are disabled on this Python runtime; use the CI-supported GUI runtime (py3.11)."
    )
    has_pyqt = find_spec("PyQt5") is not None
    unsupported_gui_runtime = sys.version_info >= (3, 13)

    for item in items:
        item_path = _to_path(getattr(item, "path", getattr(item, "fspath", "")))
        if _is_gui_test_file(str(item_path)):
            item.add_marker("gui")

        if not run_gui and "gui" in item.keywords:
            item.add_marker(skip_gui)
        if run_gui and "gui" in item.keywords and not has_pyqt:
            item.add_marker(skip_missing_pyqt)
        if run_gui and "gui" in item.keywords and unsupported_gui_runtime:
            item.add_marker(skip_unsupported_runtime)


if find_spec("pytest_benchmark") is None:

    @pytest.fixture
    def benchmark():
        """Provide a lightweight fallback for pytest-benchmark in local runs."""
        def _run(fn, *args, **kwargs):
            """Execute the benchmarked callable once."""
            return fn(*args, **kwargs)

        return _run


# Ensure a safe backend/environment for GUI tests under CI/headless.
if "CI" in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("MPLBACKEND", "Agg")
matplotlib.use(os.environ.get("MPLBACKEND", "Agg"), force=True)
