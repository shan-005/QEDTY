# Provenance

QEDTY stores source, retrieval, transformation, model and claim lineage explicitly. The internal representation is QEDTY-native and can be serialized toward W3C PROV-compatible concepts such as Entity, Activity and Agent.

The current Python activity-ID behavior and its compatibility limits are specified in [Provenance ID identity policy](engineering/PROVENANCE_IDENTITY_POLICY.md). In the existing behavior, the ID is based on the activity, agent, UTC start/end timestamps, and digest of canonicalized parameters; evidence links, parent links, software identity and metadata do not enter the ID preimage. This is a documented compatibility baseline, not a claim that these exclusions are the final ideal semantics for all provenance use cases.

Existing IDs and golden vectors are to remain reproducible. A future change to identity scope requires an explicit versioned policy and migration rather than a mechanical hash-preimage change.
