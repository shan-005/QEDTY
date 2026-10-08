from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO, cast


class EvidenceStore:
    """Content-addressed evidence store with atomic writes and JSON metadata."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "objects").mkdir(exist_ok=True)
        (self.path / "metadata").mkdir(exist_ok=True)

    def put_bytes(
        self, content: bytes, *, media_type: str = "application/octet-stream", source_uri: str = ""
    ) -> str:
        digest = sha256(content).hexdigest()
        obj = self.path / "objects" / digest
        if not obj.exists():
            tmp = obj.with_suffix(".tmp")
            tmp.write_bytes(content)
            tmp.replace(obj)
        meta = self.path / "metadata" / f"{digest}.json"
        if not meta.exists():
            tmpm = meta.with_suffix(".tmp")
            tmpm.write_text(
                json.dumps(
                    {
                        "sha256": digest,
                        "size": len(content),
                        "media_type": media_type,
                        "source_uri": source_uri,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            tmpm.replace(meta)
        return digest

    def put_text(self, content: str, *, source_uri: str = "") -> str:
        return self.put_bytes(
            content.encode("utf-8"), media_type="text/plain; charset=utf-8", source_uri=source_uri
        )

    def exists(self, digest: str) -> bool:
        return (self.path / "objects" / digest).is_file()

    def open(self, digest: str) -> BinaryIO:
        p = self.path / "objects" / digest
        if not p.is_file():
            raise KeyError(digest)
        return p.open("rb")

    def get_bytes(self, digest: str) -> bytes:
        with self.open(digest) as f:
            return f.read()

    def metadata(self, digest: str) -> dict[str, Any]:
        p = self.path / "metadata" / f"{digest}.json"
        if not p.is_file():
            raise KeyError(digest)
        return cast("dict[str, Any]", json.loads(p.read_text(encoding="utf-8")))
