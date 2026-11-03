from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from qedty.economics.currency_v2 import (
    CurrencyMetadata,
    CurrencyMetadataProfile,
    FxRate,
    FxSnapshot,
    MoneyAmount,
)
from qedty.optimization.portfolio_v2 import (
    PortfolioCandidateV2,
    PortfolioObjectiveV2,
    PortfolioRequestV2,
    _conversion_payload,
    optimize_portfolio_v2,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)
PROFILE_VERSION = "portfolio-fx-v21"
FX_PATH_POLICY = "fewest_hops_then_lexicographic_currency_path"


def test_portfolio_v21_selects_lexical_fx_path_and_preserves_cost_audit() -> None:
    profile = CurrencyMetadataProfile(
        PROFILE_VERSION,
        tuple(CurrencyMetadata(code, 2) for code in ("AAA", "BBB", "CCC", "DDD")),
    )

    rates = (
        FxRate(
            "AAA", "CCC", Decimal(5), T0,
            "fixture-market-a", "fixture:AAA/CCC",
        ),
        FxRate(
            "CCC", "DDD", Decimal(2), T0,
            "fixture-market-b", "fixture:CCC/DDD",
        ),
        FxRate(
            "AAA", "BBB", Decimal(3), T0,
            "fixture-market-c", "fixture:AAA/BBB",
            spread_bps=200, fee_bps=100,
        ),
        FxRate(
            "BBB", "DDD", Decimal(4), T0,
            "fixture-market-d", "fixture:BBB/DDD",
            spread_bps=100, fee_bps=50,
        ),
    )
    snapshot = FxSnapshot(
        "fx-portfolio-v21-cross-language",
        T1,
        T0,
        T2,
        rates,
    )

    candidate = PortfolioCandidateV2(
        intervention_id="multi-hop-infrastructure",
        cost=MoneyAmount(Decimal("1.00"), "AAA", PROFILE_VERSION),
        continuity_gain=Decimal(10),
        risk_score=Decimal(0),
        scenario_scores=(),
    )
    request = PortfolioRequestV2(
        budget=MoneyAmount(Decimal("20.00"), "DDD", PROFILE_VERSION),
        currency_profile=profile,
        candidates=(candidate,),
        objective=PortfolioObjectiveV2(kind="continuity_gain"),
        fx_snapshot=snapshot,
        schema_version="2.1",
    )

    result = optimize_portfolio_v2(request)

    assert result.schema_version == "2.1"
    assert result.status == "optimal"
    assert result.selected_intervention_ids == ("multi-hop-infrastructure",)

    recommendation = result.recommendations[0]
    conversion = recommendation.conversion

    assert recommendation.reporting_cost.amount == Decimal("11.64")
    assert conversion.target.currency_code == "DDD"
    assert conversion.target.amount == Decimal("11.64")
    assert conversion.applied_rate == Decimal("11.64388203")
    assert conversion.unrounded_target_amount == Decimal("11.64388203")

    assert conversion.fx_path_policy == FX_PATH_POLICY
    assert [
        (leg.source_currency, leg.target_currency)
        for leg in conversion.fx_path
    ] == [("AAA", "BBB"), ("BBB", "DDD")]

    first, second = conversion.fx_path
    assert first.applied_rate == Decimal("2.9403")
    assert first.rate.spread_bps == 200
    assert first.rate.fee_bps == 100
    assert first.rate.provenance_id == "fixture:AAA/BBB"

    assert second.applied_rate == Decimal("3.9601")
    assert second.rate.spread_bps == 100
    assert second.rate.fee_bps == 50
    assert second.rate.provenance_id == "fixture:BBB/DDD"

    # Verify the actual serialized conversion audit matches the v2.1 contract.
    payload = _conversion_payload(conversion)
    assert payload["applied_rate"] == "11.64388203"
    assert payload["target"]["amount"] == "11.64"
    assert payload["fx_path_policy"] == FX_PATH_POLICY
    assert [leg["fx_provenance_id"] for leg in payload["fx_path"]] == [
        "fixture:AAA/BBB",
        "fixture:BBB/DDD",
    ]
