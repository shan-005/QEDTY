"""Performance benchmarks for deterministic Seraph Guard core operations."""

from __future__ import annotations

import importlib.util

import pytest

from seraph.guard.intelligence.causal import CausalRanker
from seraph.guard.scanners.base import BlastRadius, Category, Finding, Severity


try:
    _HAS_PYTEST_BENCHMARK = importlib.util.find_spec("pytest_benchmark") is not None
except (ImportError, ValueError):
    _HAS_PYTEST_BENCHMARK = False


@pytest.mark.benchmark
def test_benchmark_causal_ranker(request) -> None:
    """Benchmark ranking of a representative finding set.

    This test requires the optional ``pytest-benchmark`` plugin. If the plugin
    is not installed, the test skips cleanly instead of failing with a missing
    fixture error.
    """
    if not _HAS_PYTEST_BENCHMARK:
        pytest.skip(
            "pytest-benchmark is not installed. "
            "Install it with 'uv add --dev pytest-benchmark' "
            "or 'python -m pip install pytest-benchmark'."
        )

    benchmark = request.getfixturevalue("benchmark")

    ranker = CausalRanker()

    findings = []
    for i in range(50):
        findings.append(
            Finding(
                scanner="BenchmarkScanner",
                category=Category.SECRET if i % 2 == 0 else Category.PATTERN,
                severity=Severity.HIGH if i % 3 == 0 else Severity.MEDIUM,
                confidence=0.90,
                file=f"src/module_{i}.py",
                line=i + 1,
                title=f"Finding {i}",
                description="Benchmark finding",
                blast_radius=BlastRadius(
                    reduction_if_fixed=float(10 + i),
                    is_assessed=True,
                ),
            )
        )

    ranked = benchmark(ranker.rank, findings)

    assert len(ranked) == 50
    assert all(f.causal_rank is not None for f in ranked)
