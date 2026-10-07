# Temporal competency questions

The reference implementation must support at least these questions:

1. Was a fact true at an instant?
2. Did two temporal extents intersect, meet, or overlap?
3. Which Allen relation holds between two finite intervals?
4. What was the latest state known at a historical transaction time?
5. What state was true at a requested valid time?
6. Can a snapshot be deterministically identified by world digest + temporal selector?
7. Can temporal records be bucketed at calendar-aware granularities?
8. Can temporal joins return the exact intersection extent?
9. Can an index return records active at an instant or overlapping a query interval?
10. Can all of the above be represented without changing semantics at the JSON/Protobuf/Arrow/RDF boundaries?
