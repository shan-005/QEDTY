"""Compatibility facade for the canonical source registry.

SERAPH-PCI-X keeps the registry implementation in seraph.sources.registry.
This module exists only for stable import compatibility.
"""

from seraph.sources.registry import SourceDefinition, SourceDomain, SourceRegistry

__all__ = ["SourceDefinition", "SourceDomain", "SourceRegistry"]
