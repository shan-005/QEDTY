from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from seraph.pci.core.types import Relationship
from seraph.pci.entities.models import Entity
from seraph.pci.graph.store import TemporalGraph


class SQLiteGraphStore:
    """Durable graph storage using SQLite transactions, WAL, and explicit foreign keys."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES entities(entity_id),
                    FOREIGN KEY(target_id) REFERENCES entities(entity_id)
                );
                CREATE INDEX IF NOT EXISTS idx_relationship_source ON relationships(source_id);
                CREATE INDEX IF NOT EXISTS idx_relationship_target ON relationships(target_id);
                """
            )

    def put_entity(self, entity: Entity) -> None:
        payload = json.dumps(entity.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with self.connection() as connection:
            existing = connection.execute("SELECT payload FROM entities WHERE entity_id=?", (entity.entity_id,)).fetchone()
            if existing is not None and existing[0] != payload:
                raise ValueError(f"entity conflict for {entity.entity_id}")
            connection.execute("INSERT OR IGNORE INTO entities(entity_id,payload) VALUES(?,?)", (entity.entity_id, payload))

    def put_relationship(self, relationship: Relationship) -> None:
        payload = json.dumps(relationship.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with self.connection() as connection:
            existing = connection.execute("SELECT payload FROM relationships WHERE relationship_id=?", (relationship.relationship_id,)).fetchone()
            if existing is not None and existing[0] != payload:
                raise ValueError(f"relationship conflict for {relationship.relationship_id}")
            connection.execute("INSERT OR IGNORE INTO relationships(relationship_id,source_id,target_id,payload) VALUES(?,?,?,?)", (relationship.relationship_id, relationship.source.entity_id, relationship.target.entity_id, payload))

    def load(self) -> TemporalGraph:
        graph = TemporalGraph()
        with self.connection() as connection:
            entities = [Entity.model_validate(json.loads(row[0]), strict=False) for row in connection.execute("SELECT payload FROM entities ORDER BY entity_id")]
            relationships = [Relationship.model_validate(json.loads(row[0]), strict=False) for row in connection.execute("SELECT payload FROM relationships ORDER BY relationship_id")]
        graph.bulk_add(entities, relationships)
        return graph
