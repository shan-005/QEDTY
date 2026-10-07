# Algorithm contract

1. Baseline and intervention worlds share the same shock and graph unless the caller explicitly supplies a different model.
2. An intervention acts through explicit protected entities and configured transmission/capacity effects.
3. The counterfactual is a model comparison, not an empirical causal estimate by default.
4. Result digests cover the reported result and its provenance fields.
5. Economic deltas are caller-bound unless an explicit loss function is supplied.
