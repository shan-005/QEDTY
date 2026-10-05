from __future__ import annotations

import argparse
import json
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seraph-pci",
        description="SERAPH-PCI-X planetary continuity intelligence tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate import and domain contracts")
    sub.add_parser("demo", help="run the deterministic GNSS continuity demonstration")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        from seraph.core.enums import EpistemicStatus
        from seraph.graph.schema import GraphSchemaVersion
        print(json.dumps({
            "status": "ok",
            "schema": GraphSchemaVersion().key,
            "epistemic_states": [s.value for s in EpistemicStatus],
        }, sort_keys=True))
        return 0
    if args.command == "demo":
        from seraph.sources.space.gnss_demo import run_demo
        print(json.dumps(run_demo(), sort_keys=True, indent=2))
        return 0
    raise RuntimeError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(run())
