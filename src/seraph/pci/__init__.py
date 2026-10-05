"""SERAPH-PCI-X application boundary.

The domain implementation lives in the promoted top-level seraph packages.
This package intentionally contains only the PCI-X application entry point so
there is one canonical implementation of every domain primitive.
"""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PCI-X command line application."""
    from seraph.pci.__main__ import run
    return run(argv)


__all__ = ["main"]
