from __future__ import annotations

import argparse
import json

from seraph.graph.persistence import save_json
from seraph.sources.space.gnss_demo import build_demo_graph, run_demo


def main() -> int:
    parser = argparse.ArgumentParser(prog="seraph-pci", description="Seraph Planetary Continuity Intelligence")
    parser.add_argument("command", choices=("demo", "validate"), nargs="?", default="demo")
    parser.add_argument("--graph-out", default=None)
    args = parser.parse_args()
    graph = build_demo_graph()
    if args.command == "validate":
        print("PCI_GRAPH_VALIDATION=PASS")
        print(f"NODES={graph.snapshot().entity_count}")
        print(f"RELATIONSHIPS={graph.snapshot().relationship_count}")
        return 0
    if args.graph_out:
        save_json(graph, args.graph_out, overwrite=True)
        print(f"GRAPH_WRITTEN={args.graph_out}")
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
    return 0
