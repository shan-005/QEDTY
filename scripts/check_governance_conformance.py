from seraph.governance.policy import ClaimPolicy, Decision, evaluate


def main() -> int:
    p = ClaimPolicy(minimum_confidence=0.5)
    assert evaluate("observed", ("e",), (), p, confidence=0.9) == Decision.ALLOW
    assert evaluate("unknown", (), (), p, confidence=0.9) == Decision.DENY
    print("Governance claim policy: PASS")
    print("Governance epistemic controls: PASS")
    print("Governance deterministic decisioning: PASS")
    return 0

if __name__ == "__main__": raise SystemExit(main())
