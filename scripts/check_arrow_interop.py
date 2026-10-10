"""Verify real PyArrow <-> Rust Arrow IPC interoperability."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pyarrow as pa


def main() -> int:
    metadata = {
        b"qedty.contract": b"arrow-interop@1",
        b"qedty.origin": b"python",
    }
    schema = pa.schema(
        [
            pa.field("active", pa.bool_()),
            pa.field("count", pa.int64()),
            pa.field("event_time_ms", pa.timestamp("ms", tz="UTC")),
            pa.field("measurement", pa.float64()),
            pa.field("name", pa.string()),
        ],
        metadata=metadata,
    )
    timestamp = pa.array(
        [1712345678901, None, -1], type=pa.int64()
    ).cast(pa.timestamp("ms", tz="UTC"))

    table = pa.Table.from_arrays(
        [
            pa.array([True, None, False], type=pa.bool_()),
            pa.array([1, None, 3], type=pa.int64()),
            timestamp,
            pa.array([1.25, None, -2.5], type=pa.float64()),
            pa.array(["alpha", None, "gamma"], type=pa.string()),
        ],
        schema=schema,
    )

    with tempfile.TemporaryDirectory(prefix="qedty-arrow-") as tmp:
        directory = Path(tmp)
        python_stream = directory / "python.arrow"
        rust_stream = directory / "rust.arrow"

        with pa.OSFile(str(python_stream), "wb") as sink:
            with pa.ipc.new_stream(sink, schema) as writer:
                writer.write_table(table)

        subprocess.run(
            [
                "cargo", "run", "--locked", "-p", "qedty-core",
                "--example", "arrow_interop_smoke", "--",
                str(rust_stream), str(python_stream),
            ],
            check=True,
        )

        output = pa.ipc.open_stream(str(rust_stream)).read_all()
        assert output.num_rows == 3
        assert output["active"].to_pylist() == [True, None, False]
        assert output["count"].to_pylist() == [1, None, 3]
        assert output["measurement"].to_pylist() == [1.25, None, -2.5]
        assert output["name"].to_pylist() == ["alpha", None, "gamma"]
        assert output["event_time_ms"].type == pa.timestamp("ms", tz="UTC")
        assert output["event_time_ms"].cast(pa.int64()).to_pylist() == [
            1712345678901, None, -1
        ]
        assert output.schema.metadata == {
            b"qedty.contract": b"arrow-interop@1",
            b"qedty.origin": b"rust",
        }

    print(f"PASS: Rust/PyArrow bidirectional IPC interoperability ({pa.__version__}).")
    print("PASS: Nulls, UTC timestamp values, column types, and schema metadata.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: Arrow interoperability: {exc}", file=sys.stderr)
        raise SystemExit(1)
