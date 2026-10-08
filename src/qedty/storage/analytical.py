from __future__ import annotations

from pathlib import Path
from typing import Any


def write_parquet(rows: list[dict[str, Any]], path: str | Path) -> None:
    """Write a Parquet file when pyarrow is installed; fail explicitly otherwise."""
    try:
        import pyarrow as pa  # type: ignore[import-untyped]
        import pyarrow.parquet as pq  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for Parquet storage") from exc
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), p)


def duckdb_query(path: str | Path, sql: str) -> list[dict[str, Any]]:
    """Execute a caller-supplied read/query statement with the file path as parameter 1."""
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("duckdb is required for analytical queries") from exc
    connection = duckdb.connect()
    try:
        result = connection.execute(sql, [str(path)])
        columns = [name for name, *_ in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    finally:
        connection.close()
