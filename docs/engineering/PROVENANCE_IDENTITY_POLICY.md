# Provenance ID identity policy

**Status:** compatibility baseline, behavior-preserving  
**Scope:** current Python `ProvenanceActivity` IDs  
**Implementation:** `src/qedty/evidence/provenance.py` and `src/qedty/core/hash.py`  
**Regression vector:** `data/contracts/golden-vectors/evidence/provenance.json`

## Purpose and decision boundary

This document freezes and explains the ID behavior that QEDTY already emits. It does not change the implementation, add a field to the hash preimage, or claim that this is the final desired identity semantics for every PROV activity.

For discussion, this document calls the existing preimage behavior **provenance-ID v1**. That is a documentation label only: no new runtime profile field or version token is added to the ID. The current serializer is still `qedty-canonical-json@1`; the optional RFC 8785/JCS path is separate and is not used here.

## Exact current preimage

`ProvenanceActivity.create` first normalizes its timestamps to UTC with `ensure_utc` and computes:

```python
parameters_digest = sha256_hex(parameters)

provenance_id = deterministic_id(
    "prov",
    activity,
    agent,
    ensure_utc(started_at).isoformat(),
    ensure_utc(ended_at).isoformat() if ended_at else None,
    parameters_digest,
)
```

The resulting identity preimage is the structured object:

```json
{
  "kind": "prov",
  "parts": [
    "<activity>",
    "<agent>",
    "<UTC started_at using datetime.isoformat()>",
    "<UTC ended_at using datetime.isoformat()> or null",
    "<64-character lowercase parameters_digest>"
  ]
}
```

The exact process is:

1. Hash the parameters object with `sha256_hex`, which hashes the UTF-8 bytes of QEDTY canonical JSON under `qedty-canonical-json@1`. This is a digest of the parameter value, not a digest of raw evidence bytes.
2. Normalize non-null timestamps to UTC. The ID preimage uses Python `datetime.isoformat()` after normalization; a UTC timestamp in that preimage therefore uses `+00:00`, even though the golden-vector JSON representation may display the same instant with `Z`.
3. Build the `kind = "prov"` identity preimage with the five ordered parts above and hash its canonical JSON with SHA-256.
4. Retain the first 32 lowercase hexadecimal digest characters and add the `prov:` prefix.

The end time is represented by JSON `null` when absent. This preimage order, timestamp spelling, canonicalization profile, hash algorithm, truncation length, and prefix are compatibility-sensitive.

## Fields that do and do not define the ID

| Field | Included in current ID? | Current behavior |
|---|---:|---|
| `activity` | Yes | Exact field value is part 1; no additional case or whitespace normalization |
| `agent` | Yes | Exact field value is part 2 |
| `started_at` | Yes | UTC-normalized ISO string is part 3 |
| `ended_at` | Yes | UTC-normalized ISO string or `null` is part 4 |
| `parameters` | Yes, by digest | QEDTY-canonical-JSON SHA-256 digest is part 5 |
| `used_evidence_ids` | No | Serialized on the model but omitted from the identity preimage |
| `generated_evidence_ids` | No | Serialized on the model but omitted from the identity preimage |
| `parent_ids` | No | Serialized on the model but omitted from the identity preimage |
| `software_name` | No | Serialized on the model but omitted from the identity preimage |
| `software_version` | No | Serialized on the model but omitted from the identity preimage |
| `metadata` | No | Serialized on the model but omitted from the identity preimage |
| `parameters_digest` | Yes | The digest itself is included; the original parameters object is not a model field |

The `.create()` method currently sorts and de-duplicates the three evidence/parent ID collections, but that normalization does not make them part of the ID. Metadata, software identity and lineage can differ while the computed ID remains the same.

## Consequences and collision semantics

The current ID identifies an activity signature made from activity name, agent, time interval and parameter digest. It is **not** a content address of the entire serialized `ProvenanceActivity`, nor does it uniquely identify every possible lineage/software annotation of that activity.

Two objects with the same five included inputs can therefore have equal `provenance_id` values but different excluded fields. `ProvenanceChain.add` detects this as a provenance collision when those unequal objects are inserted under the same ID; it must not be assumed that the ID alone makes all model fields identical.

Whether a provenance ID ought instead to identify each execution instance—including lineage and software build—is an open domain-policy decision. This baseline deliberately records the existing signature semantics rather than silently choosing a different one.

## Compatibility requirements

- Keep `prov:42ae4810d2217dec5892239a309d0228` and the current provenance golden vector unchanged.
- Do not add lineage, software, metadata, a new version token, or a different timestamp representation to this preimage as an incidental refactor.
- Do not silently replace `qedty-canonical-json@1` with RFC 8785/JCS.
- Any approved change to which fields define provenance identity must use a separately specified identity profile and explicit migration plan. It must ship old/new regression vectors, state whether historical IDs remain resolvable, define collision and dual-read behavior, and prove existing vectors remain reproducible.
- Keep parameter-object canonicalization, raw evidence-byte integrity digests, and provenance identity as distinct concepts.

## Executable regression coverage

`tests/test_provenance.py` pins the historical vector and tests both halves of the preimage contract:

- changing any current identity input changes the ID;
- changing only evidence links, parent IDs, software name/version, or metadata does not change the ID (although the model objects differ);
- equivalent instants with different timezone offsets normalize to the same ID.

These tests intentionally preserve today's behavior. They are not a decision that excluding lineage or software is the only correct future semantics.
