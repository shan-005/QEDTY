# SERAPH-PCI-X Temporal 2.0.0 installation

This archive is an overlay for the root of an existing SERAPH-PCI-X checkout.
It does not contain or replace the root README, project manifest, lockfile,
or unrelated modules.

```bash
cd ~/seraph
unzip -o /mnt/c/Users/nirik/Downloads/seraph_pci_x_temporal_v2_final.zip

uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
uv run mypy src

uv run python scripts/check_temporal_conformance.py

protoc \
  --proto_path=proto \
  --descriptor_set_out=/tmp/seraph-temporal.pb \
  proto/seraph/temporal/v1/temporal.proto

test -s /tmp/seraph-temporal.pb && echo "Temporal Protobuf descriptor: PASS"

git restore -- src/seraph/_version.py
git --no-pager diff --check
git status --short
```

The archive intentionally does not include `target/` or Python bytecode.
