from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecurityObservation:
    observation_id: str
    path: str
    category: str
    rule_id: str
    severity: str
    evidence_excerpt: str


class RepositorySecurityAdapter:
    """Security-source adapter. It never defines SERAPH world-model entities or platform ranking semantics."""

    domain = "repository_security"
    SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\b\s*[:=]")

    def inspect_text(self, path: Path) -> tuple[SecurityObservation, ...]:
        out = []
        for i, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if self.SECRET_RE.search(line):
                out.append(
                    SecurityObservation(
                        f"repo-sec:{path}:{i}",
                        str(path),
                        "credential-exposure",
                        "credential-assignment",
                        "high",
                        line[:240],
                    )
                )
        return tuple(out)
