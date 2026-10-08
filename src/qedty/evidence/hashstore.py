from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from qedty.core.errors import IdentityError, StorageError


class EvidenceFileStore:
    """Filesystem content-addressed store keyed by lowercase SHA-256."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_digest(digest: str) -> str:
        normalized = digest.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise IdentityError("digest must be a 64-character lowercase SHA-256 hex value")
        return normalized

    def _path(self, digest: str) -> Path:
        normalized = self._validate_digest(digest)
        return self.root / normalized[:2] / normalized[2:]

    def has(self, digest: str) -> bool:
        return self._path(digest).is_file()

    def put(self, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        target = self._path(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if self.get(digest) != payload:
                raise StorageError("content-addressed collision")
            return digest
        name: str | None = None
        try:
            fd, name = tempfile.mkstemp(prefix=".evidence-", dir=target.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            Path(name).replace(target)
        except OSError as exc:
            if name is not None:
                with contextlib.suppress(OSError):
                    Path(name).unlink()
            raise StorageError(f"failed to store evidence: {exc}") from exc
        return digest

    def put_stream(self, stream: BinaryIO, *, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        digest = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(
            prefix=".evidence-stream-", dir=self.root, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            try:
                while chunk := stream.read(chunk_size):
                    digest.update(chunk)
                    total += len(chunk)
                    temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
                final_digest = digest.hexdigest()
                target = self._path(final_digest)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if self.get(final_digest) != temp_path.read_bytes():
                        raise StorageError("content-addressed collision")
                else:
                    temp_path.replace(target)
                return final_digest, total
            finally:
                temp_path.unlink(missing_ok=True)

    def get(self, digest: str) -> bytes:
        target = self._path(digest)
        try:
            payload = target.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"evidence not found: {digest}") from exc
        except OSError as exc:
            raise StorageError(f"failed to read evidence: {exc}") from exc
        actual = hashlib.sha256(payload).hexdigest()
        if actual != digest.lower():
            raise StorageError("stored evidence digest mismatch")
        return payload

    def verify(self, digest: str) -> bool:
        try:
            self.get(digest)
        except StorageError:
            return False
        return True
