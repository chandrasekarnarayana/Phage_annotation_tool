from __future__ import annotations

from dataclasses import dataclass

from phage_annotator.smlm.widget import SmlmDockWidget


@dataclass
class _Loc:
    frame_index: int
    x_px: float
    y_px: float
    sigma_px: float
    photons: float
    background: float
    uncertainty_px: float
    label: str = ""


def test_smlm_widget_renders_localizations_and_selection(qtbot, tmp_path) -> None:
    widget = SmlmDockWidget()
    qtbot.addWidget(widget)
    widget.set_localizations(
        [
            _Loc(0, 10.0, 20.0, 1.2, 300.0, 5.0, 0.2),
            _Loc(1, 11.0, 21.0, 1.1, 250.0, 4.5, 0.3),
        ]
    )

    assert widget.results_table.rowCount() == 2
    assert widget.add_ann_btn.text() == "Add All (2)"

    widget.results_table.selectRow(1)

    assert widget.selected_localization_indices() == [1]
    assert widget.add_ann_btn.text() == "Add Selected (1)"
    assert "selected" in widget.results_summary_lbl.text().lower()

    out = tmp_path / "smlm.csv"
    widget.export_localizations_csv(str(out))
    text = out.read_text(encoding="utf-8")
    assert "frame_index,x_px,y_px" in text
    assert "11.0000" in text


def test_smlm_widget_clear_localizations_disables_add(qtbot) -> None:
    widget = SmlmDockWidget()
    qtbot.addWidget(widget)
    widget.set_localizations([_Loc(0, 1.0, 2.0, 1.0, 10.0, 1.0, 0.1)])

    widget.clear_localizations()

    assert widget.results_table.rowCount() == 0
    assert widget.add_ann_btn.isEnabled() is False
    assert widget.results_summary_lbl.text() == "No localizations yet."
