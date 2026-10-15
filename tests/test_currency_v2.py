from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

import pytest

from qedty.economics.currency_v2 import (
    CurrencyMetadata,
    CurrencyMetadataProfile,
    FxRate,
    FxSnapshot,
    MoneyAmount,
    convert_money,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)


def profile() -> CurrencyMetadataProfile:
    return CurrencyMetadataProfile(
        profile_version="fixture-v1",
        currencies=(
            CurrencyMetadata("AAA", 3, ROUND_HALF_UP),
            CurrencyMetadata("BBB", 2, ROUND_HALF_UP),
            CurrencyMetadata("CCC", 2),
        ),
    )


def fx_snapshot(*rates: FxRate) -> FxSnapshot:
    return FxSnapshot(
        snapshot_id="fx-fixture-1",
        as_of=T1,
        valid_from=T0,
        valid_to=T2,
        rates=tuple(rates),
    )


def rate(base: str, quote: str, value: str, *, observed_at: datetime = T0) -> FxRate:
    return FxRate(
        base_currency=base,
        quote_currency=quote,
        rate=Decimal(value),
        observed_at=observed_at,
        source="independent-fixture",
        provenance_id=f"fixture:{base}/{quote}",
    )


def money(value: str, currency: str = "AAA", version: str = "fixture-v1") -> MoneyAmount:
    return MoneyAmount(Decimal(value), currency, version)


def test_currency_metadata_is_data_driven_and_rounding_is_explicit() -> None:
    arbitrary_code_profile = CurrencyMetadataProfile(
        "custom-profile",
        (CurrencyMetadata("XQZ", 4, ROUND_HALF_UP),),
    )
    arbitrary_code_profile.validate_amount(money("1.2345", "XQZ", "custom-profile"))
    assert arbitrary_code_profile.metadata_for("XQZ").minor_unit_scale == 4


def test_direct_conversion_rounds_once_to_target_minor_unit() -> None:
    result = convert_money(
        money("1.005"),
        "BBB",
        currency_profile=profile(),
        fx_snapshot=fx_snapshot(rate("AAA", "BBB", "1")),
    )
    assert result.unrounded_target_amount == Decimal("1.005")
    assert result.target.amount == Decimal("1.01")
    assert result.rounding_mode == ROUND_HALF_UP
    assert result.fx_snapshot_id == "fx-fixture-1"
    assert result.fx_provenance_id == "fixture:AAA/BBB"
    assert result.rate_was_inverted is False
    assert result.calculation_precision == 34


def test_reciprocal_rate_is_explicit_and_auditable() -> None:
    result = convert_money(
        money("4.00", "BBB"),
        "AAA",
        currency_profile=profile(),
        fx_snapshot=fx_snapshot(rate("AAA", "BBB", "2")),
    )
    assert result.applied_rate == Decimal("0.5")
    assert result.target.amount == Decimal("2.000")
    assert result.rate_was_inverted is True
    assert result.rate_base_currency == "AAA"
    assert result.rate_quote_currency == "BBB"


def test_same_currency_conversion_needs_no_fx_snapshot() -> None:
    result = convert_money(money("12.300"), "AAA", currency_profile=profile())
    assert result.target.amount == Decimal("12.300")
    assert result.applied_rate == Decimal(1)
    assert result.fx_snapshot_id is None
    assert result.fx_source is None


def test_cross_currency_conversion_requires_explicit_snapshot() -> None:
    with pytest.raises(ValueError, match="explicit FX snapshot"):
        convert_money(money("1.000"), "BBB", currency_profile=profile())


def test_missing_cross_rate_does_not_triangulate_implicitly() -> None:
    snapshot = fx_snapshot(
        rate("AAA", "BBB", "2"),
        rate("BBB", "CCC", "3"),
    )
    with pytest.raises(ValueError, match="triangulation is disabled"):
        convert_money(money("1.000"), "CCC", currency_profile=profile(), fx_snapshot=snapshot)


def test_snapshot_validity_uses_half_open_interval() -> None:
    snapshot = fx_snapshot(rate("AAA", "BBB", "2"))
    with pytest.raises(ValueError, match="not valid"):
        convert_money(
            money("1.000"),
            "BBB",
            currency_profile=profile(),
            fx_snapshot=snapshot,
            effective_at=T2,
        )


def test_input_precision_must_match_metadata_profile() -> None:
    with pytest.raises(ValueError, match="minor-unit scale"):
        profile().validate_amount(money("1.2345"))
    with pytest.raises(ValueError, match="profile version"):
        profile().validate_amount(money("1.00", version="other-profile"))


@pytest.mark.parametrize(
    ("amount", "currency"),
    [
        (Decimal("-1"), "AAA"),
        (Decimal("NaN"), "AAA"),
        (Decimal("Infinity"), "AAA"),
    ],
)
def test_non_finite_and_negative_money_is_rejected(amount: Decimal, currency: str) -> None:
    with pytest.raises(ValueError):
        MoneyAmount(amount, currency, "fixture-v1")


def test_float_money_is_rejected_at_boundary() -> None:
    with pytest.raises(ValueError, match="Decimal"):
        MoneyAmount(1.25, "AAA", "fixture-v1")  # type: ignore[arg-type]


def test_invalid_and_ambiguous_fx_quotes_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive Decimal"):
        rate("AAA", "BBB", "0")
    with pytest.raises(ValueError, match="only one directional quote"):
        fx_snapshot(rate("AAA", "BBB", "2"), rate("BBB", "AAA", "0.5"))


def test_timezone_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FxRate(
            base_currency="AAA",
            quote_currency="BBB",
            rate=Decimal("2"),
            observed_at=datetime(2026, 1, 1),
            source="fixture",
            provenance_id="fixture:naive",
        )
