import pytest

from qedty.core.enums import EpistemicStatus
from qedty.governance.claims import Claim
from qedty.governance.policy import ClaimPolicy, Decision, enforce, evaluate


def test_observed_requires_evidence() -> None:
    with pytest.raises(ValueError):
        Claim(claim_id="c", statement="x", status=EpistemicStatus.OBSERVED)
    claim = Claim(
        claim_id="c", statement="x", status=EpistemicStatus.OBSERVED, evidence_ids=("e1",)
    )
    assert claim.claim_id == "c"


def test_policy_decisions() -> None:
    p = ClaimPolicy(minimum_confidence=0.5)
    with pytest.raises(ValueError):
        enforce("observed", (), (), p)
    assert evaluate("observed", ("e1",), (), p, confidence=0.9) == Decision.ALLOW
    assert evaluate("unknown", (), (), p, confidence=0.9) == Decision.DENY
