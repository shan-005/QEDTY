"""Canonical scenario domain models.

Scenarios are conditional, explicit descriptions of alternative world states or
courses of events.  This module deliberately separates scenario description
from downstream propagation/economic/uncertainty engines.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import EpistemicStatus, EventType, InterventionType
from seraph.core.hash import canonical_json, deterministic_id, sha256_hex
from seraph.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime


class ScenarioKind(StrEnum):
    BASELINE = "baseline"
    EXPLORATORY = "exploratory"
    STRESS = "stress"
    OPERATIONAL = "operational"
    COUNTERFACTUAL = "counterfactual"
    ADAPTATION = "adaptation"


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class PatchOperation(StrEnum):
    SET = "set"
    ADD = "add"
    MULTIPLY = "multiply"
    MIN = "min"
    MAX = "max"
    REMOVE = "remove"


class ComparisonOperator(StrEnum):
    LT = "lt"
    LE = "le"
    EQ = "eq"
    NE = "ne"
    GE = "ge"
    GT = "gt"


JsonScalar = str | int | float | bool | None
JsonValue = Any


def _finite_number(value: float, field_name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


class StatePatch(BaseModel):
    """Deterministic mutation of a scenario state.

    ``path`` is either ``capacity`` or an ``attributes`` path such as
    ``attributes.operating_mode``.  Nested attribute paths are supported.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str = Field(min_length=1, max_length=256)
    path: str = Field(min_length=1, max_length=1024)
    operation: PatchOperation
    value: JsonValue = None
    reason: str = ""

    @field_validator("entity_id", "path")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("value")
    @classmethod
    def finite_numbers(cls, value: JsonValue) -> JsonValue:
        def walk(item: Any) -> None:
            if isinstance(item, float) and not isfinite(item):
                raise ValueError("patch values must be finite")
            if isinstance(item, dict):
                for nested in item.values():
                    walk(nested)
            elif isinstance(item, list):
                for nested in item:
                    walk(nested)

        walk(value)
        return value

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        if self.path != "capacity" and not self.path.startswith("attributes."):
            raise ValueError("patch path must be 'capacity' or start with 'attributes.'")
        if self.operation is PatchOperation.REMOVE and self.value is not None:
            raise ValueError("remove patches must not provide a value")
        return self


class ScenarioGuard(BaseModel):
    """Declarative guard used to branch/adapt scenario execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    path: str = Field(min_length=1, max_length=1024)
    operator: ComparisonOperator
    value: JsonValue

    @model_validator(mode="after")
    def finite(self) -> Self:
        def walk(value: Any) -> None:
            if isinstance(value, float) and not isfinite(value):
                raise ValueError("guard values must be finite")
            if isinstance(value, dict):
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(self.value)
        return self


class ScenarioBranch(BaseModel):
    """Edge in a scenario tree, with optional declarative applicability guard."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    branch_id: str = Field(min_length=1, max_length=256)
    parent_scenario_id: str = Field(min_length=1, max_length=256)
    child_scenario_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=512)
    guard: ScenarioGuard | None = None
    priority: int = Field(default=0, ge=-1_000_000, le=1_000_000)

    @model_validator(mode="after")
    def not_self(self) -> Self:
        if self.parent_scenario_id == self.child_scenario_id:
            raise ValueError("scenario branch cannot point to itself")
        return self


class Scenario(BaseModel):
    """Immutable canonical scenario descriptor.

    A scenario is conditional, not a claim about what will happen.  Probability
    is intentionally absent: probabilistic treatment belongs to Uncertainty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    scenario_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    description: str = ""
    kind: ScenarioKind = ScenarioKind.EXPLORATORY
    status: ScenarioStatus = ScenarioStatus.DRAFT
    parent_scenario_id: str | None = None
    base_world_digest: str = Field(min_length=1, max_length=256)
    base_state_digest: str | None = Field(default=None, max_length=256)
    epistemic_status: EpistemicStatus = EpistemicStatus.MODELED
    assumptions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    parameters: dict[str, float] = Field(default_factory=dict)
    capacities: dict[str, float] = Field(default_factory=dict)
    patches: tuple[StatePatch, ...] = ()
    shocks: tuple[Shock, ...] = ()
    interventions: tuple[Intervention, ...] = ()
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("valid_from", "valid_to")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @field_validator("scenario_id", "name")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("parameters")
    @classmethod
    def finite_parameters(cls, value: dict[str, float]) -> dict[str, float]:
        for key, number in value.items():
            if not key.strip():
                raise ValueError("parameter names must not be blank")
            _finite_number(number, f"parameter[{key}]")
            if number < 0:
                raise ValueError("capacity multipliers must be non-negative")
        return dict(sorted(value.items()))

    @field_validator("capacities")
    @classmethod
    def valid_capacities(cls, value: dict[str, float]) -> dict[str, float]:
        for key, number in value.items():
            if not key.strip():
                raise ValueError("capacity entity ids must not be blank")
            _finite_number(number, f"capacity[{key}]")
            if not 0.0 <= number <= 1.0:
                raise ValueError("capacity overrides must be between 0 and 1")
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.parent_scenario_id == self.scenario_id:
            raise ValueError("scenario cannot be its own parent")
        if self.base_state_digest == self.scenario_id:
            raise ValueError("base_state_digest cannot equal scenario_id")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("invalid scenario interval")
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("duplicate scenario tags")
        if len({shock.shock_id for shock in self.shocks}) != len(self.shocks):
            raise ValueError("duplicate shock ids")
        if len({item.intervention_id for item in self.interventions}) != len(self.interventions):
            raise ValueError("duplicate intervention ids")
        return self

    @classmethod
    def build(
        cls,
        *,
        name: str,
        base_world_digest: str,
        parent_scenario_id: str | None = None,
        kind: ScenarioKind = ScenarioKind.EXPLORATORY,
        **kwargs: Any,
    ) -> Scenario:
        scenario_id = deterministic_id(
            "scenario",
            base_world_digest,
            parent_scenario_id,
            name.casefold().strip(),
            kind.value,
            canonical_json(kwargs),
        )
        return cls(
            scenario_id=scenario_id,
            name=name,
            base_world_digest=base_world_digest,
            parent_scenario_id=parent_scenario_id,
            kind=kind,
            **kwargs,
        )

    @property
    def digest(self) -> str:
        return sha256_hex(self.model_dump(mode="json"))


class Shock(BaseModel):
    """Explicit initiating or exogenous scenario event.

    Severity is descriptive.  State consequences are only materialized when
    an explicit capacity multiplier or patch is provided; this avoids silently
    treating every event severity as a causal capacity loss.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    shock_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    event_type: EventType
    source_entity_id: str = Field(min_length=1, max_length=256)
    starts_at: datetime
    ends_at: datetime
    severity: float = Field(ge=0, le=1)
    epistemic_status: EpistemicStatus = EpistemicStatus.MODELED
    target_entity_ids: tuple[str, ...] = ()
    capacity_multipliers: dict[str, float] = Field(default_factory=dict)
    patches: tuple[StatePatch, ...] = ()
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("shock ends_at must be after starts_at")
        if any(not item.strip() for item in self.target_entity_ids):
            raise ValueError("target_entity_ids must not be blank")
        if len(set(self.target_entity_ids)) != len(self.target_entity_ids):
            raise ValueError("duplicate target_entity_ids")
        for entity_id, multiplier in self.capacity_multipliers.items():
            if not entity_id.strip():
                raise ValueError("shock capacity entity ids must not be blank")
            _finite_number(multiplier, f"capacity_multipliers[{entity_id}]")
            if not 0.0 <= multiplier <= 1.0:
                raise ValueError("shock capacity multipliers must be between 0 and 1")
        return self

    def normalized(self) -> Shock:
        return self.model_copy(
            update={"starts_at": ensure_utc(self.starts_at), "ends_at": ensure_utc(self.ends_at)}
        )

    def active_at(self, at: datetime) -> bool:
        instant = ensure_utc(at)
        return self.starts_at <= instant < self.ends_at

    @property
    def duration_seconds(self) -> float:
        return (self.ends_at - self.starts_at).total_seconds()


class Intervention(BaseModel):
    """Explicit action applied to protect or alter a scenario state."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    intervention_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    intervention_type: InterventionType
    cost_usd: float = Field(ge=0)
    protected_entity_ids: tuple[str, ...] = ()
    transmission_reduction: float = Field(default=0, ge=0, le=1)
    capacity_gain: float = Field(default=0, ge=0, le=1)
    activation_at: datetime | None = None
    deactivation_at: datetime | None = None
    patches: tuple[StatePatch, ...] = ()
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("activation_at", "deactivation_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            self.deactivation_at
            and self.activation_at
            and self.deactivation_at <= self.activation_at
        ):
            raise ValueError("intervention deactivation must be after activation")
        if len(set(self.protected_entity_ids)) != len(self.protected_entity_ids):
            raise ValueError("duplicate protected entity ids")
        if not self.protected_entity_ids and (
            self.transmission_reduction or self.capacity_gain or self.patches
        ):
            raise ValueError("intervention effects require protected entities")
        return self

    def active_at(self, at: datetime | None) -> bool:
        if at is None:
            return self.activation_at is None
        instant = ensure_utc(at)
        return (self.activation_at is None or instant >= self.activation_at) and (
            self.deactivation_at is None or instant < self.deactivation_at
        )


class ScenarioRun(BaseModel):
    """Deterministic execution record for a scenario application."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    run_id: str = Field(min_length=1, max_length=256)
    scenario_id: str
    base_digest: str
    result_digest: str
    applied_shock_ids: tuple[str, ...] = ()
    applied_intervention_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    epistemic_status: EpistemicStatus = EpistemicStatus.MODELED

    @property
    def deterministic_key(self) -> str:
        return deterministic_id(
            "scenario-run", self.scenario_id, self.base_digest, self.result_digest
        )


class ScenarioTree(BaseModel):
    """Validated scenario tree definition for branching alternatives."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    root_scenario_id: str = Field(min_length=1, max_length=256)
    scenarios: tuple[Scenario, ...]
    branches: tuple[ScenarioBranch, ...] = ()

    @model_validator(mode="after")
    def valid(self) -> Self:
        scenario_ids = {item.scenario_id for item in self.scenarios}
        if self.root_scenario_id not in scenario_ids:
            raise ValueError("root scenario must be included")
        if len(scenario_ids) != len(self.scenarios):
            raise ValueError("duplicate scenario ids")
        parents: dict[str, str] = {}
        branch_ids: set[str] = set()
        branch_pairs: set[tuple[str, str]] = set()
        scenario_index = {item.scenario_id: item for item in self.scenarios}
        for branch in self.branches:
            if branch.branch_id in branch_ids:
                raise ValueError("duplicate branch ids")
            branch_ids.add(branch.branch_id)
            pair = (branch.parent_scenario_id, branch.child_scenario_id)
            if pair in branch_pairs:
                raise ValueError("duplicate scenario branch")
            branch_pairs.add(pair)
            if (
                branch.parent_scenario_id not in scenario_ids
                or branch.child_scenario_id not in scenario_ids
            ):
                raise ValueError("branch references unknown scenario")
            previous_parent = parents.get(branch.child_scenario_id)
            if previous_parent is not None and previous_parent != branch.parent_scenario_id:
                raise ValueError("scenario tree child cannot have multiple parents")
            child = scenario_index[branch.child_scenario_id]
            if (
                child.parent_scenario_id is not None
                and child.parent_scenario_id != branch.parent_scenario_id
            ):
                raise ValueError("scenario parent_scenario_id conflicts with tree branch")
            parents[branch.child_scenario_id] = branch.parent_scenario_id
        if self.root_scenario_id in parents:
            raise ValueError("root scenario cannot have a parent")
        self._assert_acyclic(scenario_ids)
        self._assert_rooted(scenario_ids)
        return self

    def _assert_acyclic(self, scenario_ids: set[str]) -> None:
        children: dict[str, list[str]] = {item: [] for item in scenario_ids}
        for branch in self.branches:
            children[branch.parent_scenario_id].append(branch.child_scenario_id)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("scenario tree contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for child in children[node]:
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(scenario_ids):
            visit(node)

    def _assert_rooted(self, scenario_ids: set[str]) -> None:
        children: dict[str, list[str]] = {item: [] for item in scenario_ids}
        for branch in self.branches:
            children[branch.parent_scenario_id].append(branch.child_scenario_id)
        reachable: set[str] = set()
        stack = [self.root_scenario_id]
        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)
            stack.extend(children[node])
        if reachable != scenario_ids:
            missing = sorted(scenario_ids - reachable)
            raise ValueError(f"scenario tree is disconnected from root: {missing}")

    def children_of(self, scenario_id: str) -> tuple[Scenario, ...]:
        child_ids = [
            branch.child_scenario_id
            for branch in self.branches
            if branch.parent_scenario_id == scenario_id
        ]
        index = {scenario.scenario_id: scenario for scenario in self.scenarios}
        return tuple(index[item] for item in sorted(child_ids))


Scenario.model_rebuild()
