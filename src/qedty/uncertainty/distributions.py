from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, pi, sqrt


@dataclass(frozen=True, slots=True)
class Normal:
    mean: float
    std: float

    def _check(self) -> None:
        if self.std <= 0:
            raise ValueError("std must be positive")

    def pdf(self, x: float) -> float:
        self._check()
        z = (x - self.mean) / self.std
        return exp(-0.5 * z * z) / (self.std * sqrt(2 * pi))

    def cdf(self, x: float) -> float:
        self._check()
        return 0.5 * (1 + erf((x - self.mean) / (self.std * sqrt(2))))

    def ppf(self, p: float) -> float:
        self._check()
        if not 0 < p < 1:
            raise ValueError("p must be in (0,1)")
        lo = self.mean - 12 * self.std
        hi = self.mean + 12 * self.std
        for _ in range(80):
            mid = (lo + hi) / 2
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


@dataclass(frozen=True, slots=True)
class Uniform:
    low: float
    high: float

    def _check(self) -> None:
        if self.high <= self.low:
            raise ValueError("high must exceed low")

    def pdf(self, x: float) -> float:
        self._check()
        return 1 / (self.high - self.low) if self.low <= x <= self.high else 0.0

    def cdf(self, x: float) -> float:
        self._check()
        return (
            0.0
            if x < self.low
            else 1.0
            if x >= self.high
            else (x - self.low) / (self.high - self.low)
        )

    def ppf(self, p: float) -> float:
        if not 0 <= p <= 1:
            raise ValueError("p must be in [0,1]")
        self._check()
        return self.low + p * (self.high - self.low)


@dataclass(frozen=True, slots=True)
class LogNormal:
    mean_log: float
    std_log: float

    def _normal(self) -> Normal:
        return Normal(self.mean_log, self.std_log)

    def pdf(self, x: float) -> float:
        if x <= 0:
            return 0.0
        return self._normal().pdf(log(x)) / x

    def cdf(self, x: float) -> float:
        return 0.0 if x <= 0 else self._normal().cdf(log(x))

    def ppf(self, p: float) -> float:
        return exp(self._normal().ppf(p))
