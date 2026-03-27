"""Focused builders for assist-related UI setup blocks."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets


def build_assist_controls(owner, layout, row: int) -> int:
    """Build assist/ranker controls inside the advanced settings layout."""
    r = int(row)

    owner.suggestion_auto_retrain_chk = QtWidgets.QCheckBox("Auto-retrain proposal ranker")
    owner.suggestion_auto_retrain_chk.setChecked(
        bool(owner.controller.session_state.suggestion_auto_retrain_enabled)
    )
    layout.addWidget(owner.suggestion_auto_retrain_chk, r, 0, 1, 2)
    r += 1

    owner.suggestion_min_labels_spin = QtWidgets.QSpinBox()
    owner.suggestion_min_labels_spin.setRange(5, 5000)
    owner.suggestion_min_labels_spin.setValue(
        int(owner.controller.session_state.suggestion_auto_retrain_min_labels)
    )
    layout.addWidget(QtWidgets.QLabel("Min labels for retrain"), r, 0)
    layout.addWidget(owner.suggestion_min_labels_spin, r, 1)
    r += 1

    owner.suggestion_train_now_btn = QtWidgets.QPushButton("Train Ranker Now")
    layout.addWidget(owner.suggestion_train_now_btn, r, 0, 1, 2)
    r += 1

    owner.annotation_space_combo = QtWidgets.QComboBox()
    owner.annotation_space_combo.addItems(["stack", "projection"])
    owner.annotation_space_combo.setCurrentText(
        str(getattr(owner.controller.session_state, "annotation_space", "stack"))
    )
    layout.addWidget(QtWidgets.QLabel("Annotation space"), r, 0)
    layout.addWidget(owner.annotation_space_combo, r, 1)
    r += 1

    owner.generation_space_combo = QtWidgets.QComboBox()
    owner.generation_space_combo.addItems(["stack", "projection"])
    owner.generation_space_combo.setCurrentText(
        str(getattr(owner.controller.session_state, "generation_space", "stack"))
    )
    owner.generation_space_combo.setToolTip(
        "Choose whether assist generates proposals from the active slice stack context or a projection context."
    )
    layout.addWidget(QtWidgets.QLabel("Generation space"), r, 0)
    layout.addWidget(owner.generation_space_combo, r, 1)
    r += 1

    owner.disable_bulk_accept_when_stale_chk = QtWidgets.QCheckBox(
        "Block batch accept when suggestions are stale"
    )
    owner.disable_bulk_accept_when_stale_chk.setChecked(
        bool(getattr(owner.controller.session_state, "disable_bulk_accept_when_stale", True))
    )
    owner.disable_bulk_accept_when_stale_chk.setToolTip(
        "Require an explicit one-shot override before accepting a stale batch after annotations changed."
    )
    layout.addWidget(owner.disable_bulk_accept_when_stale_chk, r, 0, 1, 2)
    r += 1

    owner.interactive_learning_experimental_chk = QtWidgets.QCheckBox(
        "Enable experimental interactive learning sidecar"
    )
    owner.interactive_learning_experimental_chk.setChecked(
        bool(owner.controller.feature_enabled("interactive_learning_experimental", False))
    )
    owner.interactive_learning_experimental_chk.setToolTip(
        "Experimental parallel learning surface. Off by default to keep assist confidence messaging reproducible."
    )
    layout.addWidget(owner.interactive_learning_experimental_chk, r, 0, 1, 2)
    r += 1

    owner.assist_min_total_spin = QtWidgets.QSpinBox()
    owner.assist_min_total_spin.setRange(1, 5000)
    owner.assist_min_total_spin.setValue(
        int(getattr(owner.controller.session_state, "assist_min_total_labels", 30))
    )
    owner.assist_min_positive_spin = QtWidgets.QSpinBox()
    owner.assist_min_positive_spin.setRange(1, 5000)
    owner.assist_min_positive_spin.setValue(
        int(getattr(owner.controller.session_state, "assist_min_positive_labels", 15))
    )
    owner.assist_min_negative_spin = QtWidgets.QSpinBox()
    owner.assist_min_negative_spin.setRange(1, 5000)
    owner.assist_min_negative_spin.setValue(
        int(getattr(owner.controller.session_state, "assist_min_negative_labels", 15))
    )
    owner.assist_min_context_spin = QtWidgets.QSpinBox()
    owner.assist_min_context_spin.setRange(1, 5000)
    owner.assist_min_context_spin.setValue(
        int(getattr(owner.controller.session_state, "assist_min_labels_per_context", 10))
    )
    owner.qc_auto_show_chk = QtWidgets.QCheckBox("Auto-show QC panel on issues")
    owner.qc_auto_show_chk.setChecked(
        bool(owner._settings.value("qcAutoShowOnIssues", True, type=bool))
    )
    layout.addWidget(QtWidgets.QLabel("Assist min total labels"), r, 0)
    layout.addWidget(owner.assist_min_total_spin, r, 1)
    r += 1
    layout.addWidget(QtWidgets.QLabel("Assist min positive labels"), r, 0)
    layout.addWidget(owner.assist_min_positive_spin, r, 1)
    r += 1
    layout.addWidget(QtWidgets.QLabel("Assist min negative labels"), r, 0)
    layout.addWidget(owner.assist_min_negative_spin, r, 1)
    r += 1
    layout.addWidget(QtWidgets.QLabel("Assist min labels/context"), r, 0)
    layout.addWidget(owner.assist_min_context_spin, r, 1)
    r += 1
    layout.addWidget(owner.qc_auto_show_chk, r, 0, 1, 2)
    r += 1

    warmup_group = QtWidgets.QGroupBox("Assist Warmup Progress")
    warmup_layout = QtWidgets.QGridLayout(warmup_group)
    owner.assist_warmup_status_lbl = QtWidgets.QLabel("Assist: Unavailable")
    owner.assist_warmup_counts_lbl = QtWidgets.QLabel("Labels total/+/-: 0/0/0")
    owner.assist_warmup_need_lbl = QtWidgets.QLabel("Need +0 total, +0 positive, +0 negative")
    owner.assist_warmup_context_lbl = QtWidgets.QLabel("Context labels: 0 (need +0)")
    owner.assist_warmup_queue_lbl = QtWidgets.QLabel("Visible uncertain queue: 0")
    owner.assist_warmup_next_btn = QtWidgets.QPushButton("Jump Next Uncertain")
    owner.assist_warmup_refresh_btn = QtWidgets.QPushButton("Refresh")
    warmup_layout.addWidget(owner.assist_warmup_status_lbl, 0, 0, 1, 2)
    warmup_layout.addWidget(owner.assist_warmup_counts_lbl, 1, 0, 1, 2)
    warmup_layout.addWidget(owner.assist_warmup_need_lbl, 2, 0, 1, 2)
    warmup_layout.addWidget(owner.assist_warmup_context_lbl, 3, 0, 1, 2)
    warmup_layout.addWidget(owner.assist_warmup_queue_lbl, 4, 0, 1, 2)
    warmup_layout.addWidget(owner.assist_warmup_next_btn, 5, 0)
    warmup_layout.addWidget(owner.assist_warmup_refresh_btn, 5, 1)
    layout.addWidget(warmup_group, r, 0, 1, 4)
    r += 1

    return r
