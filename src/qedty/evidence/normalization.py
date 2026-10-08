from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from qedty.core.hash import canonical_json, deterministic_id, sha256_hex

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    source_name: str
    record_id: str
    attributes: dict[str, Any]
    source_digest: str
    normalization_profile: str = "qedty-normalization@1"

    @property
    def normalized_digest(self) -> str:
        return sha256_hex(
            {
                "profile": self.normalization_profile,
                "source_digest": self.source_digest,
                "attributes": self.attributes,
            }
        )

    @property
    def record_digest(self) -> str:
        return deterministic_id(
            "normalized-record",
            self.source_name,
            self.record_id,
            self.source_digest,
            self.normalized_digest,
        )


def normalize_text(value: str, *, collapse_whitespace: bool = True, casefold: bool = False) -> str:
    normalized = value.strip()
    if collapse_whitespace:
        normalized = " ".join(normalized.split())
    if casefold:
        normalized = normalized.casefold()
    return normalized


def normalize_record(
    source_name: str,
    record_id: str,
    attributes: Mapping[str, Any],
    *,
    normalizers: Mapping[str, Callable[[Any], Any]] | None = None,
) -> NormalizedRecord:
    clean: dict[str, Any] = {}
    normalizers = normalizers or {}
    for key, value in attributes.items():
        name = normalize_text(str(key))
        if not name:
            continue
        transformed = normalizers[name](value) if name in normalizers else value
        clean[name] = transformed
    source_digest = sha256_hex(
        {"source_name": source_name, "record_id": record_id, "attributes": dict(attributes)}
    )
    return NormalizedRecord(source_name, record_id, clean, source_digest)


def canonical_row_bytes(attributes: Mapping[str, Any]) -> bytes:
    return canonical_json(dict(attributes)).encode("utf-8")
