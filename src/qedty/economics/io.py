from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class IOModel:
    sectors: tuple[str, ...]
    technical_coefficients: tuple[tuple[float, ...], ...]
    value_added_coefficients: tuple[float, ...] = ()

    def validate(self) -> None:
        n = len(self.sectors)
        if n == 0:
            raise ValueError("IO model requires at least one sector")
        if len(self.technical_coefficients) != n or any(
            len(r) != n for r in self.technical_coefficients
        ):
            raise ValueError("IO matrix dimension mismatch")
        if any((x < 0 or not isfinite(x)) for r in self.technical_coefficients for x in r):
            raise ValueError("IO coefficients must be non-negative and finite")
        if self.value_added_coefficients and len(self.value_added_coefficients) != n:
            raise ValueError("value-added vector dimension mismatch")
        if any(x < 0 for x in self.value_added_coefficients):
            raise ValueError("value-added coefficients must be non-negative")
        if self.spectral_radius_estimate() >= 1.0:
            raise ValueError("IO model is unstable: spectral radius must be < 1")

    def spectral_radius_estimate(self, iterations: int = 200) -> float:
        n = len(self.sectors)
        if n == 0:
            return 0.0
        v = [1.0 for _ in range(n)]
        rho = 0.0
        for _ in range(iterations):
            w = [sum(self.technical_coefficients[i][j] * v[j] for j in range(n)) for i in range(n)]
            scale = max(w)
            if scale == 0:
                return 0.0
            v = [x / scale for x in w]
            rho = scale
        return rho

    @staticmethod
    def _solve(a: list[list[float]], b: list[float]) -> list[float]:
        n = len(b)
        m = [[*row[:], b[i]] for i, row in enumerate(a)]
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
            if abs(m[pivot][col]) < 1e-12:
                raise ValueError("singular IO system")
            m[col], m[pivot] = m[pivot], m[col]
            pv = m[col][col]
            for j in range(col, n + 1):
                m[col][j] /= pv
            for r in range(n):
                if r == col:
                    continue
                f = m[r][col]
                if f:
                    for j in range(col, n + 1):
                        m[r][j] -= f * m[col][j]
        return [m[i][n] for i in range(n)]

    def total_output(self, final_demand: tuple[float, ...]) -> tuple[float, ...]:
        self.validate()
        n = len(self.sectors)
        if len(final_demand) != n:
            raise ValueError("final demand mismatch")
        if any(x < 0 or not isfinite(x) for x in final_demand):
            raise ValueError("final demand must be non-negative and finite")
        a = [[(-self.technical_coefficients[i][j]) for j in range(n)] for i in range(n)]
        for i in range(n):
            a[i][i] += 1.0
        return tuple(self._solve(a, list(final_demand)))

    def output_from_demand_shock(
        self, baseline_demand: tuple[float, ...], loss_fraction: tuple[float, ...]
    ) -> tuple[float, ...]:
        if len(baseline_demand) != len(loss_fraction):
            raise ValueError("shock vector mismatch")
        if any(not 0 <= x <= 1 for x in loss_fraction):
            raise ValueError("loss fractions must be in [0,1]")
        # FIXED: Changed 'l' to 'loss' to avoid E741 ambiguous variable name
        stressed = tuple(
            d * (1 - loss) for d, loss in zip(baseline_demand, loss_fraction, strict=True)
        )
        return self.total_output(stressed)
