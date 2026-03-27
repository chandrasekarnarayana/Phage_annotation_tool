"""Assist ranker training and calibration helpers."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.qt_compat import QtWidgets


def on_suggestion_auto_retrain_changed(owner, checked: bool) -> None:
    """Persist auto-retrain enablement through the controller boundary."""
    owner.controller.set_suggestion_retrain_config(enabled=bool(checked))
    owner._settings.setValue("suggestionAutoRetrainEnabled", bool(checked))
    owner._status_info(
        "Auto-retrain enabled." if bool(checked) else "Auto-retrain disabled.",
        source="assist.training",
    )
    owner._update_status()


def on_suggestion_min_labels_changed(owner, value: int) -> None:
    """Persist the minimum labels threshold for auto-retraining."""
    min_labels = int(max(1, value))
    owner.controller.set_suggestion_retrain_config(min_labels=min_labels)
    owner._settings.setValue("suggestionAutoRetrainMinLabels", min_labels)
    owner._status_info(
        f"Auto-retrain min labels set to {min_labels}.",
        source="assist.training",
    )
    owner._update_status()


def train_suggestion_ranker_now(owner) -> None:
    """Force immediate suggestion-ranker training."""
    ok = owner.controller.train_suggestion_ranker_now()
    if ok:
        owner._status_success("Suggestion ranker trained.", source="assist.training")
    else:
        owner._status_warning(
            "Not enough labeled suggestions to train ranker.",
            source="assist.training",
        )
    owner._refresh_assist_warmup_panel()
    owner._update_status()


def show_calibration_visualizer(owner) -> None:
    """Display the acceptance-likelihood calibration plot."""
    if getattr(owner, "_settings", None) is not None and bool(
        owner._settings.value("firstRunHintCalibration", True, type=bool)
    ):
        QtWidgets.QMessageBox.information(
            owner,
            "Calibration Hint",
            "Calibration compares acceptance likelihood bins to observed acceptance.\n"
            "Use it to validate whether p_accept is reliable for this dataset.",
        )
        owner._settings.setValue("firstRunHintCalibration", False)
    rows = owner.controller.get_suggestion_calibration_samples()
    if not rows:
        QtWidgets.QMessageBox.information(
            owner,
            "Calibration Visualizer",
            "No reviewed suggestions with calibrated p_accept are available yet.",
        )
        return
    bins = np.linspace(0.0, 1.0, 11)
    centers = (bins[:-1] + bins[1:]) * 0.5
    counts = np.zeros(len(centers), dtype=int)
    acc_sum = np.zeros(len(centers), dtype=float)
    for p_accept, accepted in rows:
        idx = int(np.clip(np.digitize([p_accept], bins, right=False)[0] - 1, 0, len(centers) - 1))
        counts[idx] += 1
        acc_sum[idx] += float(accepted)
    rates = np.divide(acc_sum, np.maximum(1, counts), where=np.ones_like(acc_sum, dtype=bool))
    dlg = QtWidgets.QDialog(owner)
    dlg.setWindowTitle("Calibration Visualizer (Acceptance Likelihood)")
    layout = QtWidgets.QVBoxLayout(dlg)
    fig = plt.Figure(figsize=(6.5, 4.8), dpi=100)
    canvas = FigureCanvasQTAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], "--", color="#9e9e9e", linewidth=1.2, label="Ideal")
    mask = counts > 0
    ax.plot(centers[mask], rates[mask], "o-", color="#2e7d32", label="Observed acceptance rate")
    for idx in np.where(mask)[0]:
        ax.annotate(
            str(int(counts[idx])),
            (centers[idx], rates[idx]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=8,
        )
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Acceptance likelihood (p_accept) bin")
    ax.set_ylabel("Observed acceptance rate")
    ax.set_title("Calibration by p_accept bins")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    summary = QtWidgets.QLabel(
        f"Samples: {len(rows)} reviewed suggestions "
        f"(accepted={sum(v for _, v in rows)}, rejected={len(rows) - sum(v for _, v in rows)})"
    )
    summary.setWordWrap(True)
    layout.addWidget(summary)
    layout.addWidget(canvas)
    close_btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, parent=dlg)
    close_btn.rejected.connect(dlg.reject)
    close_btn.accepted.connect(dlg.accept)
    layout.addWidget(close_btn)
    dlg.resize(760, 560)
    dlg.exec()
