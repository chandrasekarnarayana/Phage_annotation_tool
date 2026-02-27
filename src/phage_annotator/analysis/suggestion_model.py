"""Model-in-the-loop point suggestion adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol

import numpy as np

from phage_annotator.core.annotation import PointSuggestion


class SuggestionModel(Protocol):
    """Interface for proposal models used by assisted annotation."""

    model_name: str

    def predict(
        self,
        image_slice: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
    ) -> List[PointSuggestion]:
        """Generate candidate point suggestions for one 2D slice."""


@dataclass
class LocalPeakSuggestionModel:
    """Fast baseline model using local maxima as candidate points."""

    min_distance_px: int = 6
    max_points: int = 200
    threshold_quantile: float = 0.995
    anisotropic_radius_x: float | None = None
    anisotropic_radius_y: float | None = None
    scale_sigma: float = 1.0
    model_name: str = "local_peaks"

    @staticmethod
    def _gaussian_fit_features(arr: np.ndarray, y: int, x: int) -> tuple[float, float, float]:
        """Estimate Gaussian-like spot features from a local patch.

        Returns
        -------
        amplitude_fit : float
            Estimated amplitude above local background.
        sigma_fit : float
            Isotropic sigma estimate from second moments.
        residual_fit : float
            RMSE between normalized patch and normalized Gaussian model.
        """
        h, w = arr.shape
        r = 3
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        patch = np.asarray(arr[y0:y1, x0:x1], dtype=np.float64)
        if patch.size == 0:
            return 0.0, 1.0, 1.0

        background = float(np.nanmedian(patch))
        signal = patch - background
        signal[~np.isfinite(signal)] = 0.0
        signal = np.maximum(signal, 0.0)
        amplitude = float(np.max(signal)) if signal.size else 0.0
        if amplitude <= 1e-8:
            return 0.0, 1.0, 1.0

        yy, xx = np.mgrid[0 : signal.shape[0], 0 : signal.shape[1]]
        cx = float(x - x0)
        cy = float(y - y0)
        total = float(np.sum(signal)) + 1e-8
        var_x = float(np.sum(signal * (xx - cx) ** 2) / total)
        var_y = float(np.sum(signal * (yy - cy) ** 2) / total)
        sigma = float(max(0.3, np.sqrt(max(1e-8, 0.5 * (var_x + var_y)))))

        gauss = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma))
        gauss = amplitude * gauss
        # Compare normalized shapes to make residual scale-robust.
        obs = signal / (amplitude + 1e-8)
        mod = gauss / (amplitude + 1e-8)
        residual = float(np.sqrt(np.mean((obs - mod) ** 2)))
        return amplitude, sigma, residual

    def _corrected_image(self, arr: np.ndarray) -> np.ndarray:
        """Simple illumination correction proxy: subtract local mean."""
        padded = np.pad(arr, ((1, 1), (1, 1)), mode="reflect")
        local_mean = (
            padded[:-2, :-2]
            + padded[:-2, 1:-1]
            + padded[:-2, 2:]
            + padded[1:-1, :-2]
            + padded[1:-1, 1:-1]
            + padded[1:-1, 2:]
            + padded[2:, :-2]
            + padded[2:, 1:-1]
            + padded[2:, 2:]
        ) / 9.0
        corrected = arr - local_mean
        corrected -= float(np.nanmin(corrected))
        return corrected

    def _collect_candidates(
        self,
        arr: np.ndarray,
        *,
        threshold_quantile: float,
        source_modality: str,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        roi_id: str | None,
    ) -> list[PointSuggestion]:
        finite = np.isfinite(arr)
        if not finite.any():
            return []
        values = arr[finite]
        threshold = float(np.quantile(values, threshold_quantile))
        baseline = float(np.nanmedian(values))
        std = float(np.nanstd(values)) + 1e-8
        h, w = arr.shape
        rows: list[tuple[float, PointSuggestion]] = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                center = float(arr[y, x])
                if not np.isfinite(center) or center < threshold:
                    continue
                window = arr[y - 1 : y + 2, x - 1 : x + 2]
                if center < float(np.nanmax(window)):
                    continue
                local_mean = float(np.nanmean(window))
                local_std = float(np.nanstd(window)) + 1e-8
                local_contrast = center - local_mean
                snr = (center - baseline) / std
                peak_score = center
                amplitude_fit, sigma_fit, residual_fit = self._gaussian_fit_features(arr, y, x)
                laplace = (
                    float(arr[y - 1, x]) + float(arr[y + 1, x]) + float(arr[y, x - 1]) + float(arr[y, x + 1]) - 4.0 * center
                )
                rows.append(
                    (
                        peak_score,
                        PointSuggestion(
                            image_id=int(image_id),
                            image_name=str(image_name),
                            t=int(t),
                            z=int(z),
                            y=float(y),
                            x=float(x),
                            score=0.0,
                            label=str(label),
                            source_model=self.model_name,
                            source_modality=source_modality,
                            scale_sigma=float(self.scale_sigma),
                            psf_radius=float(self.min_distance_px),
                            roi_id=roi_id,
                            score_components={
                                "peak": float(peak_score),
                                "snr": float(snr),
                                "local_contrast": float(local_contrast),
                                "local_std": float(local_std),
                                "local_background": float(local_mean),
                                "log_response": float(-laplace),
                                "amplitude_fit": float(amplitude_fit),
                                "sigma_fit": float(sigma_fit),
                                "residual_fit": float(residual_fit),
                            },
                            meta={"raw_peak": float(center)},
                        ),
                    )
                )
        if not rows:
            return []
        rows.sort(key=lambda r: r[0], reverse=True)
        max_peak = max(1e-8, float(rows[0][0]))
        for peak, suggestion in rows:
            comp = suggestion.score_components
            peak_norm = float(peak / max_peak)
            snr_norm = float(max(0.0, min(1.0, comp["snr"] / 8.0)))
            contrast_norm = float(max(0.0, min(1.0, abs(comp["local_contrast"]) / (abs(max_peak) + 1e-8))))
            residual_penalty = float(max(0.0, min(1.0, 1.0 - comp.get("residual_fit", 1.0))))
            suggestion.score = float(
                0.45 * peak_norm + 0.2 * snr_norm + 0.15 * contrast_norm + 0.2 * residual_penalty
            )
        return [row[1] for row in rows]

    def _nms(self, candidates: list[PointSuggestion]) -> list[PointSuggestion]:
        radius_x = float(self.anisotropic_radius_x or self.min_distance_px)
        radius_y = float(self.anisotropic_radius_y or self.min_distance_px)
        if radius_x <= 0 or radius_y <= 0:
            return list(candidates)
        picked: list[PointSuggestion] = []
        for suggestion in sorted(candidates, key=lambda s: float(s.score), reverse=True):
            keep = True
            for prev in picked:
                dx = (float(prev.x) - float(suggestion.x)) / radius_x
                dy = (float(prev.y) - float(suggestion.y)) / radius_y
                if dx * dx + dy * dy < 1.0:
                    keep = False
                    break
            if keep:
                picked.append(suggestion)
            if len(picked) >= int(self.max_points):
                break
        return picked

    @staticmethod
    def _consensus(raw: list[PointSuggestion], corrected: list[PointSuggestion], radius: float) -> list[PointSuggestion]:
        if not raw or not corrected:
            return []
        out: list[PointSuggestion] = []
        radius2 = float(max(1.0, radius) ** 2)
        for a in raw:
            for b in corrected:
                dx = float(a.x) - float(b.x)
                dy = float(a.y) - float(b.y)
                if dx * dx + dy * dy > radius2:
                    continue
                merged = PointSuggestion(
                    image_id=a.image_id,
                    image_name=a.image_name,
                    t=a.t,
                    z=a.z,
                    y=float((a.y + b.y) / 2.0),
                    x=float((a.x + b.x) / 2.0),
                    score=float((a.score + b.score) / 2.0),
                    label=a.label,
                    source_model=a.source_model,
                    source_modality="consensus",
                    scale_sigma=a.scale_sigma,
                    psf_radius=a.psf_radius,
                    roi_id=a.roi_id,
                    score_components={
                        "raw_score": float(a.score),
                        "corrected_score": float(b.score),
                    },
                    meta={"consensus": True},
                )
                out.append(merged)
                break
        return out

    def predict(
        self,
        image_slice: np.ndarray,
        *,
        image_id: int,
        image_name: str,
        t: int,
        z: int,
        label: str,
        strategy: str = "raw",
        threshold_min_score: float = 0.0,
        roi_id: str | None = None,
    ) -> List[PointSuggestion]:
        arr = np.asarray(image_slice)
        if arr.ndim != 2 or arr.size == 0:
            return []
        strategy_key = str(strategy or "raw").strip().lower()
        raw_candidates = self._collect_candidates(
            arr,
            threshold_quantile=self.threshold_quantile,
            source_modality="raw",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
        )
        corrected = self._corrected_image(arr)
        corrected_candidates = self._collect_candidates(
            corrected,
            threshold_quantile=self.threshold_quantile,
            source_modality="corrected",
            image_id=image_id,
            image_name=image_name,
            t=t,
            z=z,
            label=label,
            roi_id=roi_id,
        )
        if strategy_key in ("corrected",):
            selected = corrected_candidates
        elif strategy_key in ("consensus",):
            selected = self._consensus(raw_candidates, corrected_candidates, float(self.min_distance_px))
        else:
            selected = raw_candidates
        nms_selected = self._nms(selected)
        ranked = sorted(
            [s for s in nms_selected if float(s.score) >= float(threshold_min_score)],
            key=lambda s: float(s.score),
            reverse=True,
        )
        return ranked[: int(self.max_points)]


def summarize_suggestion_feedback(
    suggestions: Iterable[PointSuggestion],
    accepted_ids: set[str],
) -> dict:
    """Compute simple acceptance summary for reporting."""
    ids = [s.suggestion_id for s in suggestions]
    accepted = sum(1 for sid in ids if sid in accepted_ids)
    total = len(ids)
    return {
        "total": total,
        "accepted": accepted,
        "rejected": max(0, total - accepted),
        "accept_rate": (accepted / total) if total else 0.0,
    }
