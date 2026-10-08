from __future__ import annotations

from .intervals import AllenRelation, Interval, classify

ALLEN_RELATIONS: tuple[AllenRelation, ...] = tuple(AllenRelation)


def relation(left: Interval, right: Interval) -> AllenRelation:
    return classify(left, right)


def inverse(value: AllenRelation) -> AllenRelation:
    mapping = {
        AllenRelation.BEFORE: AllenRelation.AFTER,
        AllenRelation.AFTER: AllenRelation.BEFORE,
        AllenRelation.MEETS: AllenRelation.MET_BY,
        AllenRelation.MET_BY: AllenRelation.MEETS,
        AllenRelation.OVERLAPS: AllenRelation.OVERLAPPED_BY,
        AllenRelation.OVERLAPPED_BY: AllenRelation.OVERLAPS,
        AllenRelation.STARTS: AllenRelation.STARTED_BY,
        AllenRelation.STARTED_BY: AllenRelation.STARTS,
        AllenRelation.DURING: AllenRelation.CONTAINS,
        AllenRelation.CONTAINS: AllenRelation.DURING,
        AllenRelation.FINISHES: AllenRelation.FINISHED_BY,
        AllenRelation.FINISHED_BY: AllenRelation.FINISHES,
        AllenRelation.EQUALS: AllenRelation.EQUALS,
    }
    return mapping[value]
