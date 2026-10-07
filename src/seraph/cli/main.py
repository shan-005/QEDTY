from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seraph.cli.validate import validate
from seraph.core.version import PRODUCT_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seraph", description="SERAPH-PCI-X Planetary Continuity Intelligence"
    )
    p.add_argument("--version", action="version", version="%(prog)s %(prog_version)s")
    p.set_defaults(prog_version=PRODUCT_VERSION)
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("validate", help="validate installed contracts")
    s.add_parser("demo", help="run deterministic demonstration")
    for name in ("scenario", "impact", "resilience"):
        sub = s.add_parser(name)
        sub.add_argument("action", choices=["demo"])
    ec = s.add_parser("entity")
    ec.add_argument("action", choices=["create"])
    ec.add_argument("--type", default="other")
    ec.add_argument("--name", default="Demo")
    out = s.add_parser("export")
    out.add_argument("kind", choices=["demo", "validate"])
    out.add_argument("--format", choices=["json", "table"], default="json")
    out.add_argument("--output", type=Path)
    return p


def _emit(payload: Any, *, fmt: str = "json", output: Path | None = None) -> int:
    from seraph.output.json import dumps
    from seraph.output.table import summary_rows

    text = (
        dumps(payload)
        if fmt == "json"
        else summary_rows(payload if isinstance(payload, dict) else {"value": 1})
    )
    print(text)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _emit(validate())
    if args.command == "demo":
        from seraph.cli.scenario import demo_payload

        return _emit(demo_payload())
    if args.command in {"scenario", "impact", "resilience"}:
        module = __import__(f"seraph.cli.{args.command}", fromlist=["demo_payload"]).demo_payload
        return _emit(module())
    if args.command == "entity":
        from seraph.core.enums import EntityType
        from seraph.core.hash import deterministic_id

        et = (
            EntityType(args.type)
            if args.type in {e.value for e in EntityType}
            else EntityType.OTHER
        )
        return _emit(
            {
                "entity_id": deterministic_id("entity", "seraph", et.value, args.name.casefold()),
                "entity_type": et.value,
                "canonical_name": args.name,
            }
        )
    if args.command == "export":
        payload = (
            validate()
            if args.kind == "validate"
            else __import__("seraph.cli.scenario", fromlist=["demo_payload"]).demo_payload()
        )
        return _emit(payload, fmt=args.format, output=args.output)
    return 2
