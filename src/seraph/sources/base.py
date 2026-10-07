from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True, slots=True)
class SourceContext:
    source_id: str
    license_scope: str
    configuration_digest: str
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    timeout_seconds: float = 20.0
    allowed_hosts: tuple[str, ...] = ()
    user_agent: str = "seraph-pci-x/0.1a0"
    max_bytes: int = 10_000_000

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_bytes <= 0:
            raise ValueError("timeout and max_bytes must be positive")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

    def permits(self, uri: str) -> bool:
        host = urlparse(uri).hostname or ""
        return not self.allowed_hosts or host in self.allowed_hosts


@dataclass(frozen=True, slots=True)
class FetchResult:
    uri: str
    content: bytes
    content_sha256: str
    fetched_at: datetime
    status_code: int
    etag: str | None = None
    last_modified: str | None = None

    @classmethod
    def from_bytes(
        cls,
        uri: str,
        content: bytes,
        status_code: int = 200,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        return cls(
            uri,
            content,
            sha256(content).hexdigest(),
            datetime.now(UTC),
            status_code,
            etag,
            last_modified,
        )


class SourceAdapter(ABC):
    domain = "unknown"

    @abstractmethod
    def discover(self, context: SourceContext) -> tuple[object, ...]:
        """Discover normalized records under an explicit source contract."""
        raise NotImplementedError

    def fetch(self, uri: str, context: SourceContext) -> FetchResult:
        if not context.permits(uri):
            raise ValueError(f"source host not allowed: {uri}")
        headers = {"User-Agent": context.user_agent, "Accept": "*/*"}
        with httpx.Client(
            timeout=context.timeout_seconds, follow_redirects=False, headers=headers
        ) as client:
            response = client.get(uri)
            response.raise_for_status()
            content = response.content
            if len(content) > context.max_bytes:
                raise ValueError("source response exceeds max_bytes")
            return FetchResult.from_bytes(
                uri,
                content,
                response.status_code,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
