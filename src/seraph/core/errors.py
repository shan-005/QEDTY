from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class SeraphError(Exception):
    """Base exception with a stable machine-readable error code."""

    code = "seraph.error"

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.message = message
        self.details = dict(details or {})
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


class ContractError(SeraphError):
    code = "seraph.contract"


class IdentityError(ContractError):
    code = "seraph.identity"


class ProvenanceError(ContractError):
    code = "seraph.provenance"


class TemporalError(ContractError):
    code = "seraph.temporal"


class SpatialError(ContractError):
    code = "seraph.spatial"


class GeometryError(SpatialError):
    code = "seraph.geometry"


class UnitError(ContractError):
    code = "seraph.unit"


class SchemaError(ContractError):
    code = "seraph.schema"


class InteroperabilityError(ContractError):
    code = "seraph.interoperability"


class NormalizationError(ContractError):
    code = "seraph.normalization"


class SourceError(SeraphError):
    code = "seraph.source"


class StorageError(SeraphError):
    code = "seraph.storage"


class ModelError(SeraphError):
    code = "seraph.model"


class PropagationError(ModelError):
    code = "seraph.propagation"


class OptimizationError(ModelError):
    code = "seraph.optimization"


class ConfigurationError(SeraphError):
    code = "seraph.configuration"


class SemanticValidationError(ContractError):
    code = "seraph.validation"
