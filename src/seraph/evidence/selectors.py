from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SelectorType(StrEnum):
    TEXT_QUOTE = "text_quote"
    TEXT_POSITION = "text_position"
    JSON_POINTER = "json_pointer"
    BYTE_RANGE = "byte_range"
    LINE_RANGE = "line_range"
    URI_FRAGMENT = "uri_fragment"
    ROW_RANGE = "row_range"


class EvidenceSelector(BaseModel):
    """Stable pointer into an immutable evidence representation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    selector_type: SelectorType
    value: str | None = Field(default=None, max_length=8192)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            self.selector_type
            in {
                SelectorType.TEXT_QUOTE,
                SelectorType.JSON_POINTER,
                SelectorType.URI_FRAGMENT,
            }
            and not self.value
        ):
            raise ValueError("selector value is required")
        if self.selector_type in {
            SelectorType.TEXT_POSITION,
            SelectorType.BYTE_RANGE,
            SelectorType.LINE_RANGE,
            SelectorType.ROW_RANGE,
        } and (self.start is None or self.end is None or self.end <= self.start):
            raise ValueError("range selectors require end > start")
        return self
