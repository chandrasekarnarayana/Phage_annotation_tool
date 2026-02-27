"""Context/QC UI integration guide.

This module documents how to wire context actions and QC/problem-view components
into the main window and dock registry.
"""

### STEP 1: Add imports to main_window.py ###
"""
from phage_annotator.ui_qt.utils.context_menu import ContextMenuMixin
from phage_annotator.ui_qt.utils.validation_hooks import ValidationHooksMixin
"""

### STEP 2: Update KeypointAnnotator class inheritance ###
"""
class KeypointAnnotator(
    QtWidgets.QMainWindow,
    UiSetupMixin,
    UiExtrasMixin,
    JobsMixin,
    EventsMixin,
    StateMixin,
    PlaybackMixin,
    RenderingMixin,
    RoiCropMixin,
    AnnotationsMixin,
    ContextMenuMixin,  # ADD THIS - M5 context menu support
    ValidationHooksMixin,  # ADD THIS - M6 real-time validation
    ActionsMixin,
    FileActionsMixin,
    ControlsMixin,
    TableStatusMixin,
    ExportMixin,
    ModalityHelpersMixin,
    KeyboardHandlersMixin,
):
"""

### STEP 3: Add QC panel to ui_docks.py ###
"""
# In the imports section of ui_docks.py, add:
from phage_annotator.ui_qt.panels.qc_issues_panel import QCIssuesPanel

# In build_panel_registry() function, add this panel spec:
PanelSpec(
    id="qc_issues",
    title="QC Issues",
    default_area=QtCore.Qt.BottomDockWidgetArea,
    default_visible=False,
    widget_factory=self._make_qc_issues_widget,
    toggle_action_text="QC Issues",
    shortcut="Ctrl+Q",
),

# In init_panels() function, add:
self.dock_qc_issues = self.panel_docks.get("qc_issues")
self.qc_issues_panel = None
if self.dock_qc_issues:
    self.qc_issues_panel = self.dock_qc_issues.widget()
"""

### STEP 4: Add widget factory method ###
"""
# Add to ui_docks.py or appropriate mixin:

def _make_qc_issues_widget(self) -> QtWidgets.QWidget:
    '''Create QC issues panel widget.'''
    panel = QCIssuesPanel()
    
    # Connect signals
    panel.jump_to_location.connect(self._jump_to_qc_issue)
    panel.validation_requested.connect(self._trigger_qc_validation)
    panel.export_requested.connect(self._export_qc_report)
    
    return panel
"""

### STEP 5: Add signal handlers to main window ###
"""
# Add these methods to main_window.py or appropriate mixin:

def _jump_to_qc_issue(self, x: float, y: float, z: int, t: int):
    '''Jump to QC issue location.'''
    # Set time and z-slice
    self.t_slider.setValue(t)
    self.z_slider.setValue(z)
    
    # Center view on location
    ax = self.ax_frame
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    width = xlim[1] - xlim[0]
    height = ylim[1] - ylim[0]
    
    ax.set_xlim(x - width / 2, x + width / 2)
    ax.set_ylim(y - height / 2, y + height / 2)
    
    # Refresh display
    self._refresh_image()
    
    # Highlight annotation in table if possible
    # (Implementation depends on table structure)

def _trigger_qc_validation(self):
    '''Manually trigger QC validation.'''
    if hasattr(self, '_manual_validation_trigger'):
        self._manual_validation_trigger()
    elif hasattr(self.controller, 'qc_orchestrator'):
        self.controller.qc_orchestrator.validate_all()
        if self.qc_issues_panel:
            self.qc_issues_panel.refresh()

def _export_qc_report(self, format: str):
    '''Export QC report in requested format.'''
    from PyQt5.QtWidgets import QFileDialog
    from phage_annotator.io.qc_export import QCReportExporter
    
    # Prompt for save location
    ext = {'csv': 'CSV Files (*.csv)', 
           'json': 'JSON Files (*.json)', 
           'html': 'HTML Files (*.html)'}[format]
    
    filepath, _ = QFileDialog.getSaveFileName(
        self, f"Export QC Report ({format.upper()})", "", ext
    )
    
    if not filepath:
        return
    
    # Get QC state from controller
    if not hasattr(self.controller, 'qc_state'):
        self._set_status("QC system not initialized")
        return
    
    # Export report
    exporter = QCReportExporter(self.controller.qc_state)
    
    if format == 'csv':
        exporter.export_csv(filepath)
    elif format == 'json':
        exporter.export_json(filepath)
    elif format == 'html':
        exporter.export_html(filepath)
    
    self._set_status(f"QC report exported to {filepath}")
"""

### STEP 6: Integrate context menu for right-click ###
"""
# Modify AnnotationsMixin._on_click() in annotations.py to handle right-click:

def _on_click(self, event) -> None:
    '''Handle canvas click events.'''
    if event.inaxes == self.ax_frame and event.xdata is not None and event.ydata is not None:
        fx, fy = self._to_full_coords(self.ax_frame, event.xdata, event.ydata)
        self._set_cursor_xy(fx, fy, refresh=False)
    
    # Handle right-click for context menu
    if event.button == 3 and hasattr(self, '_show_annotation_context_menu'):
        if event.inaxes == self.ax_frame and event.xdata is not None and event.ydata is not None:
            fx, fy = self._to_full_coords(self.ax_frame, event.xdata, event.ydata)
            
            # Get global position for menu
            from PyQt5.QtCore import QPoint
            canvas = event.canvas
            pos = canvas.mapToGlobal(QPoint(int(event.x), int(canvas.height() - event.y)))
            
            # Show context menu
            self._show_annotation_context_menu(fx, fy, pos)
            return
    
    # Normal left-click handling
    if self.tool_router is not None:
        self.tool_router.on_click(event)
"""

### STEP 7: Install validation hooks ###
"""
# In main window __init__ or _finalize_setup(), add:

# Install validation hooks after controller is initialized
if hasattr(self, '_install_validation_hooks'):
    self._install_validation_hooks()
"""

### STEP 8: Initialize QC system in controller ###
"""
# In SessionController initialization or main window setup:

from phage_annotator.analysis.qc_validators import QCOrchestrator
from phage_annotator.session.qc_state import QCState

# Create QC state
self.qc_state = QCState()

# Create QC orchestrator
self.qc_orchestrator = QCOrchestrator(
    controller=self,
    qc_state=self.qc_state
)

# Register with QC panel if it exists
if hasattr(self, 'qc_issues_panel') and self.qc_issues_panel:
    self.qc_issues_panel.set_qc_state(self.qc_state)
"""

### STEP 9: Add batch operation menu actions ###
"""
# In menu setup (e.g., ui_extra.py or main_window.py):

qc_menu = self.menuBar().addMenu("&QC")

validate_all_action = qc_menu.addAction("Validate All Images")
validate_all_action.triggered.connect(self._trigger_qc_validation)
validate_all_action.setShortcut("Ctrl+Shift+V")

qc_menu.addSeparator()

fix_duplicates_action = qc_menu.addAction("Fix All Duplicates")
fix_duplicates_action.triggered.connect(self._batch_fix_duplicates)

fix_out_of_bounds_action = qc_menu.addAction("Delete Out-of-Bounds")
fix_out_of_bounds_action.triggered.connect(self._batch_fix_out_of_bounds)

assign_labels_action = qc_menu.addAction("Assign Missing Labels...")
assign_labels_action.triggered.connect(self._batch_assign_labels)

qc_menu.addSeparator()

show_qc_panel_action = qc_menu.addAction("Show QC Panel")
show_qc_panel_action.triggered.connect(lambda: self.dock_qc_issues.setVisible(True))
show_qc_panel_action.setShortcut("Ctrl+Q")
"""

### STEP 10: Implement batch operation handlers ###
"""
# Add these methods to main window:

def _batch_fix_duplicates(self):
    '''Fix all duplicate annotation issues.'''
    from phage_annotator.session.batch_commands import BatchDeleteDuplicatesCommand
    
    if not hasattr(self.controller, 'qc_state'):
        return
    
    # Get duplicate issues
    issues = self.controller.qc_state.get_filtered_issues()
    duplicate_issues = [i for i in issues if i.issue_type == 'duplicate']
    
    if not duplicate_issues:
        self._set_status("No duplicate issues found")
        return
    
    # Execute batch command
    cmd = BatchDeleteDuplicatesCommand(self.controller, duplicate_issues)
    self.controller.command_manager.execute(cmd)
    
    # Re-validate and refresh
    self._trigger_qc_validation()
    self._refresh_image()
    
    self._set_status(f"Fixed {len(duplicate_issues)} duplicate issues")

def _batch_fix_out_of_bounds(self):
    '''Delete all out-of-bounds annotations.'''
    from phage_annotator.session.batch_commands import BatchDeleteOutOfBoundsCommand
    from PyQt5.QtWidgets import QMessageBox
    
    if not hasattr(self.controller, 'qc_state'):
        return
    
    # Get out-of-bounds issues
    issues = self.controller.qc_state.get_filtered_issues()
    oob_issues = [i for i in issues if i.issue_type == 'out_of_bounds']
    
    if not oob_issues:
        self._set_status("No out-of-bounds issues found")
        return
    
    # Confirm deletion
    reply = QMessageBox.question(
        self,
        "Confirm Deletion",
        f"Delete {len(oob_issues)} out-of-bounds annotations?",
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply != QMessageBox.Yes:
        return
    
    # Execute batch command
    cmd = BatchDeleteOutOfBoundsCommand(self.controller, oob_issues)
    self.controller.command_manager.execute(cmd)
    
    # Re-validate and refresh
    self._trigger_qc_validation()
    self._refresh_image()
    
    self._set_status(f"Deleted {len(oob_issues)} out-of-bounds annotations")

def _batch_assign_labels(self):
    '''Assign labels to all unlabeled annotations.'''
    from phage_annotator.session.batch_commands import BatchAssignLabelCommand
    from PyQt5.QtWidgets import QInputDialog
    
    if not hasattr(self.controller, 'qc_state'):
        return
    
    # Get missing label issues
    issues = self.controller.qc_state.get_filtered_issues()
    missing_label_issues = [i for i in issues if i.issue_type == 'missing_label']
    
    if not missing_label_issues:
        self._set_status("No missing label issues found")
        return
    
    # Prompt for label
    label, ok = QInputDialog.getText(
        self,
        "Assign Label",
        f"Enter label for {len(missing_label_issues)} unlabeled annotations:"
    )
    
    if not ok or not label:
        return
    
    # Execute batch command
    cmd = BatchAssignLabelCommand(self.controller, missing_label_issues, label)
    self.controller.command_manager.execute(cmd)
    
    # Re-validate and refresh
    self._trigger_qc_validation()
    self._refresh_image()
    
    self._set_status(f"Assigned label '{label}' to {len(missing_label_issues)} annotations")
"""

### INTEGRATION CHECKLIST ###
"""
✅ 1. Add ContextMenuMixin and ValidationHooksMixin to KeypointAnnotator inheritance
✅ 2. Add QC panel spec to build_panel_registry() in ui_docks.py
✅ 3. Implement _make_qc_issues_widget() factory method
✅ 4. Add signal handlers: _jump_to_qc_issue, _trigger_qc_validation, _export_qc_report
✅ 5. Modify _on_click() to handle right-click (button == 3)
✅ 6. Call _install_validation_hooks() after controller initialization
✅ 7. Initialize qc_state and qc_orchestrator in controller/main window
✅ 8. Add QC menu with validation and batch operation actions
✅ 9. Implement batch operation handlers
✅ 10. Test context menu, QC panel, validation, and batch operations
"""

### DEPENDENCIES ###
"""
The following modules must exist:
- src/phage_annotator/ui_qt/utils/context_menu.py (M5 - CREATED)
- src/phage_annotator/ui_qt/utils/validation_hooks.py (M6 - CREATED)
- src/phage_annotator/ui_qt/panels/qc_issues_panel.py (M6 - EXISTS)
- src/phage_annotator/session/batch_commands.py (M6 - CREATED)
- src/phage_annotator/session/context_commands.py (M5 - should exist from previous work)
- src/phage_annotator/analysis/qc_validators.py (M6 - should exist)
- src/phage_annotator/analysis/qc_state.py (M6 - should exist)
- src/phage_annotator/analysis/qc_export.py (M6 - should exist)
"""
