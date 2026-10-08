from __future__ import annotations


def summary_rows(summary: dict[str, int]) -> str:
    lines = ["metric | value", "--- | ---"]
    lines += [f"{k} | {v}" for k, v in sorted(summary.items())]
    return "\n".join(lines)


def rows_to_csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    keys = sorted({k for r in rows for k in r})
    lines = [",".join(keys)]
    import csv
    import io

    for row in rows:
        buf = io.StringIO()
        csv.writer(buf, lineterminator="").writerow([row.get(k, "") for k in keys])
        lines.append(buf.getvalue())
    return "\n".join(lines)
