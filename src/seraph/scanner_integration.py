from dataclasses import dataclass
from pathlib import Path

from seraph.ufic.classifier import UFICClassifier


@dataclass
class MockFinding:
    scanner_type: str  # 'secret', 'pattern', 'sbom', 'policy'
    rule_id: str  # 'exec', 'eval', 'hardcoded_password', 'aws_access_key'
    language: str  # 'python', 'javascript', 'java', 'go'
    file_path: str
    line_number: int
    title: str = ""  # Added for UFIC evaluate_finding compatibility
    intent: str = "production"  # Populated by UFIC


def run_seraph_scan(repo_path: str) -> list[MockFinding]:
    # 1. Initialize UFIC (No repo_path needed, it uses topology dict)
    ufic = UFICClassifier()

    # Mocking your file discovery phase
    discovered_files = [
        Path(repo_path) / "vault/testing.go",
        Path(repo_path) / "lib/ansible/executor/task_queue.py",
        Path(repo_path) / "src/main.py",
        Path(repo_path) / "tests/test_auth.py",
        Path(repo_path) / "node_modules/react/index.js",
    ]

    files_to_scan = []

    # PHASE 1: PRE-SCAN FILTERING
    print("--- Phase 1: File Discovery & Intent Classification ---")
    for f in discovered_files:
        if ufic.should_skip_file(f):
            print(f"[SKIP] {f.name} (Layer 0: Always Skip)")
            continue

        intent = ufic.get_file_intent(f)
        # Expanded intent skip list to match UFICClassifier outputs
        if intent in (
            "test",
            "documentation",
            "example",
            "generated",
            "vendored",
            "non_production",
            "ci_script",
            "dev_tooling",
            "mock_frontend",
            "config",
        ):
            print(f"[SKIP] {f.name} (Intent: {intent})")
            continue

        print(f"[SCAN] {f.name} (Intent: {intent})")
        files_to_scan.append((f, intent))

    # Mocking your scanners running (Trivy, Gitleaks, PatternScanner)
    print("\n--- Scanners Running... ---")
    raw_findings = [
        MockFinding(
            "pattern", "exec", "go", "vault/testing.go", 78, title="Dangerous pattern: exec"
        ),
        MockFinding(
            "pattern",
            "exec",
            "python",
            "lib/ansible/executor/task_queue.py",
            112,
            title="Dangerous pattern: exec",
        ),
        MockFinding(
            "pattern", "exec", "python", "src/main.py", 45, title="Dangerous pattern: exec"
        ),
        MockFinding(
            "secret",
            "hardcoded_password",
            "python",
            "tests/test_auth.py",
            12,
            title="Hardcoded password",
        ),
        MockFinding(
            "pattern",
            "eval",
            "javascript",
            "node_modules/react/index.js",
            99,
            title="Dangerous pattern: eval",
        ),
    ]

    # PHASE 2: POST-SCAN FILTERING
    print("\n--- Phase 2: Finding Evaluation (Semantic & Context) ---")
    final_report = []

    for finding in raw_findings:
        # Inject the intent calculated in Phase 1 dynamically
        finding.intent = ufic.get_file_intent(Path(finding.file_path))

        if ufic.evaluate_finding(finding):  # type: ignore[truthy-bool]
            print(
                f"[SUPPRESS] {finding.rule_id} in {Path(finding.file_path).name} (Context/Semantic Safe)"
            )
        else:
            print(f"[ALERT]    {finding.rule_id} in {Path(finding.file_path).name}")
            final_report.append(finding)

    print(f"\n--- Final Report: {len(final_report)} True Positives ---")
    return final_report


# Example Execution
if __name__ == "__main__":
    run_seraph_scan("./mock_repo")
