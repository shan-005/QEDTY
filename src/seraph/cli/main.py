from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from seraph.cli.validate import validate


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seraph", description="SERAPH-PCI-X Planetary Continuity Intelligence"
    )
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("validate")
    s.add_parser("demo")
    sc = s.add_parser("scenario")
    sc.add_argument("action", choices=["demo"])
    ic = s.add_parser("impact")
    ic.add_argument("action", choices=["demo"])
    rc = s.add_parser("resilience")
    rc.add_argument("action", choices=["demo"])
    ec = s.add_parser("entity")
    ec.add_argument("action", choices=["create"])
    ec.add_argument("--type", required=False, default="other")
    ec.add_argument("--name", required=False, default="Demo")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        print(json.dumps(validate(), sort_keys=True))
        return 0
    if args.command == "demo":
        from seraph.cli.scenario import demo_payload

        print(json.dumps(demo_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "scenario":
        print(json.dumps(demo_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "impact":
        from seraph.cli.impact import demo_payload

        print(json.dumps(demo_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "resilience":
        from seraph.cli.resilience import demo_payload

        print(json.dumps(demo_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "entity":
        from seraph.core.enums import EntityType
        from seraph.core.hash import deterministic_id

        et = (
            EntityType(args.type)
            if args.type in {e.value for e in EntityType}
            else EntityType.OTHER
        )
        print(
            json.dumps(
                {
                    "entity_id": deterministic_id(
                        "entity", "seraph", et.value, args.name.casefold()
                    ),
                    "entity_type": et.value,
                    "canonical_name": args.name,
                },
                sort_keys=True,
            )
        )
        return 0
    return 2
