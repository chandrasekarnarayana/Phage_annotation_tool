import os
import sys
from pathlib import Path

import matplotlib
import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def pytest_addoption(parser):
    parser.addoption(
        "--run-gui",
        action="store_true",
        default=False,
        help="Run GUI tests (requires Qt backend / Xvfb).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "gui: GUI tests that require a Qt backend/Xvfb")


def pytest_collection_modifyitems(config, items):
    run_gui = config.getoption("--run-gui")
    selected_marker = config.getoption("-m")
    marker_includes_gui = selected_marker and "gui" in selected_marker

    if run_gui or marker_includes_gui:
        return

    skip_gui = pytest.mark.skip(reason="Use --run-gui or -m gui to run GUI tests.")
    for item in items:
        if "gui" in item.keywords:
            item.add_marker(skip_gui)


# Ensure a safe backend/environment for GUI tests under CI/headless
if "CI" in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("MPLBACKEND", "Agg")
matplotlib.use(os.environ.get("MPLBACKEND", "Agg"), force=True)
