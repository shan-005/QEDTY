"""Split-conformal ordinal severity prediction for Seraph findings.

This implementation provides a deterministic calibration/prediction mechanism
without claiming conditional or universal coverage. Empirical coverage is a
property of the calibrated method under its data assumptions and must be
validated on held-out data.
"""

from __future__ import annotations

import math

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from seraph.sources.repository.scanners.base import Finding, Severity


_SEVERITIES = [
    Severity.CRITICAL.value,
    Severity.HIGH.value,
    Severity.MEDIUM.value,
    Severity.LOW.value,
    Severity.INFO.value,
]
_INDEX = {value: i for i, value in enumerate(_SEVERITIES)}
_CANONICAL = {value: value for value in _SEVERITIES}


def _severity_value(finding: Finding) -> str:
    value = getattr(finding, "effective_severity", None) or getattr(
        finding, "severity", Severity.INFO
    )
    text = str(getattr(value, "value", value)).lower()
    return _CANONICAL.get(text, Severity.INFO.value)


def _clip(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = low
    if not math.isfinite(x):
        x = low
    return max(low, min(high, x))


@dataclass(frozen=True)
class PredictionResult:
    point_prediction: str
    prediction_set: list[str]
    coverage_guarantee: float
    calibrated: bool
    alpha: float
    calibration_size: int
    nonconformity_score: float
    lower: float | None = None
    upper: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def conformal_lower(self) -> float | None:
        return self.lower

    @property
    def conformal_upper(self) -> float | None:
        return self.upper

    @property
    def confidence(self) -> float:
        if self.calibrated:
            return self.coverage_guarantee
        return _clip(1.0 - self.nonconformity_score)


class ConformalPredictionEngine:
    """Deterministic split-conformal ordinal severity engine."""

    def __init__(self, alpha: float = 0.1, min_calibration_size: int = 30) -> None:
        alpha = float(alpha)
        alpha_error = "alpha must be strictly between 0 and 1"
        if not 0.0 < alpha < 1.0:
            raise ValueError(alpha_error)

        self.alpha = alpha
        self.min_calibration_size = max(1, int(min_calibration_size))
        self.calibration_scores: list[float] = []
        self.calibration_quantile: float | None = None
        self.is_calibrated = False
        self.last_prediction: PredictionResult | None = None

    @property
    def calibration_size(self) -> int:
        return len(self.calibration_scores)

    def reset(self) -> None:
        self.calibration_scores.clear()
        self.calibration_quantile = None
        self.is_calibrated = False
        self.last_prediction = None

    def _score_for_observed(self, finding: Finding) -> float:
        # Higher confidence => lower nonconformity. The score is deliberately
        # bounded and deterministic so it can be calibrated with a finite sample.
        confidence = _clip(getattr(finding, "confidence", 0.0))
        return _clip(1.0 - confidence)

    @staticmethod
    def _candidate_score(point: str, candidate: str, base_score: float) -> float:
        distance = abs(_INDEX[candidate] - _INDEX[point]) / 4.0
        # Small ordinal penalty keeps nearby severities together while allowing
        # the calibrated threshold to widen the prediction set when uncertain.
        return _clip(base_score + 0.22 * distance)

    @staticmethod
    def _finite_sample_quantile(scores: Sequence[float], alpha: float) -> float:
        ordered = sorted(float(x) for x in scores)
        n = len(ordered)
        rank = math.ceil((n + 1) * (1.0 - alpha))
        index = min(max(rank - 1, 0), n - 1)
        return _clip(ordered[index])

    def calibrate(self, findings: Sequence[Finding]) -> None:
        if len(findings) < self.min_calibration_size:
            message = (
                f"Need at least {self.min_calibration_size} calibration findings; "
                f"got {len(findings)}"
            )
            raise ValueError(message)

        scores = [self._score_for_observed(finding) for finding in findings]
        self.calibration_scores = list(scores)
        self.calibration_quantile = self._finite_sample_quantile(scores, self.alpha)
        self.is_calibrated = True

    def predict(self, finding: Finding) -> PredictionResult:
        point = _severity_value(finding)
        base_score = self._score_for_observed(finding)

        if not self.is_calibrated or self.calibration_quantile is None:
            result = PredictionResult(
                point_prediction=point,
                prediction_set=[point],
                coverage_guarantee=0.0,
                calibrated=False,
                alpha=self.alpha,
                calibration_size=self.calibration_size,
                nonconformity_score=base_score,
                lower=_INDEX[point] / 4.0,
                upper=_INDEX[point] / 4.0,
                metadata={
                    "coverage_status": "uncalibrated",
                    "empirical_guarantee_claimed": False,
                },
            )
            self.last_prediction = result
            return result

        threshold = self.calibration_quantile
        candidates = sorted(
            {
                point,
                *(
                    label
                    for label in _SEVERITIES
                    if self._candidate_score(point, label, base_score) <= threshold + 1e-12
                ),
            },
            key=lambda label: _INDEX[label],
        )

        lower = min(_INDEX[label] for label in candidates) / 4.0
        upper = max(_INDEX[label] for label in candidates) / 4.0

        result = PredictionResult(
            point_prediction=point,
            prediction_set=candidates,
            coverage_guarantee=1.0 - self.alpha,
            calibrated=True,
            alpha=self.alpha,
            calibration_size=self.calibration_size,
            nonconformity_score=base_score,
            lower=lower,
            upper=upper,
            metadata={
                "coverage_status": "calibrated",
                "confidence_level": 1.0 - self.alpha,
                "empirical_guarantee_claimed": False,
                "calibration_quantile": threshold,
            },
        )
        self.last_prediction = result
        return result

    def apply(self, findings: list[Finding]) -> list[Finding]:
        for finding in findings:
            pred = self.predict(finding)

            finding.conformal_set = list(pred.prediction_set)
            finding.conformal_lower = pred.lower
            finding.conformal_upper = pred.upper
            finding.conformal_confidence = pred.confidence

            finding.metadata["conformal"] = {
                **pred.metadata,
                "point_prediction": pred.point_prediction,
                "prediction_set": list(pred.prediction_set),
                "calibrated": pred.calibrated,
                "calibration_size": pred.calibration_size,
                "alpha": self.alpha,
                "confidence": pred.confidence,
            }

        return findings


__all__ = ["ConformalPredictionEngine", "PredictionResult"]
