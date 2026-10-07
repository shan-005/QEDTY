"""Evidence/source adapters for SERAPH-PCI-X.

Adapters normalize external data into bounded source records. Network access is
explicit, host-allowlisted, hashed, and never silently promoted to observed
world state without an evidence identifier.
"""

from .base import FetchResult, SourceAdapter, SourceContext
from .registry import SourceDefinition, SourceRegistry

__all__ = ["FetchResult", "SourceAdapter", "SourceContext", "SourceDefinition", "SourceRegistry"]
