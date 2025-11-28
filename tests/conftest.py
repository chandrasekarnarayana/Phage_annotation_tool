import pytest


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
