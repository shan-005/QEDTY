from seraph.evidence.provenance import ProvenanceActivity


def prov_dict(record: ProvenanceActivity) -> dict:
    return record.model_dump(mode="json")
