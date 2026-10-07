# SERAPH-PCI-X Evidence Contract

Version: 2.0.0

The Evidence layer records **what was observed/acquired, where it came from, which immutable representation was captured, when it was retrieved/observed, how it was selected, transformed, assessed for quality, and what rights apply**. It does not turn evidence into truth: interpretation belongs to the ontology/assertion and intelligence layers.

## Standards boundaries

- W3C PROV-DM / PROV-O: derivation, activities, agents, generation and usage.
- W3C DCAT 3: dataset/distribution catalog semantics where evidence is distributed data.
- W3C DQV: explicit, metric-based quality measurements; no mandatory universal quality score.
- W3C Web Annotation: stable selectors for fragments of documents/media/data.
- SPDX expressions: license identification; unknown permissions remain unknown.
- RFC 9530: HTTP `Content-Digest` compatibility at acquisition boundaries.
- JSON Schema 2020-12: machine validation contract.
- Protobuf: typed service/control representation.
- Arrow: bulk metadata interchange; evidence bytes remain content-addressed.
- FAIR: findability, accessibility, interoperability and reusability metadata principles.

The implementation deliberately distinguishes **integrity** (the captured bytes match their digest) from **provenance** (how/why the bytes entered the pipeline) and **quality** (fitness information measured under an explicit metric). A digest does not establish truthfulness.
