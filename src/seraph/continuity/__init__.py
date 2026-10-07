"""SERAPH-PCI-X continuity and resilience semantics.

Continuity converts propagated impairment into explicit service-performance
trajectories and auditable recovery metrics. It does not assign probabilities.
"""

from .engine import ContinuityEngine
from .models import ContinuityPoint, ContinuityResult

__all__ = ["ContinuityEngine", "ContinuityPoint", "ContinuityResult"]
