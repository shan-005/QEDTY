# QEDTY Scenarios — research baseline (2026-10-06)

## Scope

Scenarios describe conditional alternative developments of the QEDTY world model. They are not forecasts, observations, or probability models. The implementation keeps likelihood/probability out of this layer so that uncertainty semantics remain owned by the later `uncertainty/` layer.

## Research synthesis

### IPCC scenario methodology

IPCC AR6 WGIII Annex III defines scenarios as descriptions of alternative future developments used to explore implications of possible futures and alternative courses of action, with particular value under deep uncertainty. QEDTY adopts the conditional/assumption-explicit framing and rejects relabeling a scenario as a forecast.

Reference: https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_Annex-III.pdf

### NASA operational scenarios and risk-informed modeling

NASA systems engineering guidance treats scenarios as timelines covering nominal and off-nominal conditions. NASA technical risk-management material characterizes risk using scenarios, likelihood, and consequences, and identifies initiating events and subsequent event progression. NASA PRA guidance also uses event trees and explicit scenario modeling.

References:
- https://www.nasa.gov/reference/system-engineering-handbook-appendix/
- https://www.nasa.gov/reference/6-4-technical-risk-management/
- https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_8705_0005_&page_name=ALL

QEDTY implication: initiating events, scenario progression, and consequences must remain explicit rather than embedding an unexplained severity-to-outcome shortcut.

### OECD strategic foresight and resilience

OECD Global Scenarios 2035 uses multiple internally coherent scenarios as a foresight device for preparing for unexpected futures. OECD resilience guidance emphasizes understanding evolving, interconnected risks and using analysis to construct a roadmap toward resilience.

References:
- https://www.oecd.org/en/publications/2021/05/global-scenarios-2035_72de6a64.html
- https://www.oecd.org/en/publications/guidelines-for-resilience-systems-analysis_b0017c2c-en.html

QEDTY implication: scenario sets should be comparable, explicit about assumptions, and useful for downstream resilience/continuity analysis.

### Dynamic Adaptive Policy Pathways

Haasnoot, Kwakkel, Walker and ter Maat's Dynamic Adaptive Policy Pathways (2013) formalizes planning under deep uncertainty as alternative sequences of decisions over time, including triggers/signposts and path dependency. The later computer-assisted work shows how pathway generation can be treated as an explicit computational problem.

References:
- https://doi.org/10.1016/j.gloenvcha.2012.12.006
- https://doi.org/10.1007/s10584-014-1210-4

QEDTY implication: scenario trees and guards belong in the scenario layer; probability distributions and calibration belong later in uncertainty.

### General Morphological Analysis

Johansen (2018) describes morphological analysis as a structured approach to scenario construction using explicit factors and internally/external consistency assessment, with a clear audit trail. This supports QEDTY's emphasis on explicit patches, assumptions, deterministic composition, and auditable scenario lineage.

Reference: https://doi.org/10.1016/j.techfore.2017.05.016

### ASAM OpenSCENARIO

ASAM OpenSCENARIO 2.0 defines a domain-specific language and domain model for dynamic scenario description, including parameterization, composition, event-based execution, and varying levels of abstraction. QEDTY does not adopt the automotive domain model, but the structural lessons are relevant: explicit scenario composition, parameters, dynamic events, and exchangeable representations.

References:
- https://www.asam.net/standards/detail/openscenario/v200/
- https://www.asam.net/fileadmin/Standards/OpenSCENARIO/ASAM_OpenSCENARIO_2-0_Concept_Paper.html

### Risk governance

ISO 31000:2018 remains the current confirmed edition as of the research date. It frames risk management around identifying, analyzing, evaluating, treating, monitoring, and communicating risk. QEDTY uses related concepts but does not claim ISO 31000 conformity.

Reference: https://www.iso.org/standard/65694.html

## Contract/interoperability baseline

- JSON Schema Draft 2020-12: https://json-schema.org/draft/2020-12/
- Protocol Buffers: https://protobuf.dev/
- Apache Arrow: https://arrow.apache.org/docs/
- W3C SHACL: https://www.w3.org/TR/shacl/
- W3C PROV-O: https://www.w3.org/TR/prov-o/

## Architectural decisions

1. A scenario is conditional and assumption-bearing, not a forecast.
2. Shock severity is descriptive; causal state consequences require explicit capacity multipliers or patches.
3. Intervention effects are explicit and deterministic.
4. Scenario parameters remain backward-compatible capacity multipliers.
5. Scenario capacities remain backward-compatible absolute capacity overrides.
6. State mutation is copy-based; the input state is never modified by `apply_scenario`.
7. Scenario state has a deterministic canonical digest for provenance and cross-language conformance.
8. Scenario trees are acyclic, rooted, connected, and single-parent for non-root nodes.
9. Declarative guards allow adaptive branching without embedding domain-specific Python callbacks.
10. Probability distributions, calibration, Monte Carlo, and robust optimization are intentionally deferred to later layers.
11. JSON is the document boundary; Protobuf is the service boundary; Arrow is the data-plane boundary.
12. The Python implementation is the semantic reference for a later Rust implementation.

## Non-goals

This layer does not claim to be a complete scenario-planning methodology, a probabilistic risk engine, a causal identification system, an event-tree GUI, a simulator, or a replacement for domain-specific scenario languages.
