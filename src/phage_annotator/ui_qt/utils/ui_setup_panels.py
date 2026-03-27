"""Panel policy builders for the main UI setup mixin."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.utils import ui_docks


def build_panel_policy_controls(owner) -> None:
    """Build per-panel auto-open and pin controls in Preferences."""
    if getattr(owner, "advanced_layout", None) is None:
        return
    if getattr(owner, "panel_policy_group", None) is not None:
        return
    group = QtWidgets.QGroupBox("Panel Auto-Open & Pinning")
    group.setCheckable(False)
    layout = QtWidgets.QGridLayout(group)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setHorizontalSpacing(12)
    layout.setVerticalSpacing(6)
    layout.addWidget(QtWidgets.QLabel("Panel"), 0, 0)
    layout.addWidget(QtWidgets.QLabel("Auto-open"), 0, 1)
    layout.addWidget(QtWidgets.QLabel("Pinned"), 0, 2)
    owner.panel_policy_auto_checks = {}
    owner.panel_policy_pin_checks = {}
    owner.panel_policy_open_btns = {}
    row = 1
    for spec in list(getattr(owner, "panel_specs", []) or []):
        panel_id = str(spec.id)
        label = QtWidgets.QLabel(str(spec.title))
        auto_chk = QtWidgets.QCheckBox()
        pin_chk = QtWidgets.QCheckBox()
        open_btn = QtWidgets.QPushButton("Open")
        open_btn.setMaximumWidth(56)
        open_btn.clicked.connect(lambda _checked=False, pid=panel_id: owner.open_panel(pid, reason="panel_policy"))
        auto_chk.toggled.connect(lambda checked, pid=panel_id: owner.set_panel_auto_open_enabled(pid, bool(checked)))
        pin_chk.toggled.connect(lambda checked, pid=panel_id: owner.set_panel_pinned(pid, bool(checked)))
        layout.addWidget(label, row, 0)
        layout.addWidget(auto_chk, row, 1)
        layout.addWidget(pin_chk, row, 2)
        layout.addWidget(open_btn, row, 3)
        owner.panel_policy_auto_checks[panel_id] = auto_chk
        owner.panel_policy_pin_checks[panel_id] = pin_chk
        owner.panel_policy_open_btns[panel_id] = open_btn
        row += 1
    reset_btn = QtWidgets.QPushButton("Reset Auto-Open Defaults")
    reset_btn.clicked.connect(owner._reset_panel_auto_open_defaults)
    layout.addWidget(reset_btn, row, 0, 1, 2)
    owner.panel_policy_reset_btn = reset_btn
    owner.panel_policy_group = group
    owner.advanced_layout.addWidget(group, owner._advanced_layout_row, 0, 1, 4)
    owner._advanced_layout_row += 1


def refresh_panel_policy_controls(owner) -> None:
    """Sync panel policy checkboxes with persisted/current policy state."""
    if hasattr(ui_docks, "refresh_panel_policy_actions"):
        try:
            ui_docks.refresh_panel_policy_actions(owner)
        except Exception:
            pass
    for panel_id, chk in dict(getattr(owner, "panel_policy_auto_checks", {}) or {}).items():
        desired = bool(owner.is_panel_auto_open_enabled(panel_id))
        if chk.isChecked() != desired:
            chk.blockSignals(True)
            chk.setChecked(desired)
            chk.blockSignals(False)
    for panel_id, chk in dict(getattr(owner, "panel_policy_pin_checks", {}) or {}).items():
        desired = bool(owner.is_panel_pinned(panel_id))
        if chk.isChecked() != desired:
            chk.blockSignals(True)
            chk.setChecked(desired)
            chk.blockSignals(False)
