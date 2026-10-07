# Propagation research baseline

Research date: 2026-10-06.

## Mechanistic foundations

1. Watts (2002), *A simple model of global cascades on random networks*: small shocks can trigger large cascades under threshold-style network conditions.
2. Crucitti, Latora & Marchiori (2004), *Model for cascading failures in complex networks*: load redistribution can make infrastructure cascades fundamentally dynamic rather than simple reachability.
3. Motter (2004), *Cascade Control and Defense in Complex Networks*: selective intervention can suppress cascade size; propagation and mitigation must therefore expose controllable edge/node attenuation.
4. Buldyrev et al. (2010), *Catastrophic cascade of failures in interdependent networks*: failures can recursively cross coupled networks; single-layer reachability is insufficient for interdependent systems.
5. Brummitt, D'Souza & Leicht (2012), *Suppressing cascades of load in interdependent networks*: interconnection can both suppress and amplify cascades, depending on regime.
6. Majdandzic et al. (2016), *Multiple tipping points and optimal repairing in interacting networks*: failure, damage spread, recovery and tipping behavior interact; propagation should preserve explicit state/lineage rather than flattening everything to one static score.
7. Valdez et al. (2020), *Cascading Failures in Complex Networks*: physics/network models are valuable mechanistic representations, but their simplified predictions should not be confused with precise engineering forecasts.

## Temporal-network foundation

Holme & Saramäki's temporal-network work establishes that timing and time-respecting paths can change reachability and spreading dynamics. SERAPH propagation therefore uses relationship validity at departure/arrival and explicit edge delay attributes rather than treating the frozen temporal graph as a static graph.

## Risk/resilience standards

ISO 31000:2018 provides the risk-management framework; IEC 31010:2019 provides risk-assessment technique guidance. NIST SP 800-30 Rev. 1 structures risk assessment, and NIST SP 800-160 Vol. 2 Rev. 1 addresses resilience against adverse conditions, stresses and attacks. These support explicit assumptions, bounded analysis, uncertainty separation, and traceable reasoning.

## Interoperability

Apache Arrow provides a language-independent in-memory columnar representation and IPC format suitable for the future Python/Rust data plane. OGC API Features / JSON-FG provide the project's geospatial service/data interoperability boundary. GraphBLAS provides a rigorous future path for sparse graph kernels and semiring-style computation, consistent with the project's future Rust/native optimization direction.

## Engineering choices derived from the baseline

- Deterministic ordering is mandatory for reproducible runs.
- Time is explicit; a path must be time-respecting.
- Multiple path contributions can be combined as MAX, capped SUM, or NOISY-OR; this is a configurable modeling assumption, not an empirical truth.
- The engine is bounded by maximum hops, signals, and paths per entity.
- Interventions act as explicit attenuation inputs; they do not mutate the underlying graph.
- Evidence preserves source shocks and relationship path provenance.
- The reference implementation avoids mandatory heavyweight network/ML dependencies. The future Rust/GraphBLAS path can optimize the same semantics.

## Limitations

This layer does not model power-flow equations, hydraulic equations, epidemic compartment dynamics, market clearing, agent behavior, or calibrated probabilities. Those require domain-specific models and/or later SERAPH layers. A graph cascade is a mechanistic scenario result, not a claim that the real world will follow that trajectory.
