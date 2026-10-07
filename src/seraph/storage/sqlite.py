from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic import BaseModel

    from seraph.ontology.relations import Relationship

from seraph.ontology.entities import Entity


class SQLiteWorldStore:
    """Transactional local world store.

    SQLite WAL is enabled for concurrent readers. Entity and relationship writes
    are idempotent and content-addressed by their canonical JSON payloads.
    """

    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS relationships(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES entities(id), FOREIGN KEY(target_id) REFERENCES entities(id));
                CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
                CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
            """)
            c.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES ('schema_version',?)",
                (str(self.SCHEMA_VERSION),),
            )

    @staticmethod
    def _payload(model: BaseModel) -> str:
        return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        c = self._conn()
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    def put_entity(self, e: Entity) -> None:
        p = self._payload(e)
        digest = sha256(p.encode()).hexdigest()
        with self.transaction() as c:
            row = c.execute(
                "SELECT payload_sha256 FROM entities WHERE id=?", (e.entity_id,)
            ).fetchone()
            if row and row[0] != digest:
                raise ValueError("entity collision")
            c.execute(
                "INSERT OR IGNORE INTO entities(id,payload,payload_sha256) VALUES (?,?,?)",
                (e.entity_id, p, digest),
            )

    def get_entity(self, entity_id: str) -> Entity | None:
        c = self._conn()
        try:
            row = c.execute("SELECT payload FROM entities WHERE id=?", (entity_id,)).fetchone()
            if row is None:
                return None
            return Entity.model_validate(json.loads(row["payload"]))
        finally:
            c.close()

    def put_relationship(self, r: Relationship) -> None:
        p = self._payload(r)
        digest = sha256(p.encode()).hexdigest()
        with self.transaction() as c:
            if (
                c.execute("SELECT 1 FROM entities WHERE id=?", (r.source.entity_id,)).fetchone()
                is None
            ):
                raise KeyError("source missing")
            if (
                c.execute("SELECT 1 FROM entities WHERE id=?", (r.target.entity_id,)).fetchone()
                is None
            ):
                raise KeyError("target missing")
            row = c.execute(
                "SELECT payload_sha256 FROM relationships WHERE id=?", (r.relationship_id,)
            ).fetchone()
            if row and row[0] != digest:
                raise ValueError("relationship collision")
            c.execute(
                "INSERT OR IGNORE INTO relationships(id,source_id,target_id,payload,payload_sha256) VALUES (?,?,?,?,?)",
                (r.relationship_id, r.source.entity_id, r.target.entity_id, p, digest),
            )

    def counts(self) -> dict[str, int]:
        c = self._conn()
        try:
            return {
                "entities": c.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                "relationships": c.execute("SELECT COUNT(*) FROM relationships").fetchone()[0],
            }
        finally:
            c.close()

    def integrity_check(self) -> bool:
        c = self._conn()
        try:
            result = c.execute("PRAGMA integrity_check").fetchone()[0]
            return cast("str", result) == "ok"
        finally:
            c.close()
