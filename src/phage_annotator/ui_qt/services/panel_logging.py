"""Panel-specific action logging helpers.

Provides lightweight decorators and context managers for logging actions
across different UI panels without modifying core logic.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional

from phage_annotator.ui_qt.services.action_logger import get_action_logger


class PanelActionLogger:
    """Helper for logging panel-specific actions."""

    def __init__(self, panel_name: str, owner: Optional[Any] = None):
        self.panel_name = panel_name
        self.logger = get_action_logger()
        self.owner = owner  # Optional reference to GUI owner for real-time log display

    def log_click(self, button_name: str, **details) -> None:
        """Log a button click."""
        gui_callback = getattr(self.owner, "_append_log", None) if self.owner else None
        self.logger.log_action(
            "click",
            panel=self.panel_name,
            details={"button": button_name, **details},
            gui_callback=gui_callback,
        )

    def log_value_change(
        self,
        control: str,
        old_value: Any,
        new_value: Any,
        **details
    ) -> None:
        """Log a control value change."""
        gui_callback = getattr(self.owner, "_append_log", None) if self.owner else None
        self.logger.log_action(
            "value_changed",
            panel=self.panel_name,
            details={
                "control": control,
                "old_value": str(old_value),
                "new_value": str(new_value),
                **details
            },
            gui_callback=gui_callback,
        )

    def log_action(self, action: str, **details) -> None:
        """Log a custom action."""
        gui_callback = getattr(self.owner, "_append_log", None) if self.owner else None
        self.logger.log_action(
            action, 
            panel=self.panel_name, 
            details=details,
            gui_callback=gui_callback,
        )

    def log_data_operation(
        self,
        operation: str,
        item_count: int = 0,
        success: bool = True,
        error: Optional[str] = None,
        **details
    ) -> None:
        """Log data modification operations (add/delete/edit)."""
        gui_callback = getattr(self.owner, "_append_log", None) if self.owner else None
        self.logger.log_action(
            operation,
            panel=self.panel_name,
            details={"item_count": item_count, **details},
            error=error if not success else None,
            gui_callback=gui_callback,
        )
    
    def set_owner(self, owner: Any) -> None:
        """Set the GUI owner for real-time log display."""
        self.owner = owner


# Panel-specific loggers
_loggers: Dict[str, PanelActionLogger] = {}
_global_owner: Optional[Any] = None  # Global reference to main GUI window


def set_global_gui_owner(owner: Any) -> None:
    """Set the global GUI owner for all panel loggers.
    
    This allows panel loggers to display logs in the GUI window.
    """
    global _global_owner
    _global_owner = owner
    for logger in _loggers.values():
        logger.set_owner(owner)


def get_panel_logger(panel_name: str, owner: Optional[Any] = None) -> PanelActionLogger:
    """Get or create a panel-specific logger.
    
    Parameters
    ----------
    panel_name : str
        Name of the panel
    owner : Any, optional
        GUI owner for real-time log display; uses global if not provided
    """
    if panel_name not in _loggers:
        _loggers[panel_name] = PanelActionLogger(panel_name, owner=owner or _global_owner)
    else:
        # Update owner if provided
        if owner is not None:
            _loggers[panel_name].set_owner(owner)
        elif _global_owner is not None:
            _loggers[panel_name].set_owner(_global_owner)
    return _loggers[panel_name]


# Decorators for automatic logging
def log_panel_action(panel_name: str, action_name: Optional[str] = None):
    """Decorator to automatically log function calls.

    Parameters
    ----------
    panel_name : str
        Name of the panel (lazy_loader, annotate, contrast, etc)
    action_name : str, optional
        Action name; defaults to function name
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_panel_logger(panel_name)
            action = action_name or func.__name__
            try:
                result = func(*args, **kwargs)
                logger.log_action(action, success=True)
                return result
            except Exception as exc:
                logger.log_action(action, success=False, error=str(exc))
                raise
        return wrapper
    return decorator


def log_contrast_changes(panel_logger: PanelActionLogger):
    """Log contrast/display value changes.

    Parameters
    ----------
    panel_logger : PanelActionLogger
        Panel logger instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(old_min, old_max, new_min, new_max, *args, **kwargs):
            panel_logger.log_value_change(
                "contrast_range",
                f"({old_min}, {old_max})",
                f"({new_min}, {new_max})"
            )
            return func(old_min, old_max, new_min, new_max, *args, **kwargs)
        return wrapper
    return decorator


def log_annotation_batch(panel_logger: PanelActionLogger):
    """Log batch annotation operations.

    Parameters
    ----------
    panel_logger : PanelActionLogger
        Panel logger instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(annotations: list, operation: str, *args, **kwargs):
            try:
                result = func(annotations, operation, *args, **kwargs)
                panel_logger.log_data_operation(
                    f"batch_{operation}",
                    item_count=len(annotations),
                    success=True
                )
                return result
            except Exception as exc:
                panel_logger.log_data_operation(
                    f"batch_{operation}",
                    item_count=len(annotations),
                    success=False,
                    error=str(exc)
                )
                raise
        return wrapper
    return decorator
