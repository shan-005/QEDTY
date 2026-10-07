# Orchestration research baseline

SERAPH separates the semantic pipeline definition from execution infrastructure. The reference Python scheduler is deterministic and local; production deployments can map the same task graph to Airflow, Temporal, Dagster, or another engine while retaining run IDs, idempotency keys, provenance, and telemetry semantics.

The orchestration contract intentionally makes retries explicit. A workflow is not considered durable merely because it retries; durable execution requires persisted progress and replay/recovery semantics supplied by the production platform.
