from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermissionState(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class Redistribution(StrEnum):
    PUBLIC = "public"
    ATTRIBUTION = "attribution_required"
    NON_COMMERCIAL = "non_commercial"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class LicensePolicy(BaseModel):
    """Explicit rights metadata; unknown rights are never treated as denied."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    spdx_expression: str = Field(min_length=1, max_length=512)
    redistribution: Redistribution = Redistribution.UNKNOWN
    commercial_use: PermissionState = PermissionState.UNKNOWN
    attribution_required: bool | None = None
    source_url: str = Field(min_length=1, max_length=4096)
    rights_holder: str | None = Field(default=None, max_length=512)
    access_rights: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("spdx_expression", "source_url", "rights_holder", "access_rights", "notes")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @property
    def is_unknown(self) -> bool:
        return (
            self.spdx_expression.upper() in {"NOASSERTION", "UNKNOWN"}
            or self.redistribution == Redistribution.UNKNOWN
            or self.commercial_use == PermissionState.UNKNOWN
        )


DEFAULT_UNKNOWN = LicensePolicy(
    spdx_expression="NOASSERTION",
    redistribution=Redistribution.UNKNOWN,
    commercial_use=PermissionState.UNKNOWN,
    attribution_required=None,
    source_url="about:blank",
)
