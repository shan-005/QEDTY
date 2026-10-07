# Storage contract

SERAPH storage distinguishes operational state from analytical interchange and provenance. Evidence is content-addressed with SHA-256 and written atomically. Provenance is append-only and hash chained. SQLite is used as a local transactional reference backend; analytical backends are optional adapters.

Standards/platform anchors:
- SQLite WAL behavior and persistence requirements: https://www.sqlite.org/wal.html
- SQLite transaction semantics: https://www.sqlite.org/lang_transaction.html
- PostgreSQL concurrency control and serializable isolation: https://www.postgresql.org/docs/current/mvcc.html
- PostGIS spatial predicates can use GiST spatial indexes: https://postgis.net/docs/ST_Intersects.html and https://postgis.net/documentation/faq/spatial-indexes/
- Apache Arrow/PyArrow provides columnar in-memory datasets and Parquet interchange: https://arrow.apache.org/docs/python/parquet.html
- DuckDB pushes projection/filter predicates into Parquet scans: https://duckdb.org/docs/stable/data/parquet/overview
- W3C PROV-O provides interoperable provenance modeling: https://www.w3.org/TR/prov-o/
