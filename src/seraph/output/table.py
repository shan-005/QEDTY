def summary_rows(summary:dict[str,int])->str:
    lines=["metric | value","--- | ---"]
    lines += [f"{k} | {v}" for k,v in sorted(summary.items())]
    return "\n".join(lines)
