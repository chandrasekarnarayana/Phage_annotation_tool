"""GPU availability checking utilities."""

from __future__ import annotations

from typing import Optional, Tuple

from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)


def check_cuda_available() -> Tuple[bool, str]:
    """Check if CUDA/GPU is available for inference.
    
    Returns
    -------
    tuple[bool, str]
        (is_available, message) where message explains any issues.
    """
    try:
        import torch
        
        if not torch.cuda.is_available():
            return False, "CUDA is not available. PyTorch was not compiled with CUDA support or no GPU detected."
        
        device_count = torch.cuda.device_count()
        if device_count == 0:
            return False, "No CUDA devices found."
            
        device_name = torch.cuda.get_device_name(0)
        return True, f"CUDA available: {device_name} ({device_count} device(s))"
        
    except ImportError:
        return False, "PyTorch is not installed. Cannot use GPU acceleration."
    except Exception as e:
        return False, f"Error checking CUDA: {e}"


def get_recommended_device(requested_device: str = "auto") -> Tuple[str, Optional[str]]:
    """Get recommended device for inference, with optional warning message.
    
    Parameters
    ----------
    requested_device : str
        One of "auto", "cuda", "cpu"
    
    Returns
    -------
    tuple[str, str | None]
        (device, warning_message) where warning_message is None if no issues.
    """
    if requested_device == "cpu":
        return "cpu", None
        
    cuda_available, cuda_message = check_cuda_available()
    
    if requested_device == "cuda":
        if not cuda_available:
            return "cpu", f"CUDA requested but not available: {cuda_message}. Falling back to CPU."
        return "cuda", None
        
    # requested_device == "auto"
    if cuda_available:
        LOGGER.info(cuda_message)
        return "cuda", None
    else:
        LOGGER.info(f"Using CPU: {cuda_message}")
        return "cpu", None
