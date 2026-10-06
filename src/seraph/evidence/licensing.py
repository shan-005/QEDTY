from enum import StrEnum
from pydantic import BaseModel,ConfigDict,Field
class Redistribution(StrEnum): PUBLIC="public"; ATTRIBUTION="attribution_required"; NON_COMMERCIAL="non_commercial"; RESTRICTED="restricted"; UNKNOWN="unknown"
class LicensePolicy(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    spdx_expression:str=Field(min_length=1,max_length=128); redistribution:Redistribution; commercial_use:bool; attribution_required:bool; source_url:str=Field(min_length=1,max_length=2048)
DEFAULT_UNKNOWN=LicensePolicy(spdx_expression="NOASSERTION",redistribution=Redistribution.UNKNOWN,commercial_use=False,attribution_required=False,source_url="about:blank")
