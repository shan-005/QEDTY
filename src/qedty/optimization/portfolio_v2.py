"""Currency-neutral v2 portfolio selection reference.

Python remains the semantic authority. The v1 USD interfaces and bounded Rust
integer-knapsack operation are intentionally unchanged by this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, localcontext

from qedty.economics.currency_v2 import (
    FX_ARITHMETIC_PRECISION,
    CurrencyMetadataProfile,
    FxSnapshot,
    MoneyAmount,
    MoneyConversion,
    convert_money,
)

MAX_PORTFOLIO_ITEMS = 4096
MAX_EXACT_ITEMS = 28
MAX_EXACT_SEARCH_NODES = 200_000
_MILLION = Decimal("1000000")
_OBJECTIVE_KINDS = frozenset(
    {"continuity_gain", "weighted_score", "robust_floor", "lower_tail_cvar"}
)


def _require_decimal(value: Decimal, field_name: str, *, non_negative: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{field_name} must be a finite Decimal")
    if non_negative and value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _time_text(value: object) -> str | None:
    if value is None:
        return None
    from datetime import UTC, datetime

    if not isinstance(value, datetime):
        raise ValueError("digest timestamp must be a datetime")
    normalized = value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _money_payload(amount: MoneyAmount) -> dict[str, str]:
    return {
        "amount": _decimal_text(amount.amount),
        "currency_code": amount.currency_code,
        "metadata_profile_version": amount.metadata_profile_version,
    }


def _sum(values: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return sum(values, Decimal(0))


def _cvar(scores: tuple[Decimal, ...], alpha: Decimal) -> Decimal:
    if not scores:
        return Decimal(0)
    ordered = sorted(scores)
    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        tail_size = max(
            1,
            int(
                ((Decimal(1) - alpha) * Decimal(len(ordered))).to_integral_value(
                    rounding=ROUND_CEILING
                )
            ),
        )
        return sum(ordered[:tail_size], Decimal(0)) / Decimal(tail_size)


def _dominance(scores: tuple[Decimal, ...]) -> Decimal:
    if not scores:
        return Decimal(0)
    mean = _sum(list(scores)) / Decimal(len(scores))
    if mean == 0:
        return Decimal(1)
    return min(scores) / mean


@dataclass(frozen=True, slots=True)
class PortfolioCandidateV2:
    """One intervention and the objective/risk inputs used to select it."""

    intervention_id: str
    cost: MoneyAmount
    continuity_gain: Decimal
    risk_score: Decimal = Decimal(0)
    scenario_scores: tuple[Decimal, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.intervention_id, str)
            or not self.intervention_id.strip()
            or len(self.intervention_id.encode("utf-8")) > 128
        ):
            raise ValueError("intervention_id must be nonblank and at most 128 UTF-8 bytes")
        if not isinstance(self.cost, MoneyAmount):
            raise ValueError("cost must be a MoneyAmount")
        _require_decimal(self.continuity_gain, "continuity_gain", non_negative=True)
        _require_decimal(self.risk_score, "risk_score", non_negative=True)
        if not isinstance(self.scenario_scores, tuple):
            raise ValueError("scenario_scores must be an immutable tuple")
        for score in self.scenario_scores:
            _require_decimal(score, "scenario score")


@dataclass(frozen=True, slots=True)
class PortfolioObjectiveV2:
    """Explicit v2 objective; monetary cost is measured in millions of numeraire units."""

    kind: str = "weighted_score"
    gain_weight: Decimal = Decimal(1)
    cost_weight: Decimal = Decimal(1)
    risk_weight: Decimal = Decimal(1)
    cvar_alpha: Decimal = Decimal("0.9")

    def __post_init__(self) -> None:
        if self.kind not in _OBJECTIVE_KINDS:
            raise ValueError(f"unsupported v2 objective kind: {self.kind!r}")
        _require_decimal(self.gain_weight, "gain_weight", non_negative=True)
        _require_decimal(self.cost_weight, "cost_weight", non_negative=True)
        _require_decimal(self.risk_weight, "risk_weight", non_negative=True)
        _require_decimal(self.cvar_alpha, "cvar_alpha")
        if not Decimal(0) < self.cvar_alpha < Decimal(1):
            raise ValueError("cvar_alpha must be in (0, 1)")


@dataclass(frozen=True, slots=True)
class PortfolioRequestV2:
    """A deterministic v2 portfolio request; budget currency is the reporting currency."""

    budget: MoneyAmount
    currency_profile: CurrencyMetadataProfile
    candidates: tuple[PortfolioCandidateV2, ...]
    objective: PortfolioObjectiveV2 = field(default_factory=PortfolioObjectiveV2)
    fx_snapshot: FxSnapshot | None = None
    fixed_overhead: MoneyAmount | None = None
    scenario_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.budget, MoneyAmount):
            raise ValueError("budget must be a MoneyAmount")
        if not isinstance(self.currency_profile, CurrencyMetadataProfile):
            raise ValueError("currency_profile must be a CurrencyMetadataProfile")
        if not isinstance(self.candidates, tuple):
            raise ValueError("candidates must be an immutable tuple")
        if len(self.candidates) > MAX_PORTFOLIO_ITEMS:
            raise ValueError(f"candidate count exceeds resource limit {MAX_PORTFOLIO_ITEMS}")
        if not isinstance(self.objective, PortfolioObjectiveV2):
            raise ValueError("objective must be a PortfolioObjectiveV2")
        if self.fx_snapshot is not None and not isinstance(self.fx_snapshot, FxSnapshot):
            raise ValueError("fx_snapshot must be an FxSnapshot when supplied")
        self.currency_profile.validate_amount(self.budget)
        if self.fixed_overhead is not None:
            self.currency_profile.validate_amount(self.fixed_overhead)
        identifiers = [candidate.intervention_id for candidate in self.candidates]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("intervention IDs must be unique")
        for candidate in self.candidates:
            if not isinstance(candidate, PortfolioCandidateV2):
                raise ValueError("candidates must contain PortfolioCandidateV2 values")
            self.currency_profile.validate_amount(candidate.cost)
        if not isinstance(self.scenario_ids, tuple):
            raise ValueError("scenario_ids must be an immutable tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.scenario_ids):
            raise ValueError("scenario IDs must be nonblank strings")
        if len(set(self.scenario_ids)) != len(self.scenario_ids):
            raise ValueError("scenario IDs must be unique")
        for candidate in self.candidates:
            if len(candidate.scenario_scores) != len(self.scenario_ids):
                raise ValueError("each candidate must provide one score per declared scenario")


@dataclass(frozen=True, slots=True)
class PortfolioRecommendationV2:
    intervention_id: str
    source_cost: MoneyAmount
    reporting_cost: MoneyAmount
    continuity_gain: Decimal
    risk_score: Decimal
    scenario_scores: tuple[Decimal, ...]
    robust_score: Decimal
    efficiency: Decimal
    utility: Decimal
    selected: bool
    rationale: str
    conversion: MoneyConversion


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationResultV2:
    schema_version: str
    status: str
    solver_mode: str
    objective_kind: str
    reporting_currency_code: str
    budget: MoneyAmount
    fixed_overhead: MoneyAmount
    spent: MoneyAmount
    total_committed: MoneyAmount
    selected_intervention_ids: tuple[str, ...]
    recommendations: tuple[PortfolioRecommendationV2, ...]
    objective_value: Decimal
    portfolio_robust_floor: Decimal
    portfolio_cvar: Decimal
    dominance_score: Decimal
    scenario_ids: tuple[str, ...]
    solver_nodes: int
    fx_snapshot_id: str | None
    digest: str


def _candidate_utility(
    candidate: PortfolioCandidateV2,
    reporting_cost: Decimal,
    objective: PortfolioObjectiveV2,
) -> tuple[Decimal, Decimal, Decimal]:
    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        efficiency = (
            candidate.continuity_gain
            if reporting_cost == 0
            else candidate.continuity_gain / (reporting_cost / _MILLION)
        )
        robust_score = (
            min(candidate.scenario_scores)
            if candidate.scenario_scores
            else candidate.continuity_gain
        )
        if objective.kind == "continuity_gain":
            raw_utility = candidate.continuity_gain
        elif objective.kind == "weighted_score":
            raw_utility = (
                objective.gain_weight * candidate.continuity_gain
                - objective.cost_weight * (reporting_cost / _MILLION)
                - objective.risk_weight * candidate.risk_score
            )
        elif objective.kind == "robust_floor":
            raw_utility = robust_score
        else:
            raw_utility = _cvar(candidate.scenario_scores, objective.cvar_alpha)
        if not raw_utility.is_finite() or not efficiency.is_finite() or not robust_score.is_finite():
            raise ValueError("objective arithmetic exceeded finite Decimal range")
        return max(raw_utility, Decimal(0)), robust_score, efficiency


def _greedy_select(
    eligible: list[tuple[str, Decimal, Decimal]], available_budget: Decimal
) -> tuple[tuple[str, ...], Decimal, Decimal]:
    free_items = [item for item in eligible if item[1] == 0 and item[2] > 0]
    positive_cost_items = [item for item in eligible if item[1] > 0 and item[2] > 0]
    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        ordered = sorted(positive_cost_items, key=lambda item: (-(item[2] / item[1]), item[0]))
        selected = [item[0] for item in free_items]
        value = _sum([item[2] for item in free_items])
        spent = Decimal(0)
        for identifier, cost, utility in ordered:
            if cost <= available_budget - spent:
                selected.append(identifier)
                value += utility
                spent += cost
    return tuple(sorted(selected)), value, spent


def _select_portfolio(
    eligible: list[tuple[str, Decimal, Decimal]], available_budget: Decimal
) -> tuple[tuple[str, ...], Decimal, Decimal, str, str, int]:
    """Select exact when bounded and proved; report a non-optimality status otherwise."""
    greedy_ids, greedy_value, greedy_spent = _greedy_select(eligible, available_budget)
    positive_cost = [
        item for item in eligible if item[1] > 0 and item[2] > 0 and item[1] <= available_budget
    ]
    if len(positive_cost) > MAX_EXACT_ITEMS:
        return (
            greedy_ids,
            greedy_value,
            greedy_spent,
            "feasible_not_proven_optimal",
            "greedy_fallback",
            0,
        )

    free_items = [item for item in eligible if item[1] == 0 and item[2] > 0]
    free_ids = tuple(sorted(item[0] for item in free_items))
    free_value = _sum([item[2] for item in free_items])
    ordered = sorted(positive_cost, key=lambda item: (-(item[2] / item[1]), item[0]))
    best_ids = greedy_ids
    best_value = greedy_value
    best_spent = greedy_spent
    nodes = 0
    exhausted = False

    def consider(chosen: tuple[str, ...], value: Decimal, spent: Decimal) -> None:
        nonlocal best_ids, best_value, best_spent
        all_ids = tuple(sorted((*free_ids, *chosen)))
        if (
            value > best_value
            or (value == best_value and spent < best_spent)
            or (value == best_value and spent == best_spent and all_ids < best_ids)
        ):
            best_ids, best_value, best_spent = all_ids, value, spent

    def search(i: int, spent: Decimal, value: Decimal, chosen: tuple[str, ...]) -> None:
        nonlocal nodes, exhausted
        if exhausted:
            return
        if nodes >= MAX_EXACT_SEARCH_NODES:
            exhausted = True
            return
        nodes += 1
        if i >= len(ordered):
            consider(chosen, value, spent)
            return
        remaining = available_budget - spent
        bound = value
        for _, cost, utility in ordered[i:]:
            if cost <= remaining:
                bound += utility
                remaining -= cost
            elif remaining > 0:
                bound += utility * remaining / cost
                break
        if bound < best_value:
            return
        identifier, cost, utility = ordered[i]
        if cost <= available_budget - spent:
            search(i + 1, spent + cost, value + utility, (*chosen, identifier))
        search(i + 1, spent, value, chosen)

    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        search(0, Decimal(0), free_value, ())
    if exhausted:
        return (
            best_ids,
            best_value,
            best_spent,
            "feasible_not_proven_optimal",
            "node_limit_fallback",
            nodes,
        )
    return best_ids, best_value, best_spent, "optimal", "exact_branch_and_bound", nodes


def _profile_payload(profile: CurrencyMetadataProfile) -> dict[str, object]:
    return {
        "profile_version": profile.profile_version,
        "currencies": [
            {
                "currency_code": item.currency_code,
                "minor_unit_scale": item.minor_unit_scale,
                "rounding_mode": item.rounding_mode,
            }
            for item in sorted(profile.currencies, key=lambda entry: entry.currency_code)
        ],
    }


def _fx_payload(snapshot: FxSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "snapshot_id": snapshot.snapshot_id,
        "as_of": _time_text(snapshot.as_of),
        "valid_from": _time_text(snapshot.valid_from),
        "valid_to": _time_text(snapshot.valid_to),
        "rates": [
            {
                "base_currency": rate.base_currency,
                "quote_currency": rate.quote_currency,
                "rate": _decimal_text(rate.rate),
                "observed_at": _time_text(rate.observed_at),
                "source": rate.source,
                "provenance_id": rate.provenance_id,
            }
            for rate in sorted(
                snapshot.rates, key=lambda item: (item.base_currency, item.quote_currency)
            )
        ],
    }


def _conversion_payload(conversion: MoneyConversion) -> dict[str, object]:
    return {
        "source": _money_payload(conversion.source),
        "target": _money_payload(conversion.target),
        "applied_rate": _decimal_text(conversion.applied_rate),
        "unrounded_target_amount": _decimal_text(conversion.unrounded_target_amount),
        "rounding_mode": conversion.rounding_mode,
        "metadata_profile_version": conversion.metadata_profile_version,
        "fx_snapshot_id": conversion.fx_snapshot_id,
        "rate_base_currency": conversion.rate_base_currency,
        "rate_quote_currency": conversion.rate_quote_currency,
        "rate_was_inverted": conversion.rate_was_inverted,
        "fx_source": conversion.fx_source,
        "fx_provenance_id": conversion.fx_provenance_id,
        "effective_at": _time_text(conversion.effective_at),
        "fx_snapshot_as_of": _time_text(conversion.fx_snapshot_as_of),
        "calculation_precision": conversion.calculation_precision,
    }


def _recommendation_payload(
    recommendation: PortfolioRecommendationV2,
) -> dict[str, object]:
    return {
        "intervention_id": recommendation.intervention_id,
        "source_cost": _money_payload(recommendation.source_cost),
        "reporting_cost": _money_payload(recommendation.reporting_cost),
        "continuity_gain": _decimal_text(recommendation.continuity_gain),
        "risk_score": _decimal_text(recommendation.risk_score),
        "scenario_scores": [_decimal_text(score) for score in recommendation.scenario_scores],
        "robust_score": _decimal_text(recommendation.robust_score),
        "efficiency": _decimal_text(recommendation.efficiency),
        "utility": _decimal_text(recommendation.utility),
        "selected": recommendation.selected,
        "rationale": recommendation.rationale,
        "conversion": _conversion_payload(recommendation.conversion),
    }


def optimize_portfolio_v2(request: PortfolioRequestV2) -> PortfolioOptimizationResultV2:
    """Optimize in the budget's reporting currency with deterministic status and audit digest."""
    if not isinstance(request, PortfolioRequestV2):
        raise ValueError("request must be a PortfolioRequestV2")

    reporting_currency = request.budget.currency_code
    profile = request.currency_profile
    overhead_source = request.fixed_overhead or MoneyAmount(
        Decimal(0), reporting_currency, profile.profile_version
    )
    overhead_conversion = convert_money(
        overhead_source,
        reporting_currency,
        currency_profile=profile,
        fx_snapshot=request.fx_snapshot,
    )
    overhead = overhead_conversion.target

    converted: dict[str, MoneyConversion] = {}
    metrics: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
    candidates_by_id = {item.intervention_id: item for item in request.candidates}
    eligible: list[tuple[str, Decimal, Decimal]] = []

    for candidate in request.candidates:
        conversion = convert_money(
            candidate.cost,
            reporting_currency,
            currency_profile=profile,
            fx_snapshot=request.fx_snapshot,
        )
        converted[candidate.intervention_id] = conversion
        utility, robust_score, efficiency = _candidate_utility(
            candidate, conversion.target.amount, request.objective
        )
        metrics[candidate.intervention_id] = (utility, robust_score, efficiency)
        eligible.append((candidate.intervention_id, conversion.target.amount, utility))

    with localcontext() as context:
        context.prec = FX_ARITHMETIC_PRECISION
        context.rounding = ROUND_HALF_EVEN
        available_budget = request.budget.amount - overhead.amount

    infeasible = available_budget < 0
    if infeasible:
        selected_ids: tuple[str, ...] = ()
        objective_value = Decimal(0)
        spent_amount = Decimal(0)
        status = "infeasible"
        solver_mode = "infeasible"
        solver_nodes = 0
    else:
        (
            selected_ids,
            objective_value,
            spent_amount,
            status,
            solver_mode,
            solver_nodes,
        ) = _select_portfolio(eligible, available_budget)

    selected_set = set(selected_ids)
    recommendations = tuple(
        sorted(
            (
                PortfolioRecommendationV2(
                    intervention_id=candidate.intervention_id,
                    source_cost=candidate.cost,
                    reporting_cost=converted[candidate.intervention_id].target,
                    continuity_gain=candidate.continuity_gain,
                    risk_score=candidate.risk_score,
                    scenario_scores=candidate.scenario_scores,
                    robust_score=metrics[candidate.intervention_id][1],
                    efficiency=metrics[candidate.intervention_id][2],
                    utility=metrics[candidate.intervention_id][0],
                    selected=candidate.intervention_id in selected_set,
                    rationale=candidate.rationale,
                    conversion=converted[candidate.intervention_id],
                )
                for candidate in request.candidates
            ),
            key=lambda item: (-item.robust_score, -item.efficiency, item.intervention_id),
        )
    )
    spent = MoneyAmount(spent_amount, reporting_currency, profile.profile_version)
    total_committed = MoneyAmount(
        spent_amount + overhead.amount, reporting_currency, profile.profile_version
    )
    if request.scenario_ids and selected_ids:
        chosen_candidates = [candidates_by_id[identifier] for identifier in selected_ids]
        portfolio_scores = tuple(
            _sum([candidate.scenario_scores[i] for candidate in chosen_candidates])
            for i in range(len(request.scenario_ids))
        )
    else:
        portfolio_scores = tuple(
            metrics[identifier][1] for identifier in selected_ids
        )
    portfolio_robust_floor = min(portfolio_scores, default=Decimal(0))
    portfolio_cvar = _cvar(portfolio_scores, request.objective.cvar_alpha)
    dominance_score = _dominance(portfolio_scores)

    objective_payload = {
        "kind": request.objective.kind,
        "gain_weight": _decimal_text(request.objective.gain_weight),
        "cost_weight": _decimal_text(request.objective.cost_weight),
        "risk_weight": _decimal_text(request.objective.risk_weight),
        "cvar_alpha": _decimal_text(request.objective.cvar_alpha),
    }
    request_payload = {
        "schema_version": "2.0",
        "budget": _money_payload(request.budget),
        "fixed_overhead": (
            None if request.fixed_overhead is None else _money_payload(request.fixed_overhead)
        ),
        "currency_profile": _profile_payload(profile),
        "fx_snapshot": _fx_payload(request.fx_snapshot),
        "objective": objective_payload,
        "scenario_ids": list(request.scenario_ids),
        "candidates": [
            {
                "intervention_id": candidate.intervention_id,
                "cost": _money_payload(candidate.cost),
                "continuity_gain": _decimal_text(candidate.continuity_gain),
                "risk_score": _decimal_text(candidate.risk_score),
                "scenario_scores": [
                    _decimal_text(score) for score in candidate.scenario_scores
                ],
                "rationale": candidate.rationale,
            }
            for candidate in sorted(request.candidates, key=lambda item: item.intervention_id)
        ],
    }
    result_payload = {
        "status": status,
        "solver_mode": solver_mode,
        "selected_intervention_ids": list(selected_ids),
        "budget": _money_payload(request.budget),
        "fixed_overhead": _money_payload(overhead),
        "spent": _money_payload(spent),
        "total_committed": _money_payload(total_committed),
        "objective_value": _decimal_text(objective_value),
        "portfolio_robust_floor": _decimal_text(portfolio_robust_floor),
        "portfolio_cvar": _decimal_text(portfolio_cvar),
        "dominance_score": _decimal_text(dominance_score),
        "scenario_ids": list(request.scenario_ids),
        "solver_nodes": solver_nodes,
        "fx_snapshot_id": (
            None if request.fx_snapshot is None else request.fx_snapshot.snapshot_id
        ),
        "recommendations": [
            _recommendation_payload(item) for item in recommendations
        ],
    }
    digest = hashlib.sha256(
        json.dumps(
            {"request": request_payload, "result": result_payload},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return PortfolioOptimizationResultV2(
        schema_version="2.0",
        status=status,
        solver_mode=solver_mode,
        objective_kind=request.objective.kind,
        reporting_currency_code=reporting_currency,
        budget=request.budget,
        fixed_overhead=overhead,
        spent=spent,
        total_committed=total_committed,
        selected_intervention_ids=selected_ids,
        recommendations=recommendations,
        objective_value=objective_value,
        portfolio_robust_floor=portfolio_robust_floor,
        portfolio_cvar=portfolio_cvar,
        dominance_score=dominance_score,
        scenario_ids=request.scenario_ids,
        solver_nodes=solver_nodes,
        fx_snapshot_id=None if request.fx_snapshot is None else request.fx_snapshot.snapshot_id,
        digest=digest,
    )
