from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RedistributionPolicy(StrEnum):
    PUBLIC = "public"
    ATTRIBUTION_REQUIRED = "attribution_required"
    NON_COMMERCIAL = "non_commercial"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class LicensePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    spdx_expression: str = Field(min_length=1, max_length=256)
    redistribution: RedistributionPolicy
    commercial_use: bool
    attribution_required: bool
    source_url: str = Field(min_length=1, max_length=2048)
    notes: str | None = None


DEFAULT_UNKNOWN_LICENSE = LicensePolicy(
    spdx_expression="NOASSERTION",
    redistribution=RedistributionPolicy.UNKNOWN,
    commercial_use=False,
    attribution_required=False,
    source_url="about:blank",
    notes="License/redistribution terms not established; do not assume commercial redistribution rights.",
)
