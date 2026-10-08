# Storage research baseline

The reference store is deliberately multi-backend: SQLite for local operational correctness, PostgreSQL/PostGIS for authoritative multi-user geospatial operations, and Arrow/Parquet/DuckDB for analytical execution. The interfaces preserve stable object hashes and provenance across these representations.

PostgreSQL's MVCC and serializable controls inform production-server guidance. SQLite WAL is used locally, with the important limitation that SQLite permits only one simultaneous write transaction.
