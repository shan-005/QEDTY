from dataclasses import dataclass
@dataclass(frozen=True)
class ClaimPolicy:
    allow_unknown:bool=False; require_evidence_for_observed:bool=True; require_provenance_for_modeled:bool=True

def enforce(status:str,evidence_ids:tuple[str,...],provenance_ids:tuple[str,...],policy:ClaimPolicy)->None:
    if status=="observed" and policy.require_evidence_for_observed and not evidence_ids:raise ValueError("observed claim requires evidence")
    if status=="modeled" and policy.require_provenance_for_modeled and not provenance_ids:raise ValueError("modeled claim requires provenance")
