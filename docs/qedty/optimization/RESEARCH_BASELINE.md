# Optimization research baseline

QEDTY separates semantic objective construction from the solver. The Python reference implementation is dependency-light so that a result can be regenerated without a specific external solver installation.

For production-scale optimization, the contract can be mapped to HiGHS or OR-Tools. Robust optimization and distributionally robust optimization motivate using scenario envelopes and lower-tail risk measures rather than optimizing only an expected gain.

The package deliberately does not claim global optimality when it uses its large-portfolio greedy fallback; the result status communicates this boundary.
