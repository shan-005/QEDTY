from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class SecurityObservation:
    observation_id: str
    path: str
    category: str
    rule_id: str
    severity: str
    evidence_excerpt: str
    line_number: int = 0
    content_sha256: str = ""


class RepositorySecurityAdapter:
    """Safe, bounded repository observation adapter.

    It never executes repository code and never turns an observation into a
    SERAPH world-model entity. File-size and traversal limits are explicit.
    """

    domain = "repository_security"
    SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\b\s*[:=].*$")

    def inspect_text(
        self, path: Path, *, max_bytes: int = 2_000_000
    ) -> tuple[SecurityObservation, ...]:
        resolved = path.resolve()
        if resolved.is_dir() or not resolved.is_file():
            raise ValueError("repository-security adapter requires a regular file")
        if resolved.stat().st_size > max_bytes:
            raise ValueError("file exceeds inspection limit")
        raw = resolved.read_bytes()
        content_hash = sha256(raw).hexdigest()
        out: list[SecurityObservation] = []
        for i, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            if self.SECRET_RE.search(line):
                redacted = self.SECRET_RE.sub(r"\1=<redacted>", line[:240])
                out.append(
                    SecurityObservation(
                        f"repo-sec:{resolved}:{i}",
                        str(resolved),
                        "credential-exposure",
                        "credential-assignment",
                        "high",
                        redacted,
                        i,
                        content_hash,
                    )
                )
        return tuple(out)
