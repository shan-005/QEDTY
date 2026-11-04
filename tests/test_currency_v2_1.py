from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

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


def _profile() -> CurrencyMetadataProfile:
    return CurrencyMetadataProfile(
        "fx-v21-fixture",
        tuple(CurrencyMetadata(code, 2) for code in ("AAA", "BBB", "CCC", "DDD")),
    )


def _rate(
    base: str,
    quote: str,
    value: str,
    *,
    spread_bps: int = 0,
    fee_bps: int = 0,
) -> FxRate:
    return FxRate(
        base,
        quote,
        Decimal(value),
        T0,
        "independent-fixture",
        f"fx:{base}/{quote}",
        spread_bps,
        fee_bps,
    )


def _snapshot(*rates: FxRate) -> FxSnapshot:
    return FxSnapshot("fx-v21", T1, T0, T2, tuple(rates))


def _money(value: str = "1.00") -> MoneyAmount:
    return MoneyAmount(Decimal(value), "AAA", "fx-v21-fixture")


def test_v21_uses_deterministic_shortest_then_lexical_path() -> None:
    snapshot = _snapshot(
        _rate("AAA", "CCC", "5"),
        _rate("CCC", "DDD", "2"),
        _rate("AAA", "BBB", "3"),
        _rate("BBB", "DDD", "4"),
    )
    result = convert_money(
        _money(),
        "DDD",
        currency_profile=_profile(),
        fx_snapshot=snapshot,
        schema_version="2.1",
    )

    assert [leg.source_currency for leg in result.fx_path] == ["AAA", "BBB"]
    assert [leg.target_currency for leg in result.fx_path] == ["BBB", "DDD"]
    assert result.fx_path_policy == "fewest_hops_then_lexicographic_currency_path"
    assert result.applied_rate == Decimal(12)
    assert result.unrounded_target_amount == Decimal("12.00")
    assert result.target.amount == Decimal("12.00")


def test_v21_applies_spread_and_fee_on_each_leg_before_final_rounding() -> None:
    snapshot = _snapshot(
        _rate("AAA", "BBB", "2", spread_bps=200, fee_bps=100),
        _rate("BBB", "CCC", "3", spread_bps=100, fee_bps=50),
    )
    result = convert_money(
        _money(),
        "CCC",
        currency_profile=_profile(),
        fx_snapshot=snapshot,
        schema_version="2.1",
    )

    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        first = Decimal(2) * Decimal("0.99") * Decimal("0.99")
        second = Decimal(3) * Decimal("0.995") * Decimal("0.995")
        expected_rate = first * second

    assert result.applied_rate == expected_rate
    assert result.unrounded_target_amount == expected_rate
    assert result.target.amount == expected_rate.quantize(Decimal("0.01"))
    assert len(result.fx_path) == 2
    assert result.fx_path[0].rate.provenance_id == "fx:AAA/BBB"
    assert result.fx_path[1].rate.provenance_id == "fx:BBB/CCC"


def test_v20_rejects_nonzero_spread_or_fee_instead_of_ignoring_them() -> None:
    snapshot = _snapshot(_rate("AAA", "BBB", "2", fee_bps=25))
    with pytest.raises(ValueError, match=r"require schema_version 2\.1"):
        convert_money(
            _money(),
            "BBB",
            currency_profile=_profile(),
            fx_snapshot=snapshot,
            schema_version="2.0",
        )


@pytest.mark.parametrize(
    ("field_value", "field_name"),
    [(20000, "spread_bps"), (10000, "fee_bps"), (-1, "fee_bps"), (True, "fee_bps")],
)
def test_v21_rejects_invalid_basis_point_values(field_value: int, field_name: str) -> None:
    kwargs = {field_name: field_value}
    with pytest.raises(ValueError, match=field_name):
        _rate("AAA", "BBB", "2", **kwargs)


def test_v21_missing_path_fails_closed() -> None:
    snapshot = _snapshot(_rate("AAA", "BBB", "2"))
    with pytest.raises(ValueError, match="missing FX conversion path"):
        convert_money(
            _money(),
            "CCC",
            currency_profile=_profile(),
            fx_snapshot=snapshot,
            schema_version="2.1",
        )


def test_v21_small_reciprocal_rate_quantizes_large_target_amount() -> None:
    snapshot = _snapshot(_rate("AAA", "BBB", "0." + ("0" * 33) + "1"))
    amount = MoneyAmount(
        Decimal("0.01"),
        "BBB",
        "fx-v21-fixture",
    )

    result = convert_money(
        amount,
        "AAA",
        currency_profile=_profile(),
        fx_snapshot=snapshot,
        schema_version="2.1",
    )

    assert result.applied_rate == Decimal("1E+34")
    assert result.unrounded_target_amount == Decimal("1E+32")
    assert result.target.amount == Decimal("100000000000000000000000000000000.00")
