from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class QEDTYError(Exception):
    """Base exception with a stable machine-readable error code."""

    code = "qedty.error"

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.message = message
        self.details = dict(details or {})
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


class ContractError(QEDTYError):
    code = "qedty.contract"


class IdentityError(ContractError):
    code = "qedty.identity"


class ProvenanceError(ContractError):
    code = "qedty.provenance"


class TemporalError(ContractError):
    code = "qedty.temporal"


class SpatialError(ContractError):
    code = "qedty.spatial"


class GeometryError(SpatialError):
    code = "qedty.geometry"


class UnitError(ContractError):
    code = "qedty.unit"


class SchemaError(ContractError):
    code = "qedty.schema"


class InteroperabilityError(ContractError):
    code = "qedty.interoperability"


class NormalizationError(ContractError):
    code = "qedty.normalization"


class SourceError(QEDTYError):
    code = "qedty.source"


class StorageError(QEDTYError):
    code = "qedty.storage"


class ModelError(QEDTYError):
    code = "qedty.model"


class PropagationError(ModelError):
    code = "qedty.propagation"


class OptimizationError(ModelError):
    code = "qedty.optimization"


class ConfigurationError(QEDTYError):
    code = "qedty.configuration"


class SemanticValidationError(ContractError):
    code = "qedty.validation"
