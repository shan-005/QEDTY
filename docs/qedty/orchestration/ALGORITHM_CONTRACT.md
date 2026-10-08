# Orchestration contract

The reference engine implements an acyclic task graph, deterministic topological ordering, explicit retry policy, bounded task timeout checks, idempotency metadata, and interval scheduling. It is deliberately not advertised as a replacement for a distributed workflow engine.

Platform anchors:
- Apache Airflow models schedules, tasks, task dependencies, retries, and timeouts around DAGs: https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html
- Temporal durable execution records workflow progress so work can resume after worker failure; its Rust SDK became generally available in September 2026: https://temporal.io/blog/build-durable-applications-rust-temporal-rust-sdk-now-generally-available
- OpenTelemetry supports traces, metrics, logs and baggage and context propagation across distributed boundaries: https://opentelemetry.io/docs/concepts/signals/ and https://opentelemetry.io/docs/concepts/context-propagation/
