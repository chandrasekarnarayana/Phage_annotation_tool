"""Real-time validation hooks for automatic QC updates (M6)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt5.QtCore import QTimer

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController


class ValidationHooksMixin:
    """Mixin to add real-time validation hooks to main window.
    
    This mixin intercepts annotation modifications and automatically
    triggers QC validation with debouncing to avoid excessive re-validation.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize validation hooks."""
        super().__init__(*args, **kwargs)
        
        # Debounce timer for validation (500ms delay)
        self._validation_timer = None
        self._validation_pending = False
        self._validation_image_ids = set()
    
    def _init_validation_hooks(self):
        """Initialize validation debounce timer."""
        self._validation_timer = QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.timeout.connect(self._execute_pending_validation)
    
    def _schedule_validation(self, image_id: str = None):
        """Schedule validation with debouncing.
        
        Parameters
        ----------
        image_id : str, optional
            Specific image to validate. If None, validates all.
        """
        if not hasattr(self, '_validation_timer') or self._validation_timer is None:
            return
        
        self._validation_pending = True
        
        if image_id:
            self._validation_image_ids.add(image_id)
        
        # Reset timer (debounce effect)
        self._validation_timer.stop()
        self._validation_timer.start(500)  # 500ms delay
    
    def _execute_pending_validation(self):
        """Execute pending validation after debounce period."""
        if not self._validation_pending:
            return
        
        # Get QC orchestrator from controller
        controller = getattr(self, 'controller', None)
        if not controller:
            return
        
        qc_orchestrator = getattr(controller, 'qc_orchestrator', None)
        if not qc_orchestrator:
            return
        
        # Validate specific images or all
        if self._validation_image_ids:
            for image_id in self._validation_image_ids:
                qc_orchestrator.validate_image(image_id)
        else:
            qc_orchestrator.validate_all()
        
        # Reset state
        self._validation_pending = False
        self._validation_image_ids.clear()
        
        # Update QC panel if available
        qc_panel = getattr(self, 'qc_issues_panel', None)
        if qc_panel:
            qc_panel.refresh()
    
    def _hook_add_annotation(self, original_method):
        """Hook add annotation method to trigger validation.
        
        Parameters
        ----------
        original_method : callable
            Original _add_annotation method to wrap.
        
        Returns
        -------
        callable
            Wrapped method with validation hook.
        """
        def wrapped_add_annotation(*args, **kwargs):
            # Execute original method
            result = original_method(*args, **kwargs)
            
            # Schedule validation for affected image
            image_id = kwargs.get('image_id') or (args[0] if args else None)
            if image_id:
                self._schedule_validation(image_id)
            
            return result
        
        return wrapped_add_annotation
    
    def _hook_remove_annotation(self, original_method):
        """Hook remove annotation method to trigger validation.
        
        Parameters
        ----------
        original_method : callable
            Original _remove_annotation_near method to wrap.
        
        Returns
        -------
        callable
            Wrapped method with validation hook.
        """
        def wrapped_remove_annotation(*args, **kwargs):
            # Execute original method
            result = original_method(*args, **kwargs)
            
            # Schedule validation for affected image
            image_id = kwargs.get('image_id') or (args[0] if args else None)
            if image_id:
                self._schedule_validation(image_id)
            
            return result
        
        return wrapped_remove_annotation
    
    def _hook_modify_annotation(self, original_method):
        """Hook annotation modification method to trigger validation.
        
        Parameters
        ----------
        original_method : callable
            Original annotation modification method to wrap.
        
        Returns
        -------
        callable
            Wrapped method with validation hook.
        """
        def wrapped_modify_annotation(*args, **kwargs):
            # Execute original method
            result = original_method(*args, **kwargs)
            
            # Schedule validation for affected image
            image_id = kwargs.get('image_id') or (args[0] if args else None)
            if image_id:
                self._schedule_validation(image_id)
            
            return result
        
        return wrapped_modify_annotation
    
    def _install_validation_hooks(self):
        """Install validation hooks on annotation methods.
        
        This should be called during main window initialization after
        controller is set up.
        """
        # Initialize validation timer
        self._init_validation_hooks()
        
        # Hook annotation methods if they exist
        if hasattr(self, '_add_annotation'):
            self._add_annotation = self._hook_add_annotation(self._add_annotation)
        
        if hasattr(self, '_remove_annotation_near'):
            self._remove_annotation_near = self._hook_remove_annotation(
                self._remove_annotation_near
            )
        
        # Hook other modification methods as needed
        # (e.g., move annotation, change label, etc.)
    
    def _manual_validation_trigger(self):
        """Manually trigger validation immediately (no debounce).
        
        This can be called from the QC panel's "Validate" button.
        """
        # Stop any pending debounced validation
        if hasattr(self, '_validation_timer') and self._validation_timer:
            self._validation_timer.stop()
        
        # Execute validation immediately
        self._validation_pending = False
        self._validation_image_ids.clear()
        self._execute_pending_validation()
