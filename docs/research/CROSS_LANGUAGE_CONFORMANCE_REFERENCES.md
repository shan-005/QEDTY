# Cross-Language Conformance Expansion — research and standards register

**Review date:** 2026-10-11
**Scope:** engineering methods and technical standards relevant to the QEDTY Python/Rust differential and conformance work. This is a curated, traceable register—not a claim that literally every publication or web page in existence has been reviewed.

## How to use the sources

Use normative standards for serialized formats and domain semantics, the QEDTY contracts and Python implementation for product-specific meaning, and peer-reviewed research for choosing test methods. An external reference does not establish QEDTY conformance by itself. Every QEDTY claim still needs a mapped contract, an appropriate oracle, and executable tests.

## Primary software-testing research

1. **Barr, E. T.; Harman, M.; McMinn, P.; Shahbaz, M.; Yoo, S. (2015). “The Oracle Problem in Software Testing: A Survey.” IEEE Transactions on Software Engineering, 41(5), 507–525. DOI: [10.1109/TSE.2014.2372785](https://doi.org/10.1109/TSE.2014.2372785).** Open access record: https://discovery.ucl.ac.uk/id/eprint/1471263/ . Relevance: differential testing helps compare implementations, but a common-mode bug or incorrectly specified contract still requires an independent oracle or human-reviewed expected behavior.
2. **Chen, T. Y.; Kuo, F.-C.; Liu, H.; Poon, P.-L.; Towey, D.; Tse, T. H.; Zhou, Z. Q. (2018). “Metamorphic Testing: A Review of Challenges and Opportunities.” ACM Computing Surveys, 51(1), Article 4.** Author page: https://i.cs.hku.hk/~tse/Papers/2010s/hlmtCSUR.html . Relevance: test relations between multiple executions when hand-authoring every expected result is difficult. For QEDTY examples include Allen-relation inverse laws, serialization idempotence, deterministic repeated output, coordinate round trips and brute-force checks for spatial-index completeness. Relations themselves must be reviewed rather than assumed true.
3. **Allen, J. F. (1983). “Maintaining Knowledge about Temporal Intervals.” Communications of the ACM, 26(11), 832–843. DOI: [10.1145/182.358434](https://doi.org/10.1145/182.358434).** ACM record: https://dl.acm.org/doi/10.1145/182.358434 . Relevance: formal basis for the thirteen basic relations implemented by QEDTY. A test suite should cover every relation, inverses, equal endpoints and proper non-empty intervals.
4. **McKeeman, W. M. (1998). “Differential Testing for Software.” Digital Technical Journal, 10(1), 100–107.** Bibliographic record: https://dblp.org/rec/journals/dtj/McKeeman98 ; archived article scan: https://www.bitsavers.org/pdf/dec/dtj/dtj_v10-01_1998.pdf . Relevance: compares multiple implementations on mechanically generated shared inputs and recommends reducing mismatches to compact bug reports. It is a methodological reference, not a normative QEDTY contract.
5. **Claessen, K.; Hughes, J. (2000). “QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs.” ICFP 2000, 268–279. DOI: [10.1145/351240.351266](https://doi.org/10.1145/351240.351266).** Relevance: influential foundation for randomized property-based testing. QEDTY should write the property/invariant first and treat generated examples as samples rather than exhaustive proof.

## Property-based, regression and Rust/Python tooling references

6. **Hypothesis documentation.** https://hypothesis.readthedocs.io/en/latest/ ; strategies/shrinking: https://github.com/HypothesisWorks/hypothesis/blob/master/guides/strategies-that-shrink.rst ; stateful testing: https://hypothesis.readthedocs.io/en/latest/stateful.html . Relevance: generate structured edge values, shrink failures and preserve replayable regressions. Do not confuse randomized sampling with exhaustive proof.
7. **Proptest (Rust) documentation.** https://proptest-rs.github.io/proptest/intro.html ; package/repository notes: https://docs.rs/crate/proptest/latest/source/README.md . Relevance: Rust-side generated invariants and shrinking. Adopt a dependency only after checking MSRV, locked dependencies, required runtime and useful shrinking for actual QEDTY cases.
8. **The Rust Programming Language — testing and integration tests.** https://doc.rust-lang.org/book/ch11-00-testing.html and https://doc.rust-lang.org/book/ch11-03-test-organization.html . Relevance: unit tests test local behavior; integration tests exercise public APIs as a caller does. Both are needed; neither alone proves Python/Rust parity.
9. **pytest parametrization.** https://pytest.org/en/latest/how-to/parametrize.html . Relevance: compact, named fixed regressions and parameterized boundary tests.
10. **cargo-fuzz.** https://github.com/rust-fuzz/cargo-fuzz and https://rustc-dev-guide.rust-lang.org/fuzzing.html . Relevance: coverage-guided fuzzing for parsers and complex untrusted input handling. cargo-fuzz relies on libFuzzer/LLVM sanitizer support and a nightly toolchain; keep it separate from stable required checks unless that environment is deliberately standardized.
11. **Criterion.rs.** https://github.com/criterion-rs/criterion.rs . Relevance: statistical Rust benchmarking after semantics are correct. Performance is a separate acceptance axis from cross-language correctness.
12. **GitHub Actions security.** https://docs.github.com/en/actions/reference/security/secure-use . Relevance: least-privilege workflow permissions, pinned actions, and no unnecessary credentials. The current differential workflow is read-only and should remain so unless reviewed requirements change.

## Serialization, identity and numerical behavior standards

13. **JSON Schema Draft 2020-12.** https://json-schema.org/draft/2020-12/ and https://json-schema.org/specification . Relevance: the existing differential case format uses Draft 2020-12. Keep one machine-readable schema and validate fixture files before executing the native adapter.
14. **RFC 8785 — JSON Canonicalization Scheme (JCS), June 2020.** https://www.rfc-editor.org/rfc/rfc8785.html . Relevance: cryptographic canonicalization requires invariant serialized bytes, compatible number handling and key ordering. QEDTY's established `qedty-canonical-json@1` profile must not be silently relabeled RFC 8785/JCS; they are separate named profiles in the Python source.
15. **RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format.** https://www.rfc-editor.org/rfc/rfc8259.html . Relevance: base JSON syntax/interoperability. Non-finite NaN/Infinity are not standard JSON values and should fail closed at the differential protocol boundary.
16. **IEEE 754-2019 — IEEE Standard for Floating-Point Arithmetic.** https://standards.ieee.org/ieee/754/6210/ . Relevance: floating-point results depend on representations, operation sequence and rounding. Python `Decimal` and Rust `f64` are not interchangeable arbitrary-precision models; define per-operation profiles and tolerances.
17. **Python `decimal` documentation.** https://docs.python.org/3/library/decimal.html . Relevance: decimal arithmetic can represent decimal inputs exactly within context limits, unlike binary floating-point for many common fractions. QEDTY comparisons that convert `Decimal` to `float` need an explicit bounded output contract; passing a tolerance does not imply full precision equivalence.

## Time and temporal semantics

18. **RFC 3339 — Date and Time on the Internet: Timestamps.** https://www.rfc-editor.org/rfc/rfc3339.html . Relevance: baseline timestamp syntax and numeric offsets. QEDTY's current cross-language profile normalizes supported inputs to UTC at microsecond precision and rejects leap-second values (`:60`); that boundary is implementation-specific and should change only with an explicit versioned contract.
19. **RFC 9557 — Date and Time on the Internet: Timestamps with Additional Information, April 2024.** https://www.rfc-editor.org/rfc/rfc9557.html . It updates RFC 3339 for extended additional information/time-zone annotation. QEDTY's current differential operation should be understood as its explicitly implemented RFC 3339 subset unless IXDTF extensions are separately designed and tested; do not infer support from RFC publication alone.
20. **W3C/OGC OWL-Time.** https://www.w3.org/TR/owl-time/ . Relevance: temporal entities, instants, intervals and Allen-derived relations. QEDTY's own canonical finite intervals use `[start,end)`; standard interval reasoning should be mapped explicitly to this convention, especially at adjacency boundaries and for proper intervals.

## Geospatial and geodesy references

21. **RFC 7946 — The GeoJSON Format.** https://www.rfc-editor.org/rfc/rfc7946.html . Relevance: GeoJSON coordinate order is longitude/latitude in WGS 84; axis order should be covered with explicit tests and not guessed from variable names.
22. **OGC API — Features.** https://www.ogc.org/standards/ogcapi-features/ . Relevance: core geospatial API semantics and CRS84 longitude/latitude boundary; separate parts add other CRS behaviors.
23. **OGC Features and Geometries JSON (JSON-FG).** https://www.ogc.org/standards/json-fg/ . Relevance: JSON-FG expands GeoJSON for feature typing and richer spatial/temporal requirements while remaining GeoJSON-compatible under the standard's constraints. Profile mappings must stay explicit.
24. **Karney, C. F. F. (2013). “Algorithms for geodesics.” Journal of Geodesy, 87, 43–55. DOI: [10.1007/s00190-012-0578-z](https://doi.org/10.1007/s00190-012-0578-z).** Open-access metadata and paper entry: https://link.springer.com/article/10.1007/s00190-012-0578-z ; https://geographiclib.sourceforge.io/geod.html . Relevance: robust direct/inverse ellipsoidal geodesic algorithms and test data. A spherical mean-Earth-radius point-index metric is not the same as an ellipsoidal inverse-geodesic solution.
25. **EPSG/IOGP Geodetic Parameter Dataset and Guidance Note 7-2.** Registry: https://epsg.org/ ; user manual explains that Guidance Note 7-2 documents conversion and transformation formulas: https://epsg.org/template/IOGP/downloads/user_manual.pdf . Relevance: use authoritative ellipsoid/CRS definitions and independently sourced expected coordinates, including stated axes/units and coordinate order. Registry versions can change; record the specific dataset/version when fixtures depend on it.

## Selected theses and dissertation research

These are targeted academic works discovered during the research pass. They extend the literature beyond journal papers; they are examples, not an exhaustive dissertation census.

27. **Xu, Congying. “Automated and Effective Metamorphic Testing: Relation Discovery, Deduction, and Generation.” Doctoral thesis, Hong Kong University of Science and Technology.** Official research-portal record: https://researchportal.hkust.edu.hk/en/studentTheses/automated-and-effective-metamorphic-testing-relation-discovery-de/ . Relevance: methods to discover and synthesize metamorphic relations from tests; potentially useful later for identifying candidate invariants, but any relation QEDTY adopts still requires domain review.
28. **Hansen, Thomas Ekström. “Increasing confidence in dependently typed programs.” PhD thesis, University of St Andrews, awarded 3 July 2026. DOI: [10.17630/sta/1560](https://doi.org/10.17630/sta/1560).** Official repository: https://research-repository.st-andrews.ac.uk/handle/10023/33592 . Relevance: combines property-based testing, generated code and stronger verification ideas; useful background for keeping implementation and verified model aligned.
29. **Martin, Joel David. “Using Property-Based Testing, Weighted Grammar-Based Generators, and a Consensus Oracle to Test Browser Rendering Engines and to Reproduce Minimized Versions of Existing Test Cases.” PhD dissertation, University of Texas at Arlington, 2019.** Institutional repository: https://mavmatrix.uta.edu/cse_dissertations/352/ . Relevance: input generation, multiple-oracle testing and reduction of failing examples.
30. **Lamela Seijas, Pablo. “Model construction, evolution, and use in testing of software systems.” PhD thesis, University of Kent, 2017.** Institutional repository: https://kar.kent.ac.uk/69474/ . Relevance: reusable models, state-machine testing and model inference from code/traces—relevant to future stateful graph/index tests.
31. **Keles, Alperen. “Designing Effective Property-Based Testing Frameworks.” University of Maryland doctoral research/defense listing.** Official department page: https://www.cs.umd.edu/node/28203 ; talk record: https://talks.cs.umd.edu/talks/4646 . The department listing gave a defense date of 29 June 2026; this research pass did not establish whether a final dissertation has been deposited. Relevance: fragmentation and evaluation of property-testing frameworks, generation and reusable property-runner concepts.

## Recent empirical work

32. **de Oliveira, Isadora; Corgozinho, Arthur Lisboa; et al. “Property-based testing in Python: empirical insights.” Empirical Software Engineering, online publication 24 August 2026. DOI: [10.1007/s10664-026-10953-w](https://doi.org/10.1007/s10664-026-10953-w).** Publisher record: https://link.springer.com/article/10.1007/s10664-026-10953-w . Relevance: recent empirical evidence on how property-based testing is applied in Python; consult the full article when making specific claims about adoption or effectiveness.

## Bounded spatial, uncertainty, and integer optimization contracts

33. **OGC API – Features, Part 1: Core.** https://www.ogc.org/standards/ogcapi-features/ . Relevance: the core geographic API profile uses WGS 84 coordinates with longitude/latitude axis order; QEDTY bbox contracts must state the coordinate order, extent boundaries, and antimeridian behavior rather than infer them from tuple position. The bounded bbox query in this batch is a local result contract, not an implementation of the full OGC API.
34. **Joint Committee for Guides in Metrology (JCGM). JCGM 100:2008, Evaluation of measurement data — Guide to the expression of uncertainty in measurement; JCGM 101:2008, propagation of distributions using a Monte Carlo method.** Official publications: https://www.bipm.org/en/committees/jc/jcgm/publications . Relevance: a scalar weighted mean is only one numerical aggregation; agreement on that kernel does not demonstrate probability-distribution propagation, sampling, calibration, or uncertainty-reporting equivalence.
35. **Martello, S.; Pisinger, D.; Toth, P. (2000). “New trends in exact algorithms for the 0–1 knapsack problem.” European Journal of Operational Research, 123(2), 325–332. DOI: [10.1016/S0377-2217(99)00260-X](https://doi.org/10.1016/S0377-2217(99)00260-X).** Publisher record: https://www.sciencedirect.com/science/article/pii/S037722179900260X . Relevance: background on exact 0–1 knapsack algorithms and dynamic programming; QEDTY additionally defines an implementation-specific state budget and deterministic selected-ID tie rule.
36. **Google OR-Tools — Knapsack Solver.** https://developers.google.com/optimization/pack/knapsack . Relevance: documents the integer-weight/capacity modeling boundary and the need to scale values when the original problem has continuous quantities. The QEDTY integer kernel is deliberately not treated as equivalent to its USD portfolio objective.

## Unit codes and quantities

**UCUM 2.2 — Unified Code for Units of Measure, revised 2024-06-17.** https://ucum.org/ucum . Relevance: standardized machine-oriented unit codes and unambiguous quantity interchange. QEDTY's current unit registry is a deliberately restricted implementation with aliases, not a claim to support every UCUM expression or currency/FX semantics.

## Engineering consequences for QEDTY

- Keep Python as the semantic reference. A test runner is not a second implementation of graph, temporal or propagation business logic.
- Use independent golden vectors for critical numeric/serialization values. Same-input differential agreement alone cannot rule out a common-mode bug.
- Validate both successful results and failures: rejected malformed inputs, shared stable error categories, deterministic ordering, duplicate identities, bounds and protocol behavior.
- State coordinate CRS/axis order and metric/tolerance in every geospatial vector.
- Treat `Decimal`/`f64`, timestamp precision and canonical-JSON profile as contract decisions, not details hidden in the adapter.
- Report generated test counts as the number of executions performed, never as proof of exhaustive coverage.
- Keep performance, fuzzing, property testing, and semantic conformance as different, clearly reported pieces of evidence.
