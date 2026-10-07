from __future__ import annotations

import random


def deterministic_uniform(seed: int, n: int) -> tuple[float, ...]:
    """Return deterministic U(0,1) draws."""
    if n < 0:
        raise ValueError("n must be non-negative")
    rng = random.Random(seed)
    return tuple(rng.random() for _ in range(n))


def latin_hypercube(seed: int, n: int, dimensions: int) -> tuple[tuple[float, ...], ...]:
    """Generate a deterministic Latin-hypercube sample in [0, 1)^d.

    Each dimension contains exactly one point in each of the n strata.
    """
    if n <= 0 or dimensions <= 0:
        raise ValueError("n and dimensions must be positive")
    rng = random.Random(seed)
    columns: list[list[float]] = []
    for _ in range(dimensions):
        values = [(i + rng.random()) / n for i in range(n)]
        rng.shuffle(values)
        columns.append(values)
    return tuple(
        tuple(columns[dimension][row] for dimension in range(dimensions)) for row in range(n)
    )


def sobol(seed: int, n: int, dimensions: int) -> tuple[tuple[float, ...], ...]:
    """Generate a deterministic scrambled Sobol sequence when SciPy is available.

    Falls back to Latin hypercube sampling when SciPy is unavailable. Sobol's
    ``random_base2`` mode requires a power-of-two sample size.
    """
    if n <= 0 or dimensions <= 0:
        raise ValueError("n and dimensions must be positive")
    try:
        from scipy.stats import qmc  # type: ignore[import-untyped]
    except ImportError:
        return latin_hypercube(seed, n, dimensions)
    m = n.bit_length() - 1
    if 2**m != n:
        raise ValueError("Sobol requires n to be a power of two")
    engine = qmc.Sobol(d=dimensions, scramble=True, seed=seed)
    values = engine.random_base2(m)
    return tuple(tuple(float(value) for value in row) for row in values)
