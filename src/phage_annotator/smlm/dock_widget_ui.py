"""UI construction mixin for the ThunderSTORM SMLM parameter panel.

Organises controls into logical groups that match the ThunderSTORM pipeline
stages: image filtering, candidate detection, Gaussian fitting, post-filtering,
super-resolution rendering, backend/bridge configuration, and reproducibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets

from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins
from phage_annotator.smlm.platform_utils import (
    fiji_executable_placeholder,
    fiji_app_placeholder,
    thunderstorm_jar_placeholder,
    discover_fiji_executable,
)


class DockWidgetUiMixin:
    """Builds the SMLM parameter panel UI.

    All QWidget attribute names must remain stable — they are referenced by
    :class:`~phage_annotator.smlm.dock_widget_handlers.DockWidgetHandlersMixin`
    and :meth:`values`.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._localizations: list = []
        self._scroll = QtWidgets.QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll)

        container = QtWidgets.QWidget()
        self._scroll.setWidget(container)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._build_acquisition_group(layout)
        self._build_filter_group(layout)
        self._build_detection_group(layout)
        self._build_fitting_group(layout)
        self._build_postfilter_group(layout)
        self._build_render_group(layout)
        self._build_backend_group(layout)
        self._build_run_controls(layout)
        self._build_debug_group(layout)
        self._build_reproducibility_controls(layout)
        self._build_export_controls(layout)
        self._build_results_group(layout)
        layout.addStretch(1)

        self._plugin_descriptors = {}
        self._populate_plugin_list()
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        self.backend_combo.currentIndexChanged.connect(self._refresh_effective_config)
        self.fiji_exec_edit.textChanged.connect(self._refresh_effective_config)
        self.fiji_macro_edit.textChanged.connect(self._refresh_effective_config)
        self.thunderstorm_jar_edit.textChanged.connect(self._refresh_effective_config)
        self.fiji_command_template_edit.textChanged.connect(self._refresh_effective_config)
        self.pyimagej_app_edit.textChanged.connect(self._refresh_effective_config)
        self.filter_combo.currentIndexChanged.connect(self._refresh_dog_visibility)
        self._refresh_dog_visibility()

        # Fiji / ThunderSTORM find & download buttons
        self.find_fiji_btn.clicked.connect(self._handle_find_fiji)
        self.download_fiji_btn.clicked.connect(self._handle_download_fiji)
        self.find_jar_btn.clicked.connect(self._handle_find_thunderstorm_jar)
        self.download_jar_btn.clicked.connect(self._handle_download_thunderstorm_jar)

        # Auto-detect bundled ThunderSTORM JAR
        bundled = discover_bundled_thunderstorm_jar()
        if bundled is not None:
            self.thunderstorm_jar_edit.setText(str(Path(bundled)))
            self.thunderstorm_jar_edit.setToolTip(
                "Auto-detected bundled ThunderSTORM JAR.\n"
                "Exposed as PHAGE_THUNDERSTORM_JAR in bridge runs."
            )
            self.jar_status_lbl.setText(f"Bundled: {bundled}")
        else:
            self.jar_status_lbl.setText("Not found — click 'Find in Fiji' or 'Download'.")

        # Auto-detect Fiji installation for the current platform
        fiji_exe = discover_fiji_executable()
        if fiji_exe:
            self.fiji_exec_edit.setText(fiji_exe)
            self.fiji_exec_edit.setToolTip(
                f"Auto-detected Fiji executable: {fiji_exe}\n"
                "Override by entering a different path or browsing."
            )
            self.fiji_status_lbl.setText(f"Found: {fiji_exe}")
        else:
            self.fiji_status_lbl.setText("Not found — click 'Find' or 'Download'.")

        self._refresh_effective_config()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_acquisition_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Microscope / acquisition metadata used for physical-unit conversion."""
        grp = QtWidgets.QGroupBox("Acquisition")
        grp.setToolTip("Physical acquisition parameters required for nm-unit results.")
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.pixel_size_spin = QtWidgets.QDoubleSpinBox()
        self.pixel_size_spin.setRange(1.0, 1000.0)
        self.pixel_size_spin.setDecimals(2)
        self.pixel_size_spin.setSingleStep(1.0)
        self.pixel_size_spin.setValue(100.0)
        self.pixel_size_spin.setSuffix(" nm/px")
        self.pixel_size_spin.setToolTip(
            "Camera pixel size at the sample plane (physical pixel pitch ÷ objective magnification).\n"
            "Used to convert pixel-space localisation uncertainties to nanometres.\n"
            "Example: 6.5 µm pixel pitch ÷ 100× objective = 65 nm/px."
        )
        g.addRow("Pixel size", self.pixel_size_spin)

        self.em_wavelength_spin = QtWidgets.QSpinBox()
        self.em_wavelength_spin.setRange(400, 800)
        self.em_wavelength_spin.setValue(680)
        self.em_wavelength_spin.setSuffix(" nm")
        self.em_wavelength_spin.setToolTip(
            "Emission wavelength of the fluorophore (nm).\n"
            "Used only for reference — does not affect the localisation algorithm.\n"
            "Typical values: Alexa 647 → 680 nm, mEos3.2 → 585 nm."
        )
        g.addRow("Emission wavelength", self.em_wavelength_spin)

        layout.addWidget(grp)

    def _build_filter_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Band-pass image filter applied before candidate detection."""
        grp = QtWidgets.QGroupBox("Image Filter")
        grp.setToolTip(
            "Band-pass filter applied to the raw camera frame before peak detection.\n"
            "The filter suppresses high-frequency shot noise and low-frequency "
            "background, enhancing single-molecule contrast."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItem("Wavelet B-spline (recommended)", "wavelet_bspline")
        self.filter_combo.addItem("Difference-of-Gaussians (DoG)", "dog")
        self.filter_combo.setToolTip(
            "Wavelet B-spline: a multi-scale wavelet decomposition ideal for PALM/STORM "
            "with high emitter density. Preserves sub-diffractive structures.\n"
            "DoG: difference of two Gaussian-smoothed images; simpler and faster."
        )
        g.addRow("Filter type", self.filter_combo)

        self.sigma_spin = QtWidgets.QDoubleSpinBox()
        self.sigma_spin.setRange(0.4, 6.0)
        self.sigma_spin.setDecimals(2)
        self.sigma_spin.setSingleStep(0.1)
        self.sigma_spin.setValue(1.3)
        self.sigma_spin.setToolTip(
            "Expected PSF standard deviation in pixels.\n"
            "Approximated as: σ ≈ 0.21 × λ_em / (NA × pixel_size_nm).\n"
            "For λ = 680 nm, NA 1.4, pixel = 100 nm: σ ≈ 1.0 px.\n"
            "Typical range: 0.8–2.5 px. Overestimating broadens detections; "
            "underestimating misses weak emitters."
        )
        g.addRow("PSF sigma (px)", self.sigma_spin)

        # DoG-specific parameters (hidden unless dog is selected)
        self.dog_sigma1_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma1_spin.setRange(0.5, 5.0)
        self.dog_sigma1_spin.setDecimals(2)
        self.dog_sigma1_spin.setSingleStep(0.1)
        self.dog_sigma1_spin.setValue(1.0)
        self.dog_sigma1_spin.setToolTip(
            "Inner Gaussian σ for DoG filter (≈ PSF σ).\n"
            "Should be close to the expected PSF standard deviation."
        )
        self.dog_sigma2_spin = QtWidgets.QDoubleSpinBox()
        self.dog_sigma2_spin.setRange(0.8, 8.0)
        self.dog_sigma2_spin.setDecimals(2)
        self.dog_sigma2_spin.setSingleStep(0.1)
        self.dog_sigma2_spin.setValue(2.0)
        self.dog_sigma2_spin.setToolTip(
            "Outer Gaussian σ for DoG filter (typically 1.6 × sigma1).\n"
            "Controls the spatial frequency band-pass; "
            "increasing widens the accepted PSF size range."
        )
        self._dog_sigma1_row = g.rowCount()
        g.addRow("DoG σ₁ (px)", self.dog_sigma1_spin)
        g.addRow("DoG σ₂ (px)", self.dog_sigma2_spin)

        layout.addWidget(grp)

    def _build_detection_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Candidate emitter detection via local maxima and MAD thresholding."""
        grp = QtWidgets.QGroupBox("Candidate Detection")
        grp.setToolTip(
            "Identifies candidate emitter positions as local intensity maxima "
            "above a threshold defined relative to the estimated background noise."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.det_thr_spin = QtWidgets.QDoubleSpinBox()
        self.det_thr_spin.setRange(0.5, 20.0)
        self.det_thr_spin.setDecimals(2)
        self.det_thr_spin.setSingleStep(0.5)
        self.det_thr_spin.setValue(3.0)
        self.det_thr_spin.setToolTip(
            "Detection threshold expressed as multiples of the median absolute "
            "deviation (MAD) of the filtered image.\n"
            "Threshold = median + k × 1.4826 × MAD  (≈ k × σ_noise for Gaussian noise).\n"
            "Lower values detect weaker emitters but increase false positives.\n"
            "Typical range: 1.5–5 MAD σ. Start at 3 and adjust based on the "
            "false-positive rate observed in the localisation results."
        )
        g.addRow("Threshold (MAD σ)", self.det_thr_spin)

        self.max_candidates_spin = QtWidgets.QSpinBox()
        self.max_candidates_spin.setRange(100, 50000)
        self.max_candidates_spin.setSingleStep(500)
        self.max_candidates_spin.setValue(5000)
        self.max_candidates_spin.setToolTip(
            "Maximum number of candidate positions accepted per frame.\n"
            "Acts as a density limiter to prevent excessive computation in "
            "high-density frames (e.g., early acquisition before bleaching).\n"
            "If localisation count per frame consistently saturates this limit, "
            "increase the detection threshold."
        )
        g.addRow("Max candidates / frame", self.max_candidates_spin)

        layout.addWidget(grp)

    def _build_fitting_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """2-D Gaussian maximum-likelihood localisation fitting."""
        grp = QtWidgets.QGroupBox("Gaussian Fitting")
        grp.setToolTip(
            "Fits a symmetric 2-D Gaussian to the intensity profile at each "
            "candidate position to refine sub-pixel coordinates, amplitude, "
            "and localisation precision (Cramér–Rao lower bound estimate)."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.fit_radius_spin = QtWidgets.QSpinBox()
        self.fit_radius_spin.setRange(2, 12)
        self.fit_radius_spin.setValue(4)
        self.fit_radius_spin.setToolTip(
            "Half-width of the fitting window in pixels (radius, not diameter).\n"
            "The fitting region spans (2 × radius + 1) × (2 × radius + 1) pixels.\n"
            "Should be ≥ 2 × PSF σ to capture >95 % of emitter photons.\n"
            "Typical values: 3–6 px. Larger windows are slower and may include "
            "neighbouring emitters in dense samples."
        )
        g.addRow("Fit radius (px)", self.fit_radius_spin)

        layout.addWidget(grp)

    def _build_postfilter_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Quality filters applied after Gaussian fitting."""
        grp = QtWidgets.QGroupBox("Post-localisation Filters")
        grp.setToolTip(
            "Quality-control filters applied to fitted localisations.\n"
            "Removes low-photon-count detections (likely noise) and "
            "high-uncertainty localisations (poor fit quality)."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.min_photons_spin = QtWidgets.QDoubleSpinBox()
        self.min_photons_spin.setRange(0.0, 100000.0)
        self.min_photons_spin.setDecimals(0)
        self.min_photons_spin.setSingleStep(50.0)
        self.min_photons_spin.setValue(50.0)
        self.min_photons_spin.setToolTip(
            "Minimum integrated photon count per localisation.\n"
            "Estimated from the Gaussian fit amplitude: N ≈ A × 2π σ².\n"
            "Localisations with N < min_photons are discarded as likely noise.\n"
            "A rough guide: SNR ≈ √N; for SNR > 5, use min_photons ≥ 25.\n"
            "The Cramér–Rao bound on position precision scales as σ / √N."
        )
        g.addRow("Min photons", self.min_photons_spin)

        self.max_uncertainty_spin = QtWidgets.QDoubleSpinBox()
        self.max_uncertainty_spin.setRange(1.0, 500.0)
        self.max_uncertainty_spin.setDecimals(1)
        self.max_uncertainty_spin.setSingleStep(5.0)
        self.max_uncertainty_spin.setValue(30.0)
        self.max_uncertainty_spin.setSuffix(" nm")
        self.max_uncertainty_spin.setToolTip(
            "Maximum allowable localisation precision (1σ, in nanometres).\n"
            "Computed from the Gaussian fit covariance and photon count.\n"
            "Typical ThunderSTORM precision: 5–30 nm for STORM.\n"
            "Localisations with σ_loc > max_uncertainty_nm are rejected."
        )
        g.addRow("Max uncertainty", self.max_uncertainty_spin)

        self.merge_radius_spin = QtWidgets.QDoubleSpinBox()
        self.merge_radius_spin.setRange(0.0, 10.0)
        self.merge_radius_spin.setDecimals(2)
        self.merge_radius_spin.setSingleStep(0.25)
        self.merge_radius_spin.setValue(1.0)
        self.merge_radius_spin.setSuffix(" px")
        self.merge_radius_spin.setToolTip(
            "Localisation merging radius in pixels.\n"
            "Pairs of localisations within this distance across consecutive frames "
            "are merged (averaged). This corrects for emitters that remain active "
            "across multiple frames, which would otherwise appear as multiple "
            "distinct localisations and inflate density estimates.\n"
            "Set to 0 to disable merging. Recommended: ≈ 1 × PSF σ."
        )
        g.addRow("Merge radius", self.merge_radius_spin)

        layout.addWidget(grp)

    def _build_render_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Super-resolution image rendering options."""
        grp = QtWidgets.QGroupBox("Super-Resolution Rendering")
        grp.setToolTip(
            "Renders a super-resolution reconstruction from the accepted localisations."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.upsample_spin = QtWidgets.QSpinBox()
        self.upsample_spin.setRange(2, 20)
        self.upsample_spin.setValue(8)
        self.upsample_spin.setToolTip(
            "Upsampling factor for the SR reconstruction grid.\n"
            "The SR image pixel size = camera pixel size ÷ upsample.\n"
            "Example: 100 nm/px × 8× = 12.5 nm/px SR pixel.\n"
            "Increasing beyond the localisation precision does not improve "
            "spatial resolution but increases memory usage."
        )
        g.addRow("Upsample factor", self.upsample_spin)

        self.render_combo = QtWidgets.QComboBox()
        self.render_combo.addItem("Histogram (fastest)", "histogram")
        self.render_combo.addItem("Gaussian (recommended)", "gaussian")
        self.render_combo.setCurrentText("Gaussian (recommended)")
        self.render_combo.setToolTip(
            "Histogram: each localisation contributes a single pixel; fast but "
            "sensitive to grid alignment artefacts.\n"
            "Gaussian: each localisation is rendered as a 2-D Gaussian with σ = "
            "render_sigma_nm, producing a visually smooth SR image."
        )
        g.addRow("Render mode", self.render_combo)

        self.render_sigma_spin = QtWidgets.QDoubleSpinBox()
        self.render_sigma_spin.setRange(0.5, 200.0)
        self.render_sigma_spin.setDecimals(1)
        self.render_sigma_spin.setSingleStep(1.0)
        self.render_sigma_spin.setValue(10.0)
        self.render_sigma_spin.setSuffix(" nm")
        self.render_sigma_spin.setToolTip(
            "Gaussian kernel width for SR rendering (in nanometres at the sample plane).\n"
            "Should approximate the mean localisation precision of accepted events.\n"
            "Typical values: 10–30 nm for STORM/PALM data.\n"
            "Setting this to the measured precision creates a physiologically "
            "meaningful probability-density SR image."
        )
        g.addRow("Render σ", self.render_sigma_spin)

        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["Photons", "Uncertainty (nm)", "Frame index", "Uniform"])
        self.color_mode_combo.setToolTip(
            "Colour-encode the SR point cloud by a localisation property.\n"
            "Photons: brighter = more detected photons.\n"
            "Uncertainty: colour reflects localisation precision (lower = more precise).\n"
            "Frame index: temporal colour-coding to visualise acquisition dynamics."
        )
        g.addRow("Colour by", self.color_mode_combo)

        layout.addWidget(grp)

    def _build_backend_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Fiji bridge / execution backend selection."""
        grp = QtWidgets.QGroupBox("Execution Backend")
        grp.setToolTip(
            "Controls how the ThunderSTORM Fiji plugin is invoked.\n"
            "'Internal': pure-Python pipeline (no Fiji required).\n"
            "'fiji_subprocess': headless Fiji process via subprocess.\n"
            "'fiji_pyimagej': Fiji via the PyImageJ Python bridge."
        )
        g = QtWidgets.QFormLayout(grp)
        g.setLabelAlignment(QtCore.Qt.AlignRight)

        self.backend_combo = QtWidgets.QComboBox()
        self.backend_combo.addItem("Internal (pure Python, no Fiji)", "internal")
        self.backend_combo.addItem("Fiji subprocess (headless)", "fiji_subprocess")
        self.backend_combo.addItem("Fiji via PyImageJ", "fiji_pyimagej")
        g.addRow("Backend", self.backend_combo)

        self.plugin_combo = QtWidgets.QComboBox()
        self.plugin_combo.setToolTip(
            "External Fiji JAR plugin. Discovered from the external_plugins/ directory.\n"
            "Select to auto-populate the JAR path and macro path fields."
        )
        g.addRow("Plugin", self.plugin_combo)

        self.fiji_exec_edit = QtWidgets.QLineEdit()
        self.fiji_exec_edit.setPlaceholderText(fiji_executable_placeholder())
        self.fiji_exec_edit.setToolTip("Path to the Fiji executable (ImageJ binary).")
        browse_exec_btn = QtWidgets.QToolButton()
        browse_exec_btn.setText("…")
        browse_exec_btn.clicked.connect(lambda: self._browse_file(self.fiji_exec_edit, "Fiji executable"))
        self.find_fiji_btn = QtWidgets.QToolButton()
        self.find_fiji_btn.setText("Find")
        self.find_fiji_btn.setToolTip("Auto-detect Fiji on this system (searches standard and Downloads locations).")
        self.download_fiji_btn = QtWidgets.QToolButton()
        self.download_fiji_btn.setText("Download")
        self.download_fiji_btn.setToolTip("Download Fiji from downloads.imagej.net and extract to the user application folder.")
        exec_row = QtWidgets.QHBoxLayout()
        exec_row.addWidget(self.fiji_exec_edit)
        exec_row.addWidget(browse_exec_btn)
        exec_row.addWidget(self.find_fiji_btn)
        exec_row.addWidget(self.download_fiji_btn)
        exec_widget = QtWidgets.QWidget()
        exec_widget.setLayout(exec_row)
        exec_widget.layout().setContentsMargins(0, 0, 0, 0)
        g.addRow("Fiji executable", exec_widget)

        self.fiji_status_lbl = QtWidgets.QLabel("")
        self.fiji_status_lbl.setToolTip("Shows the detected or downloaded Fiji path.")
        self.fiji_status_lbl.setWordWrap(True)
        g.addRow("", self.fiji_status_lbl)

        self.fiji_macro_edit = QtWidgets.QLineEdit()
        self.fiji_macro_edit.setPlaceholderText("/path/to/thunderstorm_macro.ijm")
        self.fiji_macro_edit.setToolTip("ImageJ macro (.ijm) invoked by the Fiji bridge.")
        browse_macro_btn = QtWidgets.QToolButton()
        browse_macro_btn.setText("…")
        browse_macro_btn.clicked.connect(lambda: self._browse_file(self.fiji_macro_edit, "Fiji macro", "ImageJ macros (*.ijm *.bsh);;All files (*)"))
        macro_row = QtWidgets.QHBoxLayout()
        macro_row.addWidget(self.fiji_macro_edit)
        macro_row.addWidget(browse_macro_btn)
        macro_widget = QtWidgets.QWidget()
        macro_widget.setLayout(macro_row)
        macro_widget.layout().setContentsMargins(0, 0, 0, 0)
        g.addRow("Fiji macro / script", macro_widget)

        self.thunderstorm_jar_edit = QtWidgets.QLineEdit()
        self.thunderstorm_jar_edit.setPlaceholderText(thunderstorm_jar_placeholder())
        self.thunderstorm_jar_edit.setToolTip(
            "Path to the ThunderSTORM JAR file.\n"
            "Auto-detected from the bundled JARs directory if available."
        )
        browse_jar_btn = QtWidgets.QToolButton()
        browse_jar_btn.setText("…")
        browse_jar_btn.clicked.connect(lambda: self._browse_file(self.thunderstorm_jar_edit, "ThunderSTORM JAR", "JAR files (*.jar);;All files (*)"))
        self.find_jar_btn = QtWidgets.QToolButton()
        self.find_jar_btn.setText("Find in Fiji")
        self.find_jar_btn.setToolTip("Search for ThunderSTORM inside the Fiji installation specified above.")
        self.download_jar_btn = QtWidgets.QToolButton()
        self.download_jar_btn.setText("Download")
        self.download_jar_btn.setToolTip("Download ThunderSTORM JAR from GitHub and save to the user application folder.")
        jar_row = QtWidgets.QHBoxLayout()
        jar_row.addWidget(self.thunderstorm_jar_edit)
        jar_row.addWidget(browse_jar_btn)
        jar_row.addWidget(self.find_jar_btn)
        jar_row.addWidget(self.download_jar_btn)
        jar_widget = QtWidgets.QWidget()
        jar_widget.setLayout(jar_row)
        jar_widget.layout().setContentsMargins(0, 0, 0, 0)
        g.addRow("Plugin JAR", jar_widget)

        self.jar_status_lbl = QtWidgets.QLabel("")
        self.jar_status_lbl.setToolTip("Shows the detected or downloaded ThunderSTORM JAR path.")
        self.jar_status_lbl.setWordWrap(True)
        g.addRow("", self.jar_status_lbl)

        self.fiji_command_template_edit = QtWidgets.QLineEdit()
        self.fiji_command_template_edit.setPlaceholderText(
            "{fiji_executable} --headless -macro {macro_path} "
            "'input=\"{input_tif}\",output=\"{output_csv}\",params=\"{params_json}\"'"
        )
        self.fiji_command_template_edit.setToolTip(
            "Optional command template override for the Fiji subprocess call.\n"
            "Supported tokens: {fiji_executable}, {macro_path}, "
            "{input_tif}, {output_csv}, {params_json}."
        )
        g.addRow("Command template", self.fiji_command_template_edit)

        self.pyimagej_app_edit = QtWidgets.QLineEdit()
        self.pyimagej_app_edit.setPlaceholderText(fiji_app_placeholder())
        self.pyimagej_app_edit.setToolTip(
            "Path to Fiji.app directory used by the PyImageJ backend.\n"
            "Required only when backend = 'fiji_pyimagej'."
        )
        g.addRow("PyImageJ app path", self.pyimagej_app_edit)

        layout.addWidget(grp)

    def _build_run_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        btn_row = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run SMLM (ROI)")
        self.run_btn.setToolTip("Run the full SMLM localisation pipeline on the current ROI.")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.preflight_btn = QtWidgets.QPushButton("Preflight check")
        self.preflight_btn.setToolTip(
            "Validate the Fiji bridge configuration before running: checks the "
            "executable, macro file, JAR plugin, and output path."
        )
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.preflight_btn)
        layout.addLayout(btn_row)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)

        self.fixit_group = QtWidgets.QGroupBox("Guided Fix")
        self.fixit_group.setVisible(False)
        fixit_layout = QtWidgets.QVBoxLayout(self.fixit_group)
        self.fixit_title_label = QtWidgets.QLabel("")
        self.fixit_title_label.setStyleSheet("font-weight: 600;")
        self.fixit_detail_label = QtWidgets.QLabel("")
        self.fixit_detail_label.setWordWrap(True)
        fixit_layout.addWidget(self.fixit_title_label)
        fixit_layout.addWidget(self.fixit_detail_label)
        self.fixit_actions_layout = QtWidgets.QHBoxLayout()
        self.fixit_actions_layout.addStretch(1)
        fixit_layout.addLayout(self.fixit_actions_layout)
        layout.addWidget(self.fixit_group)

    def _build_debug_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.effective_config_view = QtWidgets.QPlainTextEdit()
        self.effective_config_view.setReadOnly(True)
        self.effective_config_view.setMaximumHeight(140)
        self.effective_config_view.setPlaceholderText("Effective bridge configuration (JSON)")
        self.execution_group = QtWidgets.QGroupBox("Execution Plan / Debug")
        self.execution_group.setCheckable(True)
        self.execution_group.setChecked(False)
        execution_layout = QtWidgets.QVBoxLayout(self.execution_group)
        execution_layout.addWidget(self.effective_config_view)
        debug_btn_row = QtWidgets.QHBoxLayout()
        self.show_macro_btn = QtWidgets.QPushButton("Show Generated Macro")
        self.copy_debug_btn = QtWidgets.QPushButton("Copy Debug Report")
        debug_btn_row.addWidget(self.show_macro_btn)
        debug_btn_row.addWidget(self.copy_debug_btn)
        debug_btn_row.addStretch(1)
        execution_layout.addLayout(debug_btn_row)
        self.generated_macro_view = QtWidgets.QPlainTextEdit()
        self.generated_macro_view.setReadOnly(True)
        self.generated_macro_view.setVisible(False)
        self.generated_macro_view.setPlaceholderText("Generated / executed macro content")
        self.generated_macro_view.setMaximumHeight(140)
        execution_layout.addWidget(self.generated_macro_view)
        layout.addWidget(self.execution_group)
        self.show_macro_btn.clicked.connect(self._toggle_generated_macro_view)
        self.copy_debug_btn.clicked.connect(self._copy_debug_report)

    def _build_reproducibility_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        runbook_group = QtWidgets.QGroupBox("Reproducibility")
        runbook_group.setToolTip(
            "Runbook mode captures the exact parameter set, macro text, and "
            "bridge configuration so that an analysis run can be reproduced "
            "exactly on the same or a different system."
        )
        runbook_layout = QtWidgets.QHBoxLayout(runbook_group)
        self.repro_mode_chk = QtWidgets.QCheckBox("Runbook mode")
        self.repro_mode_chk.setToolTip(
            "Enable to record all bridge parameters and executed macro content "
            "alongside results for provenance and audit purposes."
        )
        self.lock_profile_btn = QtWidgets.QPushButton("Lock Profile")
        self.lock_profile_btn.setToolTip(
            "Lock the current parameter profile to prevent accidental changes "
            "during a multi-session acquisition campaign."
        )
        self.export_runbook_btn = QtWidgets.QPushButton("Export Runbook")
        self.export_runbook_btn.setToolTip(
            "Export a self-contained runbook bundle (parameters + macro + metadata) "
            "that can be replayed with: phage-annotator-smlm-run-demo --runbook <file>"
        )
        runbook_layout.addWidget(self.repro_mode_chk)
        runbook_layout.addWidget(self.lock_profile_btn)
        runbook_layout.addWidget(self.export_runbook_btn)
        runbook_layout.addStretch(1)
        layout.addWidget(runbook_group)

    def _build_export_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        export_row = QtWidgets.QHBoxLayout()
        self.export_csv_btn = QtWidgets.QPushButton("Export CSV")
        self.export_csv_btn.setToolTip(
            "Export localisation list to a CSV file compatible with ThunderSTORM "
            "and SMLM Analyzer."
        )
        self.export_h5_btn = QtWidgets.QPushButton("Export HDF5")
        self.export_h5_btn.setToolTip(
            "Export localisation list to HDF5 format with full metadata "
            "(compatible with Picasso and SMLM analysis tools)."
        )
        self.add_ann_btn = QtWidgets.QPushButton("Add to Annotations")
        self.add_ann_btn.setEnabled(False)
        self.add_ann_btn.setToolTip(
            "Import the localisation centroids as point annotations in the "
            "annotation layer for downstream QC and manual curation."
        )
        export_row.addWidget(self.export_csv_btn)
        export_row.addWidget(self.export_h5_btn)
        export_row.addWidget(self.add_ann_btn)
        layout.addLayout(export_row)

    def _build_results_group(self, layout: QtWidgets.QVBoxLayout) -> None:
        results_group = QtWidgets.QGroupBox("Localisation Results")
        results_layout = QtWidgets.QVBoxLayout(results_group)
        summary_row = QtWidgets.QHBoxLayout()
        self.results_summary_lbl = QtWidgets.QLabel("No localisations yet.")
        summary_row.addWidget(self.results_summary_lbl)
        summary_row.addStretch(1)
        self.show_points_chk = QtWidgets.QCheckBox("Overlay on canvas")
        self.show_points_chk.setChecked(True)
        self.show_points_chk.setToolTip(
            "Render accepted localisation positions as overlay points on the "
            "main image canvas."
        )
        summary_row.addWidget(self.show_points_chk)
        results_layout.addLayout(summary_row)

        self.results_table = QtWidgets.QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels(
            ["Frame", "X (px)", "Y (px)", "Sigma (px)", "Photons", "Uncertainty (nm)", "Merged"]
        )
        self.results_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.results_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setMinimumHeight(160)
        results_layout.addWidget(self.results_table)

        results_btn_row = QtWidgets.QHBoxLayout()
        self.copy_results_btn = QtWidgets.QPushButton("Copy Rows")
        self.select_all_results_btn = QtWidgets.QPushButton("Select All")
        self.clear_selection_btn = QtWidgets.QPushButton("Clear Selection")
        results_btn_row.addWidget(self.copy_results_btn)
        results_btn_row.addWidget(self.select_all_results_btn)
        results_btn_row.addWidget(self.clear_selection_btn)
        results_btn_row.addStretch(1)
        results_layout.addLayout(results_btn_row)
        layout.addWidget(results_group)

        self.results_table.itemSelectionChanged.connect(self._update_selection_state)
        self.results_table.customContextMenuRequested.connect(self._open_results_context_menu)
        self.copy_results_btn.clicked.connect(self._copy_selected_results)
        self.select_all_results_btn.clicked.connect(self.results_table.selectAll)
        self.clear_selection_btn.clicked.connect(self.results_table.clearSelection)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_dog_visibility(self) -> None:
        is_dog = (self.filter_combo.currentData() == "dog")
        self.dog_sigma1_spin.setEnabled(is_dog)
        self.dog_sigma2_spin.setEnabled(is_dog)

    def _browse_file(
        self,
        line_edit: QtWidgets.QLineEdit,
        title: str,
        file_filter: str = "All files (*)",
    ) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, f"Select {title}", "", file_filter)
        if path:
            line_edit.setText(path)
