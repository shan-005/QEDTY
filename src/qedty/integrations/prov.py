from typing import Any

from qedty.evidence.provenance import ProvenanceActivity


def prov_dict(record: ProvenanceActivity) -> dict[str, Any]:
    return record.model_dump(mode="json")
