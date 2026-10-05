from datetime import datetime, timezone

import pytest

from seraph.core.enums import EntityType, EpistemicStatus, RelationshipType
from seraph.core.ids import deterministic_id
from seraph.core.types import EntityRef, Relationship
from seraph.entities.models import Entity


UTC = timezone.utc


def make_entity(entity_type: EntityType, name: str) -> Entity:
    return Entity(
        entity_id=deterministic_id("entity", "seraph", entity_type.value, name.casefold()),
        entity_type=entity_type,
        canonical_name=name,
    )


def test_entity_identity_is_deterministic() -> None:
    entity = make_entity(EntityType.COMPANY, "Example Company")
    assert entity.entity_id == deterministic_id(
        "entity", "seraph", EntityType.COMPANY.value, "example company"
    )


def test_relationship_rejects_wrong_identity() -> None:
    source = make_entity(EntityType.COMPANY, "Source")
    target = make_entity(EntityType.SERVICE, "Target")
    with pytest.raises(ValueError, match="relationship_id"):
        Relationship(
            relationship_id="not-deterministic",
            source=EntityRef(entity_id=source.entity_id),
            target=EntityRef(entity_id=target.entity_id),
            relationship_type=RelationshipType.SUPPORTS,
        )


def test_observed_status_is_explicit() -> None:
    entity = make_entity(EntityType.COMPANY, "Observed Company")
    assert entity.epistemic_status is EpistemicStatus.OBSERVED


def test_self_loop_is_rejected_for_non_membership_relationship() -> None:
    entity = make_entity(EntityType.COMPANY, "Loop")
    relationship_id = deterministic_id(
        "rel",
        entity.entity_id,
        entity.entity_id,
        RelationshipType.SUPPORTS.value,
        None,
        None,
    )
    with pytest.raises(ValueError, match="self-loop"):
        Relationship(
            relationship_id=relationship_id,
            source=EntityRef(entity_id=entity.entity_id),
            target=EntityRef(entity_id=entity.entity_id),
            relationship_type=RelationshipType.SUPPORTS,
        )
