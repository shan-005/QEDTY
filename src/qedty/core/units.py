from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import UnitError

# Dimension order follows the seven SI base quantities, with information as an
# explicit QEDTY extension dimension. Currency is deliberately excluded from
# this physical-unit registry; economics owns currency and FX semantics.
Dimension = tuple[int, int, int, int, int, int, int, int]
DIMENSIONLESS: Dimension = (0, 0, 0, 0, 0, 0, 0, 0)
LENGTH: Dimension = (1, 0, 0, 0, 0, 0, 0, 0)
MASS: Dimension = (0, 1, 0, 0, 0, 0, 0, 0)
TIME: Dimension = (0, 0, 1, 0, 0, 0, 0, 0)
CURRENT: Dimension = (0, 0, 0, 1, 0, 0, 0, 0)
TEMPERATURE: Dimension = (0, 0, 0, 0, 1, 0, 0, 0)
AMOUNT: Dimension = (0, 0, 0, 0, 0, 1, 0, 0)
LUMINOUS_INTENSITY: Dimension = (0, 0, 0, 0, 0, 0, 1, 0)
INFORMATION: Dimension = (0, 0, 0, 0, 0, 0, 0, 1)


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    code: str
    dimension: Dimension
    scale_to_si: Decimal
    offset_to_si: Decimal = Decimal(0)
    aliases: tuple[str, ...] = ()
    symbol: str | None = None

    @property
    def is_affine(self) -> bool:
        return self.offset_to_si != 0

    def to_si(self, value: Decimal) -> Decimal:
        return value * self.scale_to_si + self.offset_to_si

    def from_si(self, value: Decimal) -> Decimal:
        return (value - self.offset_to_si) / self.scale_to_si


# UCUM names are preferred where practical; common human spellings are aliases.
_DEFINITIONS: tuple[UnitDefinition, ...] = (
    UnitDefinition("1", DIMENSIONLESS, Decimal(1), aliases=("one", "dimensionless")),
    UnitDefinition("m", LENGTH, Decimal(1), aliases=("meter", "metre")),
    UnitDefinition("km", LENGTH, Decimal(1000), aliases=("kilometer", "kilometre")),
    UnitDefinition("cm", LENGTH, Decimal("0.01")),
    UnitDefinition("mm", LENGTH, Decimal("0.001")),
    UnitDefinition("um", LENGTH, Decimal("0.000001"), aliases=("µm",)),
    UnitDefinition("nm", LENGTH, Decimal("0.000000001")),
    UnitDefinition("kg", MASS, Decimal(1)),
    UnitDefinition("g", MASS, Decimal("0.001"), aliases=("gram",)),
    UnitDefinition("mg", MASS, Decimal("0.000001")),
    UnitDefinition("t", MASS, Decimal(1000), aliases=("tonne",)),
    UnitDefinition("s", TIME, Decimal(1), aliases=("sec", "second")),
    UnitDefinition("ms", TIME, Decimal("0.001")),
    UnitDefinition("us", TIME, Decimal("0.000001"), aliases=("µs",)),
    UnitDefinition("ns", TIME, Decimal("0.000000001")),
    UnitDefinition("min", TIME, Decimal(60)),
    UnitDefinition("h", TIME, Decimal(3600), aliases=("hr", "hour")),
    UnitDefinition("d", TIME, Decimal(86400), aliases=("day",)),
    UnitDefinition("K", TEMPERATURE, Decimal(1)),
    UnitDefinition("Cel", TEMPERATURE, Decimal(1), Decimal("273.15"), aliases=("degC", "°C")),
    UnitDefinition("A", CURRENT, Decimal(1), aliases=("amp", "ampere")),
    UnitDefinition("mol", AMOUNT, Decimal(1)),
    UnitDefinition("cd", LUMINOUS_INTENSITY, Decimal(1)),
    UnitDefinition("rad", DIMENSIONLESS, Decimal(1), aliases=("radian",)),
    UnitDefinition(
        "deg",
        DIMENSIONLESS,
        Decimal("0.017453292519943295769236907684886"),
        aliases=("degree", "°"),
    ),
    UnitDefinition("Hz", (0, 0, -1, 0, 0, 0, 0, 0), Decimal(1)),
    UnitDefinition("N", (1, 1, -2, 0, 0, 0, 0, 0), Decimal(1)),
    UnitDefinition("kN", (1, 1, -2, 0, 0, 0, 0, 0), Decimal(1000)),
    UnitDefinition("Pa", (-1, 1, -2, 0, 0, 0, 0, 0), Decimal(1)),
    UnitDefinition("kPa", (-1, 1, -2, 0, 0, 0, 0, 0), Decimal(1000)),
    UnitDefinition("MPa", (-1, 1, -2, 0, 0, 0, 0, 0), Decimal(1000000)),
    UnitDefinition("bar", (-1, 1, -2, 0, 0, 0, 0, 0), Decimal(100000)),
    UnitDefinition("J", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(1)),
    UnitDefinition("kJ", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(1000)),
    UnitDefinition("MJ", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(1000000)),
    UnitDefinition("W", (2, 1, -3, 0, 0, 0, 0, 0), Decimal(1)),
    UnitDefinition("kW", (2, 1, -3, 0, 0, 0, 0, 0), Decimal(1000)),
    UnitDefinition("MW", (2, 1, -3, 0, 0, 0, 0, 0), Decimal(1000000)),
    UnitDefinition("GW", (2, 1, -3, 0, 0, 0, 0, 0), Decimal(1000000000)),
    UnitDefinition("Wh", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(3600)),
    UnitDefinition("kWh", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(3600000)),
    UnitDefinition("MWh", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(3600000000)),
    UnitDefinition("GWh", (2, 1, -2, 0, 0, 0, 0, 0), Decimal(3600000000000)),
    UnitDefinition("bit", INFORMATION, Decimal(1)),
    UnitDefinition("kbit", INFORMATION, Decimal(1000)),
    UnitDefinition("Mbit", INFORMATION, Decimal(1000000)),
    UnitDefinition("Gbit", INFORMATION, Decimal(1000000000)),
    UnitDefinition("B", INFORMATION, Decimal(8), aliases=("byte",)),
)

_BY_CODE: dict[str, UnitDefinition] = {}
for _definition in _DEFINITIONS:
    _BY_CODE[_definition.code] = _definition
    for _alias in _definition.aliases:
        _BY_CODE[_alias] = _definition


_EXPRESSION_TOKEN = re.compile(r"(?P<code>[A-Za-zµ°]+|1)(?:\^(?P<exp>-?\d+))?$")


def get_unit(code: str) -> UnitDefinition:
    """Resolve a registered unit or a restricted multiplicative expression."""
    text = code.strip()
    if text in _BY_CODE:
        return _BY_CODE[text]
    return parse_unit_expression(text)


def parse_unit_expression(expression: str) -> UnitDefinition:
    """Parse a simple UCUM-like product/quotient expression.

    Supported syntax is deliberately explicit: ``kg*m/s^2``, ``m/s``,
    ``MW``, etc. Parentheses, implicit multiplication and arbitrary prefixes
    are rejected rather than guessed.
    """
    text = expression.replace(" ", "")
    if not text:
        raise UnitError("unit expression must not be blank")
    tokens = re.split(r"([*/])", text)
    numerator = True
    dimension: list[int] = list(DIMENSIONLESS)
    scale = Decimal(1)
    affine = False
    for token in tokens:
        if not token:
            continue
        if token == "*":  # nosec B105
            numerator = True
            continue
        if token == "/":  # nosec B105
            numerator = False
            continue
        match = _EXPRESSION_TOKEN.fullmatch(token)
        if match is None:
            raise UnitError(f"unsupported unit expression token: {token!r}")
        code = match.group("code")
        exponent = int(match.group("exp") or "1")
        definition = _BY_CODE.get(code)
        if definition is None:
            raise UnitError(f"unknown unit: {code!r}")
        if definition.is_affine and (exponent != 1 or not numerator):
            raise UnitError("affine units cannot be used in multiplicative expressions")
        if definition.is_affine:
            affine = True
        sign = 1 if numerator else -1
        for index, value in enumerate(definition.dimension):
            dimension[index] += sign * exponent * value
        scale *= definition.scale_to_si ** (sign * exponent)
        if affine:
            # Affine units are only legal as the sole term.
            if len(tokens) != 1:
                raise UnitError("affine units must stand alone")
            return definition
    return UnitDefinition(
        code=text,
        dimension=cast("Dimension", tuple(dimension)),
        scale_to_si=scale,
        aliases=(),
    )


def are_compatible(first: str, second: str) -> bool:
    return get_unit(first).dimension == get_unit(second).dimension


def convert_value(value: Decimal | int | float, from_unit: str, to_unit: str) -> Decimal:
    """Convert a scalar between dimensionally compatible units."""
    source = get_unit(from_unit)
    target = get_unit(to_unit)
    if source.dimension != target.dimension:
        raise UnitError(f"incompatible units: {from_unit!r} and {to_unit!r}")
    decimal_value = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(context.prec, 34)
        return target.from_si(source.to_si(decimal_value))


class Quantity(BaseModel):
    """Dimension-checked quantity using Decimal for exact decimal arithmetic."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    value: Decimal
    unit: str = Field(min_length=1, max_length=128)

    _unit_cache: ClassVar[dict[str, UnitDefinition]] = {}

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise UnitError("unit must not be blank")
        get_unit(text)
        return text

    @property
    def definition(self) -> UnitDefinition:
        cached = self._unit_cache.get(self.unit)
        if cached is None:
            cached = get_unit(self.unit)
            self._unit_cache[self.unit] = cached
        return cached

    @property
    def dimension(self) -> Dimension:
        return self.definition.dimension

    @property
    def si_value(self) -> Decimal:
        return self.definition.to_si(self.value)

    def to(self, unit: str) -> Quantity:
        return Quantity(value=convert_value(self.value, self.unit, unit), unit=unit)

    def scaled(self, factor: int | float | Decimal) -> Quantity:
        if self.definition.is_affine:
            raise UnitError("absolute affine quantities cannot be scaled")
        return Quantity(value=self.value * Decimal(str(factor)), unit=self.unit)

    def __add__(self, other: Quantity) -> Quantity:
        if self.definition.is_affine or other.definition.is_affine:
            raise UnitError("absolute affine quantities cannot be added")
        if self.dimension != other.dimension:
            raise UnitError(f"cannot add {self.unit!r} and {other.unit!r}")
        return Quantity(
            value=self.value + convert_value(other.value, other.unit, self.unit),
            unit=self.unit,
        )

    def __sub__(self, other: Quantity) -> Quantity:
        if self.definition.is_affine or other.definition.is_affine:
            raise UnitError(
                "absolute affine quantities cannot be subtracted; convert to a delta unit first"
            )
        if self.dimension != other.dimension:
            raise UnitError(f"cannot subtract {other.unit!r} from {self.unit!r}")
        return Quantity(
            value=self.value - convert_value(other.value, other.unit, self.unit),
            unit=self.unit,
        )

    def __mul__(self, other: int | float | Decimal | Quantity) -> Quantity:
        if isinstance(other, Quantity):
            if self.definition.is_affine or other.definition.is_affine:
                raise UnitError("affine quantities cannot be multiplied")
            unit = f"{self.unit}*{other.unit}"
            return Quantity(value=self.value * other.value, unit=unit)
        return self.scaled(other)

    def __truediv__(self, other: int | float | Decimal | Quantity) -> Quantity:
        if isinstance(other, Quantity):
            if self.definition.is_affine or other.definition.is_affine:
                raise UnitError("affine quantities cannot be divided")
            unit = f"{self.unit}/{other.unit}"
            return Quantity(value=self.value / other.value, unit=unit)
        if other == 0:
            raise ZeroDivisionError("quantity division by zero")
        return self.scaled(Decimal(1) / Decimal(str(other)))
