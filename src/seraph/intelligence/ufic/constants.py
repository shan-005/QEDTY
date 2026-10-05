import re

from typing import Any


# =============================================================================
# 1. FILE PATH PATTERNS → auto-classified as non-production
# =============================================================================
SKIP_PATTERNS: list[str] = [
    # --- Test files (all languages) ---
    r".*_test\.go$",
    r".*testing\.go$",
    r".*/testhelpers?/.*",
    r".*/tests?/.*",
    r".*/__tests__/.*",
    r".*/test_.*\.py$",
    r".*/.*_test\.py$",
    r".*/mock.*\.",
    r".*/fixtures/.*",
    r".*/spec/.*",
    # --- Dev tooling / CI ---
    r".*/dev/breeze/.*",
    r".*/scripts/ci/.*",
    r".*/scripts/in_container/.*",
    r".*/scripts/prek/.*",
    r".*/devel-common/.*",
    r".*/airflow_mypy/.*",
    r".*/airflow_breeze/.*",
    r".*/enos/.*",
    r".*/\.release/.*",
    # --- Documentation ---
    r".*/docs?/.*",
    r".*/.*\.rst$",
    r".*/.*\.md$",
    r".*/README.*",
    r".*/CHANGELOG.*",
    r".*/CONTRIBUTING.*",
    # --- Examples ---
    r".*/example_dags?/.*",
    r".*/examples?/.*",
    r".*/sample.*",
    r".*/tutorial.*",
    # --- Docker / config noise ---
    r".*/docker-stack-docs/.*",
    r".*/docker-examples/.*",
    r".*/chart/docs/.*",
    r".*/registry/src/js/.*",
    r".*/.*\.env$",
    r".*/.*\.env\..*",
    # --- Generated / mock code / build artifacts ---
    r".*/mirage/.*",
    r".*\.gen\.go$",
    r".*\.generated\.",
    r".*/dist/.*",
    r".*/build/.*",
    r".*/\.next/.*",
    r".*/node_modules/.*",
    r".*/\.git/.*",
    r".*/__pycache__/.*",
    r".*/\.seraph-cache/.*",
    r".*/ui/scripts/.*",
    # --- Framework-specific build/internals (Root-agnostic) ---
    r"packages/next/src/build/.*",
    r"packages/next/src/bundles/.*",
    r"packages/next/src/compiled/.*",
    r"packages/react/packages/react/.*",
    r"packages/react/packages/react-dom/.*",
    r"lib/ansible/executor/.*",
    r"lib/ansible/plugins/.*",
    r"lib/ansible/module_utils/.*",
]

COMPILED_SKIP_PATTERNS = [re.compile(p) for p in SKIP_PATTERNS]

# =============================================================================
# 3. TEST-ONLY PATTERNS → strictly for is_test_file() context detection
# =============================================================================
TEST_ONLY_PATTERNS = [
    re.compile(
        r"(?:^|/)(tests?|__tests__|spec|specs|fixtures?|testdata|test_data|mocks?|__mocks__)(?:/|$)"
    ),
    re.compile(r"[_.-](test|spec)\.[a-z]+$"),
    re.compile(r"(?:^|/)test_[^/]+\.py$"),
]

# =============================================================================
# 2. FRAMEWORK CONTEXT RULES
# =============================================================================
FRAMEWORK_CONTEXT_RULES: dict[str, dict[str, Any]] = {
    "python": {
        "framework_exceptions": ["airflow"],
        "intent_exceptions": ["framework_internal"],
        "rule_suppressions": {
            "dangerous_eval": {
                "frameworks": ["airflow", "*"],
                "paths": [
                    "airflow-core/src/airflow/cli/",
                    "airflow-core/src/airflow/policies.py",
                    "airflow-core/src/airflow/utils/process_utils.py",
                    "airflow-core/src/airflow/jobs/triggerer_job_runner.py",
                    "airflow-core/src/airflow/dag_processing/",
                    "airflow-core/src/airflow/utils/db.py",
                    "providers/amazon/aws/operators/",
                    "providers/amazon/aws/hooks/",
                    "providers/amazon/aws/sensors/",
                    "providers/common/sql/",
                    "providers/databricks/",
                    "providers/docker/",
                    "providers/edge3/",
                    "providers/jenkins/",
                    "providers/microsoft/azure/",
                    "providers/singularity/",
                    "task-sdk/src/airflow/sdk/execution_time/",
                    "scripts/ci/prek/",
                    "scripts/in_container/",
                    "dev/breeze/",
                    "devel-common/",
                ],
            },
            "dangerous_exec": {
                "frameworks": ["airflow", "*"],
                "paths": [
                    "airflow-core/src/airflow/cli/",
                    "airflow-core/src/airflow/policies.py",
                    "airflow-core/src/airflow/utils/process_utils.py",
                    "airflow-core/src/airflow/jobs/triggerer_job_runner.py",
                    "airflow-core/src/airflow/dag_processing/",
                    "providers/amazon/aws/operators/",
                    "providers/amazon/aws/hooks/",
                    "providers/amazon/aws/sensors/",
                    "providers/common/sql/",
                    "providers/databricks/",
                    "providers/docker/",
                    "providers/edge3/",
                    "providers/jenkins/",
                    "providers/microsoft/azure/",
                    "providers/singularity/",
                    "task-sdk/src/airflow/sdk/execution_time/",
                    "scripts/ci/prek/",
                    "scripts/in_container/",
                    "dev/breeze/",
                    "devel-common/",
                ],
            },
        },
    },
    "go": {
        "framework_exceptions": [],
        "intent_exceptions": [],
        "rule_suppressions": {
            "hardcoded_password": {
                "frameworks": ["*"],
                "paths": [
                    "vault/testing.go",
                    "command/agent/testing.go",
                    "helper/testhelpers/",
                    "sdk/helper/testcluster/",
                    "builtin/credential/userpass/",
                    "builtin/logical/database/",
                    "plugins/database/",
                    "sdk/database/helper/connutil/",
                    "sdk/database/helper/dbutil/",
                    "ui/mirage/",
                ],
            },
            "private_key": {
                "frameworks": ["*"],
                "paths": [
                    "vault/testing.go",
                    "command/agent/testing.go",
                    "helper/testhelpers/",
                    "sdk/helper/testcluster/",
                ],
            },
        },
    },
    "javascript": {
        "framework_exceptions": [],
        "intent_exceptions": ["mock_frontend"],
    },
    "typescript": {
        "framework_exceptions": [],
        "intent_exceptions": ["mock_frontend"],
    },
}
