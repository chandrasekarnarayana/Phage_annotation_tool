"""Density model loader and predictor for 2D inputs."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from phage_annotator.density_config import DensityConfig
from phage_annotator.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class ModelHandle:
    model: object
    device: str
    use_amp: bool


class DensityPredictor:
    """Load and run a density map model on 2D images."""

    def __init__(self) -> None:
        self._handle: Optional[ModelHandle] = None

    def load(self, model_path: str, device: str = "auto", model_definition: Optional[str] = None) -> None:
        """Load a torchscript model or state_dict with a provided definition."""
        import torch

        path = Path(model_path)
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        use_amp = device == "cuda"
        model = None
        if path.suffix in (".pt", ".pth"):
            try:
                model = torch.jit.load(str(path), map_location=device)
                LOGGER.info("Loaded torchscript model: %s", path)
            except Exception:
                if model_definition is None:
                    raise
        if model is None:
            if model_definition is None:
                raise ValueError("State_dict checkpoint requires a model_definition with build_model().")
            model = _load_state_dict(path, model_definition, device)
            LOGGER.info("Loaded state_dict model: %s", path)
        model.eval()
        self._handle = ModelHandle(model=model, device=device, use_amp=use_amp)

    def warmup(self, shape: tuple[int, int, int, int] = (1, 1, 256, 256)) -> None:
        """Run a warmup pass to initialize model kernels."""
        if self._handle is None:
            return
        import torch

        dummy = torch.zeros(shape, device=self._handle.device)
        with torch.no_grad():
            if self._handle.use_amp:
                with torch.cuda.amp.autocast():
                    _ = self._handle.model(dummy)
            else:
                _ = self._handle.model(dummy)

    def predict(self, image2d: np.ndarray, *, config: DensityConfig) -> np.ndarray:
        """Run inference and return a float32 density map (H, W)."""
        if self._handle is None:
            raise RuntimeError("Model not loaded.")
        import torch

        arr = _prepare_input(image2d, config)
        tensor = torch.from_numpy(arr).to(self._handle.device)
        with torch.no_grad():
            if config.use_amp and self._handle.use_amp:
                with torch.cuda.amp.autocast():
                    out = self._handle.model(tensor)
            else:
                out = self._handle.model(tensor)
        out = out.detach().float().cpu().numpy()
        out = _squeeze_output(out)
        out = out * float(config.model_output_scale)
        if config.threshold_clip_min is not None:
            out = np.maximum(out, float(config.threshold_clip_min))
        return out.astype(np.float32, copy=False)

    def predict_batch(self, images: np.ndarray, *, config: DensityConfig) -> np.ndarray:
        """Run inference on a batch of 2D images and return (N, H, W)."""
        if self._handle is None:
            raise RuntimeError("Model not loaded.")
        if images.ndim != 3:
            raise ValueError("predict_batch expects shape (N, H, W).")
        import torch

        batch = np.stack([_prepare_input(img, config)[0] for img in images], axis=0)
        tensor = torch.from_numpy(batch).to(self._handle.device)
        with torch.no_grad():
            if config.use_amp and self._handle.use_amp:
                with torch.cuda.amp.autocast():
                    out = self._handle.model(tensor)
            else:
                out = self._handle.model(tensor)
        out = out.detach().float().cpu().numpy()
        if out.ndim == 4:
            out = out[:, 0, :, :]
        out = out * float(config.model_output_scale)
        if config.threshold_clip_min is not None:
            out = np.maximum(out, float(config.threshold_clip_min))
        return out.astype(np.float32, copy=False)


def _prepare_input(image2d: np.ndarray, config: DensityConfig) -> np.ndarray:
    if image2d.ndim != 2:
        raise ValueError("predict expects a 2D array.")
    arr = image2d.astype(np.float32, copy=False)
    if config.invert:
        arr = arr.max() - arr
    arr = _normalize(arr, config)
    if config.expected_channels == 1:
        arr = arr[None, None, :, :]
    else:
        arr = np.repeat(arr[None, None, :, :], config.expected_channels, axis=1)
    return arr


def _normalize(arr: np.ndarray, config: DensityConfig) -> np.ndarray:
    mode = config.normalize
    if mode == "minmax":
        vmin, vmax = float(arr.min()), float(arr.max())
        if vmax > vmin:
            arr = (arr - vmin) / (vmax - vmin)
    elif mode == "zscore":
        mean = float(arr.mean())
        std = float(arr.std())
        if std > 0:
            arr = (arr - mean) / std
    elif mode == "percentile":
        low = np.percentile(arr, config.p_low)
        high = np.percentile(arr, config.p_high)
        if high > low:
            arr = (arr - low) / (high - low)
            arr = np.clip(arr, 0.0, 1.0)
    return arr


def _squeeze_output(out: np.ndarray) -> np.ndarray:
    if out.ndim == 4:
        return out[0, 0, :, :]
    if out.ndim == 3:
        return out[0, :, :]
    if out.ndim == 2:
        return out
    raise ValueError(f"Unexpected model output shape: {out.shape}")


def _load_state_dict(path: Path, definition_path: str, device: str):
    import torch

    module = _import_definition(definition_path)
    if not hasattr(module, "build_model"):
        raise ValueError("model_definition must define build_model().")
    model = module.build_model()
    state = torch.load(str(path), map_location=device)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    model.load_state_dict(state)
    model.to(device)
    return model


def _import_definition(definition_path: str):
    path = Path(definition_path)
    spec = importlib.util.spec_from_file_location("density_model_definition", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load model definition: {definition_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module
