# QEDTY Ontology Competency Questions

The ontology is scoped by questions the world model must answer without requiring a downstream graph/propagation algorithm to reinterpret the base semantics.

## Identity and resolution

1. What canonical entity does an external identifier resolve to?
2. Is an external identifier ambiguous, rejected, under review, or accepted?
3. Which evidence and resolver produced the mapping?
4. Can two accepted mappings assign the same external identifier to different entities?

## World structure

5. What entities exist, what type are they, and what is their lifecycle state?
6. Which directed relationships connect two entities?
7. Which relationships are valid during a requested time window?
8. Which events are associated with or affect an entity?

## Capability and service semantics

9. What quantified capability is owned by an entity?
10. What is its nominal, minimum and maximum capacity?
11. What effective capacity remains after availability is applied?
12. Which services are delivered by an entity or its capabilities?
13. What capabilities or relationships does a service depend upon?

## Flows and assertions

14. What quantity flows between two entities during a defined validity interval?
15. Is a statement about an entity a relationship, observation, measurement, derivation or hypothesis?
16. What is the epistemic status and assessment confidence of that statement?
17. Which evidence and provenance support the statement?

## Temporal and spatial semantics

18. What was true during a specific validity interval?
19. When was the corresponding record observed or asserted?
20. Where is the entity located in the Core geodetic reference model?

## Governance boundary

21. Can a model distinguish semantic truth from an assessment score?
22. Can every derived/canonical record retain enough evidence/provenance references for later audit?
23. Can a downstream Rust/Arrow/Protobuf/SQL implementation represent the same identifiers, types, time windows and quantities without changing their meaning?

These questions are implementation tests, not claims that the ontology alone answers causality, propagation, economic impact or resilience. Those belong to later layers.
