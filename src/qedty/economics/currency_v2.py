"""Versioned, currency-neutral monetary primitives for v2 contracts.

The legacy :mod:`qedty.economics.currency` API remains unchanged for v1.
This module accepts Decimal values only and never performs network I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    InvalidOperation,
    localcontext,
)

FX_ARITHMETIC_PRECISION = 34
MAX_MINOR_UNIT_SCALE = 9

_SUPPORTED_ROUNDING_MODES = frozenset(
    {
        ROUND_05UP,
        ROUND_CEILING,
        ROUND_DOWN,
        ROUND_FLOOR,
        ROUND_HALF_DOWN,
        ROUND_HALF_EVEN,
        ROUND_HALF_UP,
        ROUND_UP,
    }
)
_CURRENCY_CODE_PATTERN = re.compile(r"[A-Z]{3}")


def _validate_currency_code(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _CURRENCY_CODE_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a three-letter uppercase currency code")


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _normalize_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _quantize_amount(value: Decimal, scale: int, rounding_mode: str) -> Decimal:
    quantum = Decimal(1).scaleb(-scale)
    try:
        return value.quantize(quantum, rounding=rounding_mode)
    except InvalidOperation as exc:
        raise ValueError("monetary amount exceeds supported decimal arithmetic") from exc


@dataclass(frozen=True, slots=True)
class CurrencyMetadata:
    """Precision and rounding metadata for one currency code."""

    currency_code: str
    minor_unit_scale: int
    rounding_mode: str = ROUND_HALF_EVEN

    def __post_init__(self) -> None:
        _validate_currency_code(self.currency_code, "currency_code")
        if (
            isinstance(self.minor_unit_scale, bool)
            or not isinstance(self.minor_unit_scale, int)
            or not 0 <= self.minor_unit_scale <= MAX_MINOR_UNIT_SCALE
        ):
            raise ValueError(
                f"minor_unit_scale must be an integer between 0 and {MAX_MINOR_UNIT_SCALE}"
            )
        if not isinstance(self.rounding_mode, str) or self.rounding_mode not in _SUPPORTED_ROUNDING_MODES:
            raise ValueError(f"unsupported decimal rounding mode: {self.rounding_mode!r}")


@dataclass(frozen=True, slots=True)
class CurrencyMetadataProfile:
    """Caller-supplied versioned currency metadata; codes are not allowlisted here."""

    profile_version: str
    currencies: tuple[CurrencyMetadata, ...]

    def __post_init__(self) -> None:
        _required_text(self.profile_version, "profile_version")
        if not isinstance(self.currencies, tuple):
            raise ValueError("currencies must be an immutable tuple")
        if not self.currencies:
            raise ValueError("currency metadata profile must contain at least one currency")
        if any(not isinstance(item, CurrencyMetadata) for item in self.currencies):
            raise ValueError("currencies must contain CurrencyMetadata values")
        codes = [item.currency_code for item in self.currencies]
        if len(set(codes)) != len(codes):
            raise ValueError("currency metadata profile contains duplicate currency codes")

    def metadata_for(self, currency_code: str) -> CurrencyMetadata:
        _validate_currency_code(currency_code, "currency_code")
        for metadata in self.currencies:
            if metadata.currency_code == currency_code:
                return metadata
        raise ValueError(
            f"currency {currency_code!r} is absent from metadata profile {self.profile_version!r}"
        )

    def validate_amount(self, amount: MoneyAmount) -> CurrencyMetadata:
        if amount.metadata_profile_version != self.profile_version:
            raise ValueError("money amount metadata profile version does not match supplied profile")
        metadata = self.metadata_for(amount.currency_code)
        represented = _quantize_amount(
            amount.amount, metadata.minor_unit_scale, metadata.rounding_mode
        )
        if represented != amount.amount:
            raise ValueError(
                f"amount for {amount.currency_code} exceeds its declared minor-unit scale"
            )
        return metadata


@dataclass(frozen=True, slots=True)
class MoneyAmount:
    """Non-negative monetary amount represented without binary floating point."""

    amount: Decimal
    currency_code: str
    metadata_profile_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise ValueError("amount must be Decimal; binary floats and implicit coercion are forbidden")
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("amount must be finite and non-negative")
        _validate_currency_code(self.currency_code, "currency_code")
        _required_text(self.metadata_profile_version, "metadata_profile_version")


@dataclass(frozen=True, slots=True)
class FxRate:
    """Directional FX quote: quote-currency units for one base-currency unit."""

    base_currency: str
    quote_currency: str
    rate: Decimal
    observed_at: datetime
    source: str
    provenance_id: str

    def __post_init__(self) -> None:
        _validate_currency_code(self.base_currency, "base_currency")
        _validate_currency_code(self.quote_currency, "quote_currency")
        if self.base_currency == self.quote_currency:
            raise ValueError("FX base and quote currencies must differ")
        if (
            not isinstance(self.rate, Decimal)
            or not self.rate.is_finite()
            or self.rate <= 0
        ):
            raise ValueError("FX rate must be a finite positive Decimal")
        object.__setattr__(self, "observed_at", _normalize_utc(self.observed_at, "observed_at"))
        _required_text(self.source, "source")
        _required_text(self.provenance_id, "provenance_id")


@dataclass(frozen=True, slots=True)
class FxSnapshot:
    """Immutable FX data with an explicit half-open validity interval."""

    snapshot_id: str
    as_of: datetime
    valid_from: datetime
    valid_to: datetime
    rates: tuple[FxRate, ...]

    def __post_init__(self) -> None:
        _required_text(self.snapshot_id, "snapshot_id")
        as_of = _normalize_utc(self.as_of, "as_of")
        valid_from = _normalize_utc(self.valid_from, "valid_from")
        valid_to = _normalize_utc(self.valid_to, "valid_to")
        if valid_from >= valid_to:
            raise ValueError("FX snapshot valid_from must be before valid_to")
        if not valid_from <= as_of < valid_to:
            raise ValueError("FX snapshot as_of must lie inside [valid_from, valid_to)")
        if not isinstance(self.rates, tuple):
            raise ValueError("rates must be an immutable tuple")
        if not self.rates:
            raise ValueError("FX snapshot must contain at least one rate")
        if any(not isinstance(rate, FxRate) for rate in self.rates):
            raise ValueError("rates must contain FxRate values")
        seen_pairs: set[tuple[str, str]] = set()
        for rate in self.rates:
            if rate.observed_at > as_of:
                raise ValueError("FX rate observation must not be later than snapshot as_of")
            pair = tuple(sorted((rate.base_currency, rate.quote_currency)))
            if pair in seen_pairs:
                raise ValueError(
                    "FX snapshot may contain only one directional quote per unordered currency pair"
                )
            seen_pairs.add(pair)
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_to", valid_to)

    def require_valid_at(self, effective_at: datetime) -> datetime:
        instant = _normalize_utc(effective_at, "effective_at")
        if not self.valid_from <= instant < self.valid_to:
            raise ValueError("FX snapshot is not valid at the requested instant")
        return instant

    def rate_for(
        self, source_currency: str, target_currency: str
    ) -> tuple[Decimal, FxRate, bool]:
        """Return source-to-target rate, quote provenance and reciprocal flag.

        Direct quotes win. A reciprocal is used only when no direct quote exists.
        Triangulation is intentionally unsupported and missing paths fail closed.
        """
        _validate_currency_code(source_currency, "source_currency")
        _validate_currency_code(target_currency, "target_currency")
        if source_currency == target_currency:
            raise ValueError("same-currency conversion does not require an FX rate")
        for rate in self.rates:
            if rate.base_currency == source_currency and rate.quote_currency == target_currency:
                return rate.rate, rate, False
            if rate.base_currency == target_currency and rate.quote_currency == source_currency:
                with localcontext() as context:
                    context.prec = FX_ARITHMETIC_PRECISION
                    context.rounding = ROUND_HALF_EVEN
                    reciprocal = Decimal(1) / rate.rate
                return reciprocal, rate, True
        raise ValueError(
            f"missing direct or reciprocal FX quote for {source_currency}/{target_currency}; "
            "triangulation is disabled"
        )


@dataclass(frozen=True, slots=True)
class MoneyConversion:
    """Converted amount plus deterministic inputs needed to audit the calculation."""

    source: MoneyAmount
    target: MoneyAmount
    applied_rate: Decimal
    unrounded_target_amount: Decimal
    rounding_mode: str
    metadata_profile_version: str
    fx_snapshot_id: str | None
    rate_base_currency: str | None
    rate_quote_currency: str | None
    rate_was_inverted: bool
    fx_source: str | None
    fx_provenance_id: str | None
    effective_at: datetime | None
    fx_snapshot_as_of: datetime | None
    calculation_precision: int = FX_ARITHMETIC_PRECISION


def convert_money(
    amount: MoneyAmount,
    target_currency_code: str,
    *,
    currency_profile: CurrencyMetadataProfile,
    fx_snapshot: FxSnapshot | None = None,
    effective_at: datetime | None = None,
) -> MoneyConversion:
    """Convert using explicit metadata and FX inputs, with one target-scale rounding step."""
    currency_profile.validate_amount(amount)
    target_metadata = currency_profile.metadata_for(target_currency_code)

    if amount.currency_code == target_currency_code:
        rounded = _quantize_amount(
            amount.amount, target_metadata.minor_unit_scale, target_metadata.rounding_mode
        )
        target = MoneyAmount(rounded, target_currency_code, currency_profile.profile_version)
        return MoneyConversion(
            source=amount,
            target=target,
            applied_rate=Decimal(1),
            unrounded_target_amount=amount.amount,
            rounding_mode=target_metadata.rounding_mode,
            metadata_profile_version=currency_profile.profile_version,
            fx_snapshot_id=None,
            rate_base_currency=None,
            rate_quote_currency=None,
            rate_was_inverted=False,
            fx_source=None,
            fx_provenance_id=None,
            effective_at=None,
            fx_snapshot_as_of=None,
        )

    if fx_snapshot is None:
        raise ValueError("cross-currency conversion requires an explicit FX snapshot")
    instant = fx_snapshot.as_of if effective_at is None else effective_at
    fx_snapshot.require_valid_at(instant)
    applied_rate, source_rate, was_inverted = fx_snapshot.rate_for(
        amount.currency_code, target_currency_code
    )

    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        unrounded = amount.amount * applied_rate
    rounded = _quantize_amount(
        unrounded, target_metadata.minor_unit_scale, target_metadata.rounding_mode
    )
    target = MoneyAmount(rounded, target_currency_code, currency_profile.profile_version)
    return MoneyConversion(
        source=amount,
        target=target,
        applied_rate=applied_rate,
        unrounded_target_amount=unrounded,
        rounding_mode=target_metadata.rounding_mode,
        metadata_profile_version=currency_profile.profile_version,
        fx_snapshot_id=fx_snapshot.snapshot_id,
        rate_base_currency=source_rate.base_currency,
        rate_quote_currency=source_rate.quote_currency,
        rate_was_inverted=was_inverted,
        fx_source=source_rate.source,
        fx_provenance_id=source_rate.provenance_id,
        effective_at=fx_snapshot.require_valid_at(instant),
        fx_snapshot_as_of=fx_snapshot.as_of,
    )
