"""SERAPH-PCI-X intelligence layer.

The layer converts evidence-backed world state into ranked signals, forecasts,
patterns, explanations, and uncertainty-aware impact assessments.  It does not
silently promote modeled or inferred statements to observed facts.
"""

from .anomaly import AnomalyScore, cusum, robust_zscore, zscore
from .claims import IntelligenceClaim
from .explanation import Explanation, ExplanationFactor
from .forecast import Forecast, holt_linear, persistence
from .fusion import FusionRecord, fuse
from .impact import ImpactScore, combine

__all__ = [
    "AnomalyScore",
    "Explanation",
    "ExplanationFactor",
    "Forecast",
    "FusionRecord",
    "ImpactScore",
    "IntelligenceClaim",
    "combine",
    "cusum",
    "fuse",
    "holt_linear",
    "persistence",
    "robust_zscore",
    "zscore",
]
